# Run this script as Administrator to install PM2 as a Windows service
# Right-click -> Run with PowerShell (as Admin)

$nssm = "C:\Users\shopp\AppData\Local\Microsoft\WinGet\Packages\NSSM.NSSM_Microsoft.Winget.Source_8wekyb3d8bbwe\nssm-2.24-101-g897c7ad\win64\nssm.exe"
$nodePath = "C:\Program Files\nodejs\node.exe"
$pm2Path = "C:\Users\shopp\AppData\Roaming\npm\node_modules\pm2\bin\pm2"

# Remove existing service if any
& $nssm stop PM2 2>$null
& $nssm remove PM2 confirm 2>$null

# Install PM2 as a service using node directly
& $nssm install PM2 $nodePath $pm2Path resurrect

# Configure the service
& $nssm set PM2 DisplayName "PM2 Process Manager"
& $nssm set PM2 Description "Keeps PM2-managed Node.js apps running as a Windows service"
& $nssm set PM2 Start SERVICE_AUTO_START
& $nssm set PM2 AppDirectory "C:\Users\shopp"

# Set environment variables so PM2 can find everything
& $nssm set PM2 AppEnvironmentExtra "HOME=C:\Users\shopp" "PM2_HOME=C:\Users\shopp\.pm2" "PATH=C:\Program Files\nodejs;C:\Users\shopp\AppData\Roaming\npm;%PATH%"

# Configure logging
& $nssm set PM2 AppStdout "C:\Users\shopp\.pm2\pm2-service.log"
& $nssm set PM2 AppStderr "C:\Users\shopp\.pm2\pm2-service-error.log"
& $nssm set PM2 AppStdoutCreationDisposition 4
& $nssm set PM2 AppStderrCreationDisposition 4
& $nssm set PM2 AppRotateFiles 1
& $nssm set PM2 AppRotateBytes 1048576

# Start the service
& $nssm start PM2

Write-Host ""
Write-Host "PM2 service installed and started!" -ForegroundColor Green
Write-Host "Your bots will now survive logoff and restart on boot." -ForegroundColor Green
Write-Host ""
Write-Host "Verify with: nssm status PM2" -ForegroundColor Cyan
Write-Host "Or check: Get-Service PM2" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close"
