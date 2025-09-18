# scripts/prepare_ibtracs.py  （強化版：一定判得出盆地）
import argparse, json
from pathlib import Path
import pandas as pd
import requests

CSV_URL = ("https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/"
           "v04r01/access/csv/ibtracs.ALL.list.v04r01.csv")

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

VALID_BASINS = {"NA","EP","CP","WP","NI","SI","SP"}

def kt_to_ms(kt): return kt * 0.514444 if pd.notna(kt) else None
def cwa_category(ms):
    if pd.isna(ms): return None
    if ms < 17.2: return "熱帶性低氣壓"
    if ms <= 24.4: return "輕度颱風"
    if ms <= 32.6: return "中度颱風"
    return "強烈颱風"

def download_csv(force=False):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / "ibtracs.csv"
    if csv_path.exists() and not force:
        print(f"[INFO] 使用現有 {csv_path}（加 --redownload 會重抓）")
        return csv_path
    print(f"[INFO] 下載 IBTrACS CSV ...")
    r = requests.get(CSV_URL, timeout=300)
    r.raise_for_status()
    csv_path.write_bytes(r.content)
    print(f"[OK] 已下載：{csv_path}")
    return csv_path

def load_data(csv_path, y0, y1):
    usecols = ["SID","SEASON","BASIN","SUBBASIN","NAME","ISO_TIME","LAT","LON","WMO_WIND","USA_ATCF_ID"]
    df = pd.read_csv(csv_path, usecols=usecols, low_memory=False)
    df = df.dropna(subset=["ISO_TIME","LAT","LON"])
    df["SEASON"] = pd.to_numeric(df["SEASON"], errors="coerce").astype("Int64")
    df["LAT"] = pd.to_numeric(df["LAT"], errors="coerce")
    df["LON"] = pd.to_numeric(df["LON"], errors="coerce")
    df["WMO_WIND"] = pd.to_numeric(df["WMO_WIND"], errors="coerce")
    df["ISO_TIME"] = pd.to_datetime(df["ISO_TIME"], errors="coerce", utc=True)
    df = df.dropna(subset=["SEASON","LAT","LON","ISO_TIME"])
    df = df[(df["SEASON"] >= y0) & (df["SEASON"] <= y1)]
    return df

def basin_from_atcf(atcf_id: str, lon_median: float, lat_median: float) -> str | None:
    if not isinstance(atcf_id, str) or len(atcf_id) < 2: return None
    p = atcf_id[:2].upper()
    if p == "AL": return "NA"
    if p == "EP": return "EP"
    if p == "CP": return "CP"
    if p == "WP": return "WP"
    if p == "IO": return "NI"
    if p == "SH":
        # 南半球：用經度粗分（約 20E–135E 為南印度洋，其東側為南太平洋）
        if lon_median is None: return "SI"
        lon = ((lon_median + 180) % 360) - 180  # 正規化到 [-180,180)
        return "SI" if 20 <= lon < 135 else "SP"
    return None

def basin_fallback_by_coords(lon_median: float, lat_median: float) -> str:
    # 非常粗略的保底分區，避免 None
    lon = ((lon_median + 180) % 360) - 180
    if lat_median >= 0:
        if -100 <= lon < 0: return "NA"        # 北大西洋（很粗）
        if -180 <= lon < -100: return "EP"    # 東北太平洋西段
        if -140 <= lon < -120: return "CP"    # 中北太平洋大致範圍
        return "WP"
    else:
        return "SI" if 20 <= lon < 135 else "SP"

def choose_basin_for_track(g: pd.DataFrame) -> str:
    # 1) SUBBASIN/BASIN 取眾數（去空白大寫）
    series = pd.concat([g.get("SUBBASIN"), g.get("BASIN")], ignore_index=True)
    series = series.dropna().astype(str).str.upper().str.strip()
    codes = [c for c in series if c in VALID_BASINS]
    if codes:
        return pd.Series(codes).mode().iloc[0]

    # 2) USA_ATCF_ID 前綴判斷
    lon_med = float(g["LON"].median()) if not g["LON"].isna().all() else None
    lat_med = float(g["LAT"].median()) if not g["LAT"].isna().all() else None
    atcf = g.get("USA_ATCF_ID")
    if atcf is not None and atcf.notna().any():
        basin2 = basin_from_atcf(str(atcf.dropna().iloc[0]), lon_med, lat_med)
        if basin2 in VALID_BASINS:
            return basin2

    # 3) 以座標粗略判斷（保底）
    return basin_fallback_by_coords(lon_med or 0.0, lat_med or 0.0)

def build_cache(df: pd.DataFrame, allow_basins: set[str]):
    grouped = df.sort_values("ISO_TIME").groupby("SID")
    storms = []
    for sid, g in grouped:
        season = int(g["SEASON"].iloc[0])
        basin  = choose_basin_for_track(g)
        if basin not in allow_basins:
            continue

        name = (g["NAME"].dropna().iloc[0] if g["NAME"].notna().any() else "UNKNOWN").title()
        coords = [[float(lon), float(lat)] for lon, lat in zip(g["LON"], g["LAT"])]
        t_start, t_end = g["ISO_TIME"].iloc[0], g["ISO_TIME"].iloc[-1]
        max_ms = kt_to_ms(g["WMO_WIND"].max(skipna=True))
        cat = cwa_category(max_ms)

        storms.append({
            "sid": sid, "season": season, "basin": basin, "name": name,
            "time_start": t_start.isoformat(), "time_end": t_end.isoformat(),
            "max_wind_ms": None if max_ms is None else round(float(max_ms),1),
            "category": cat, "coordinates": coords
        })

    # 分 (year, basin) 輸出
    by_yb = {}
    for s in storms:
        by_yb.setdefault((s["season"], s["basin"]), []).append(s)

    summary = {}
    for (year, basin), items in sorted(by_yb.items()):
        feats = [{
            "type":"Feature",
            "geometry":{"type":"LineString","coordinates": s["coordinates"]},
            "properties":{
                "sid": s["sid"], "name": s["name"], "season": s["season"], "basin": s["basin"],
                "time_start": s["time_start"], "time_end": s["time_end"],
                "max_wind_ms": s["max_wind_ms"], "category": s["category"]
            }
        } for s in items]
        out = {"type":"FeatureCollection","features":feats}
        out_path = CACHE_DIR / f"{basin.lower()}_{year}.geojson"
        out_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        print(f"[OK] {out_path} storms={len(items)}")
        summary.setdefault(year, {})[basin] = len(items)

    print("\n[SUMMARY] 每年各盆地計數（有資料才列）")
    for y in sorted(summary):
        parts = [f"{b}:{summary[y][b]}" for b in sorted(summary[y])]
        print(f"  {y} -> " + ", ".join(parts))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="y0", type=int, required=True)
    ap.add_argument("--to", dest="y1", type=int, required=True)
    ap.add_argument("--basins", nargs="*", default=list(VALID_BASINS))
    ap.add_argument("--redownload", action="store_true")
    args = ap.parse_args()

    allow = {b.upper() for b in args.basins if b.upper() in VALID_BASINS}
    if not allow:
        raise SystemExit("basins 參數無效，允許值：" + ", ".join(sorted(VALID_BASINS)))

    csv_path = download_csv(force=args.redownload)
    df = load_data(csv_path, args.y0, args.y1)
    build_cache(df, allow)
    print("\n[DONE] 請至 data/cache/ 檢查輸出檔。")

if __name__ == "__main__":
    main()
