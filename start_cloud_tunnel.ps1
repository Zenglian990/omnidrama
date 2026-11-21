# OmniDrama 免费公网隧道一键启动脚本
# 采用无感免绑卡安全 SSH 隧道，将本地 8765 端口打通到全球 HTTPS 公网

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "      OmniDrama 零成本云端服务穿透启动器                  " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "正在连接公网安全隧道..." -ForegroundColor Green

ssh -o StrictHostKeyChecking=no -R 80:127.0.0.1:8765 nokey@localhost.run
