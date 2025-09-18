param(
  [int]$FromYear = 1990,
  [int]$ToYear   = 2024,
  [string]$PythonPath = ""   # 可選：若系統找不到 python，指定 python.exe 完整路徑
)

$ErrorActionPreference = "Stop"

# --- 輸出避免亂碼 ---
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Get-PythonCmd {
  if ($PythonPath -and (Test-Path $PythonPath)) { return "`"$PythonPath`"" }
  try { & py -V 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { return "py" } } catch {}
  try { & python -V 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { return "python" } } catch {}
  throw "找不到 Python。請安裝 Python 3，或用 -PythonPath 指向 python.exe。"
}

Write-Host "=== 放寬當前視窗的腳本限制（僅此視窗生效） ==="
try { Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force } catch {}

$py = Get-PythonCmd
Write-Host "=== 使用 Python 指令：$py ==="

# 1) 建立虛擬環境（若已有則略過）
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "=== 建立虛擬環境 ==="
  & $py -m venv .venv
}

# 2) 啟用虛擬環境（多方案：ps1 或 bat）
try {
  . .\.venv\Scripts\Activate.ps1
} catch {
  & .\.venv\Scripts\activate.bat
}

Write-Host "=== 升級 pip ==="
& python -m pip install --upgrade pip

Write-Host "=== 安裝預處理依賴（pandas、requests）==="
& python -m pip install pandas==2.2.2 requests==2.32.3

Write-Host "=== 產生 IBTrACS 全球快取（$FromYear-$ToYear）==="
# 你的 scripts/prepare_ibtracs.py 已改成『依盆地×年份』輸出
& python .\scripts\prepare_ibtracs.py --from $FromYear --to $ToYear

Write-Host "=== 安裝執行期依賴（Flask）與打包工具（PyInstaller）==="
& python -m pip install Flask==3.0.3
& python -m pip install pyinstaller==6.6.0

Write-Host "=== 清理舊的 build/dist ==="
Remove-Item -Recurse -Force .\build, .\dist, .\__pycache__ -ErrorAction SilentlyContinue

Write-Host "=== 重新打包（以 spec 檔）==="
# 以模組方式執行，避免被防毒擋 pyinstaller.exe
& python -m PyInstaller .\typhoon-map.spec --clean --noconfirm

Write-Host "=== 完成！輸出：dist\typhoon-map.exe ==="
