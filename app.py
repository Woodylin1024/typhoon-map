# app.py
from flask import Flask, render_template, request, jsonify
from pathlib import Path
import json, os, sys, threading, webbrowser, socket

# ---------------------------
# 路徑：開發模式 / PyInstaller
# ---------------------------
def get_app_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent

ROOT = get_app_root()
TEMPLATE_DIR = ROOT / "templates"
STATIC_DIR   = ROOT / "static"
CACHE_DIR    = ROOT / "data" / "cache"

app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    template_folder=str(TEMPLATE_DIR)
)

VALID_LEVELS = {"熱帶性低氣壓","輕度颱風","中度颱風","強烈颱風"}
VALID_BASINS = {"NA","EP","CP","WP","NI","SI","SP"}

# ---------------------------
# 首頁
# ---------------------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------------------------
# API：依 年 + 盆地(+等級) 取資料
# /api/typhoons?year=2009&basins=WP&basins=NA&levels=中度颱風
# ---------------------------
@app.route("/api/typhoons")
def api_typhoons():
    year   = request.args.get("year", type=int)
    basins = [b.upper() for b in request.args.getlist("basins")]
    levels = request.args.getlist("levels")

    if not year:
        return jsonify({"error": "缺少 year"}), 400

    # 前端若未勾任何盆地：回傳空集合即可（避免 400）
    if not basins:
        return jsonify({"type": "FeatureCollection", "features": [], "debug": {
            "year": year, "basins": [], "levels": levels, "count": 0
        }})

    # 僅保留合法盆地代碼
    basins = [b for b in basins if b in VALID_BASINS]
    features = []

    for b in basins:
        fpath = CACHE_DIR / f"{b.lower()}_{year}.geojson"
        if not fpath.exists():
            continue
        try:
            with fpath.open(encoding="utf-8") as f:
                geo = json.load(f)
        except Exception as e:
            print(f"[ERROR] 讀取失敗 {fpath}: {e}")
            continue

        for ft in geo.get("features", []):
            props = ft.get("properties", {}) or {}
            basin_prop = (props.get("basin") or "").upper().strip()
            cat = props.get("category")


            # 僅接受完全一致或子代碼（例如 NA, NA1, NA2…）
            if not any(basin_prop == sel or basin_prop.startswith(sel) for sel in basins):
                continue
            if levels and cat not in VALID_LEVELS:
                continue
            if levels and cat not in levels:
                continue

            features.append(ft)

    return jsonify({
        "type": "FeatureCollection",
        "features": features,
        "debug": {"year": year, "basins": basins, "levels": levels, "count": len(features)}
    })

# ---------------------------
# 啟動：自動找可用埠並開瀏覽器
# ---------------------------
def find_free_port() -> int:
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def run():
    port = int(os.environ.get("PORT", 0)) or find_free_port()
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host="127.0.0.1", port=port, debug=False)

if __name__ == "__main__":
    run()
