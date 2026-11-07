param([switch]$FrontendOnly, [switch]$UseExistingBackend)
$ErrorActionPreference = 'Stop'
$uiRoot = Split-Path $PSScriptRoot -Parent
$codeRoot = Join-Path (Split-Path $uiRoot -Parent) 'CGC\HamtayarDemo'
$backend = $null
Push-Location $uiRoot
try {
    if (-not $FrontendOnly -and -not $UseExistingBackend) {
        $python = Join-Path $codeRoot 'backend\.venv\Scripts\python.exe'
        if (-not (Test-Path $python)) { throw 'First configure CGC/HamtayarDemo using its setup guide, or use -FrontendOnly for document demos.' }
        if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 8000 is already occupied. If the correct CGC backend is running, use -UseExistingBackend.' }
        $runtime = Join-Path $uiRoot 'runtime'
        New-Item -ItemType Directory -Force $runtime | Out-Null
        $backend = Start-Process -FilePath $python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory (Join-Path $codeRoot 'backend') -RedirectStandardOutput (Join-Path $runtime 'code-backend.out.log') -RedirectStandardError (Join-Path $runtime 'code-backend.err.log') -PassThru
        $ready = $false
        for ($attempt=0; $attempt -lt 40; $attempt++) {
            if ($backend.HasExited) { throw "CGC backend stopped. Check $runtime/code-backend.err.log" }
            try { $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; if ($health.status -eq 'running') { $ready=$true; break } } catch { }
            Start-Sleep -Milliseconds 250
        }
        if (-not $ready) { throw "CGC backend did not become ready. Check $runtime/code-backend.err.log" }
    }
    Write-Host 'Unified dashboard: http://127.0.0.1:5174 (no second frontend is needed)'
    & npm.cmd run dev
    if ($LASTEXITCODE -ne 0) { throw 'The frontend stopped with an error.' }
} finally {
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue }
    Pop-Location
}
