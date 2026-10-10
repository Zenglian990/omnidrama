# LocalTunnel Watchdog: Automatically maintains https://omnidrama-zeng.loca.lt
while ($true) {
    Write-Host "[Watchdog $(Get-Date -Format 'HH:mm:ss')] Starting localtunnel on port 8765 with subdomain omnidrama-zeng..." -ForegroundColor Cyan
    try {
        npx -y localtunnel --port 8765 --subdomain omnidrama-zeng
    } catch {
        Write-Host "[Watchdog] Process exited with error: $_" -ForegroundColor Red
    }
    Write-Host "[Watchdog] Connection closed. Restarting in 2 seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
}
