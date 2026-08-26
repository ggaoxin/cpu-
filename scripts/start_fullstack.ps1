param(
    [switch]$UseSqlite,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if ($UseSqlite) {
    $env:DATABASE_URL = "sqlite:///$($ProjectRoot.Replace('\', '/'))/runtime/semantic_toolkit.db"
}

$env:VITE_DEV_PORT = [string]$FrontendPort
$env:VITE_API_TARGET = "http://127.0.0.1:$BackendPort"

Start-Process -FilePath 'python' -ArgumentList @('-m', 'uvicorn', 'presentation.main:app', '--host', '127.0.0.1', '--port', $BackendPort, '--reload') -WorkingDirectory $ProjectRoot -WindowStyle Hidden
Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'dev', '--', '--port', $FrontendPort) -WorkingDirectory (Join-Path $ProjectRoot 'frontend') -WindowStyle Hidden

Write-Host "后端：http://127.0.0.1:$BackendPort/docs"
Write-Host "前端：http://127.0.0.1:$FrontendPort"
