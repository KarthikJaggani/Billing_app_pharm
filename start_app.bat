@echo off
del log.txt >nul 2>&1

tasklist /FI "IMAGENAME eq python.exe" | find /I "python.exe" >nul
if %ERRORLEVEL%==0 (
    taskkill /F /IM python.exe >nul 2>&1
    timeout /t 2 >nul
)

cd /d "C:\Users\ssanj\Documents\KJ_app\flask_pharmacy_static_hsph"
start "" "C:\Users\ssanj\AppData\Local\Programs\Python\Python313\pythonw.exe" app.py 
timeout /t 3 >nul
start http://127.0.0.1:5000
