param([string]$PythonPath, [string]$Device = 'cpu', [int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$demoRoot = $PSScriptRoot
if (-not $PythonPath) {
    $workspacePython = Join-Path (Split-Path $demoRoot -Parent) '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $workspacePython) { $PythonPath = $workspacePython }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $PythonPath = (Get-Command python).Source }
    else { throw 'Python was not found. Pass -PythonPath with your Python environment.' }
}
$env:SENTINEL_DEVICE = $Device
$env:YOLO_CONFIG_DIR = Join-Path $demoRoot '.runtime'
if (-not $env:SENTINEL_ALLOWED_ORIGINS) {
    $env:SENTINEL_ALLOWED_ORIGINS = "http://127.0.0.1:$Port,http://localhost:$Port,https://sentinel-yolov8-lab-vuong.new-reed-9170.chatgpt.site"
}
# Set SENTINEL_ALLOWED_ORIGINS explicitly for a remote WSS deployment.
Write-Host "Sentinel dashboard: http://127.0.0.1:$Port"
Push-Location $demoRoot
try { & $PythonPath -m uvicorn backend.app:app --host 127.0.0.1 --port $Port --workers 1 --ws-max-size 2000000 }
finally { Pop-Location }
