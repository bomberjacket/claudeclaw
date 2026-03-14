# Run this script as Administrator to fix the PM2 service
$nssm = "C:\Users\shopp\AppData\Local\Microsoft\WinGet\Packages\NSSM.NSSM_Microsoft.Winget.Source_8wekyb3d8bbwe\nssm-2.24-101-g897c7ad\win64\nssm.exe"
$nodePath = "C:\Program Files\nodejs\node.exe"
$pm2Path = "C:\Users\shopp\AppData\Roaming\npm\node_modules\pm2\bin\pm2"
$ecosystemPath = "C:\Users\shopp\bni-agents\claudeclaw\ecosystem.config.js"

# Stop and remove old service
& $nssm stop PM2 2>$null
& $nssm remove PM2 confirm 2>$null

# Install with --no-daemon so NSSM keeps the process alive
& $nssm install PM2 $nodePath "$pm2Path start $ecosystemPath --no-daemon"

# Configure
& $nssm set PM2 DisplayName "PM2 Process Manager"
& $nssm set PM2 Description "Keeps ClaudeClaw bots running as a Windows service"
& $nssm set PM2 Start SERVICE_AUTO_START
& $nssm set PM2 AppDirectory "C:\Users\shopp\bni-agents\claudeclaw"
& $nssm set PM2 AppEnvironmentExtra "HOME=C:\Users\shopp" "PM2_HOME=C:\Users\shopp\.pm2" "NODE_ENV=production" "PATH=C:\Program Files\nodejs;C:\Users\shopp\AppData\Roaming\npm;%PATH%"

# Logging
& $nssm set PM2 AppStdout "C:\Users\shopp\.pm2\pm2-service.log"
& $nssm set PM2 AppStderr "C:\Users\shopp\.pm2\pm2-service-error.log"
& $nssm set PM2 AppStdoutCreationDisposition 4
& $nssm set PM2 AppStderrCreationDisposition 4
& $nssm set PM2 AppRotateFiles 1
& $nssm set PM2 AppRotateBytes 1048576

# Start
& $nssm start PM2

Write-Host ""
Write-Host "PM2 service fixed and started!" -ForegroundColor Green
Write-Host "It now starts from ecosystem.config.js in no-daemon mode." -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to close"
