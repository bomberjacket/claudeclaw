@echo off
set HOME=C:\Users\shopp
set PM2_HOME=C:\Users\shopp\.pm2
"C:\Program Files\nodejs\node.exe" "C:\Users\shopp\AppData\Roaming\npm\node_modules\pm2\bin\pm2" resurrect
"C:\Program Files\nodejs\node.exe" "C:\Users\shopp\AppData\Roaming\npm\node_modules\pm2\bin\pm2" logs --raw
