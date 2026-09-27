# Starts the Sounding backend and frontend in two new windows, then opens the app.
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File "<path to>\start.ps1"

$root = $PSScriptRoot

Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location -LiteralPath '$root\backend'; uv run uvicorn app.main:app --port 8000"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location -LiteralPath '$root\frontend'; npm run dev"

Start-Sleep -Seconds 4
Start-Process 'http://localhost:5173'
