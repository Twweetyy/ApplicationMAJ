$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $python = $venvPython
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python est introuvable. Installe Python 3.11+ ou crée le venv du projet dans .venv."
    }
    $python = $pythonCommand.Source
}

$webappPath = Join-Path $projectRoot "webapp.py"
if (-not (Test-Path $webappPath)) {
    throw "webapp.py est introuvable dans $projectRoot"
}

& $python -c "import fastapi, uvicorn, multipart" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Les dépendances web manquent. Lance d'abord : .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
try {
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
} finally {
    $listener.Stop()
}

$server = Start-Process `
    -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "webapp:app", "--host", "127.0.0.1", "--port", "$port") `
    -WorkingDirectory $projectRoot `
    -PassThru

$url = "http://127.0.0.1:$port"
Write-Host "Portail BDDMAS : $url" -ForegroundColor Green
Write-Host "Les logs restent dans la fenêtre du serveur. Ferme-la ou fais Ctrl+C pour arrêter." -ForegroundColor DarkGray
Start-Process $url
