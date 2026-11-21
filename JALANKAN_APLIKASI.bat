@echo off
chcp 65001 >nul
title OpenOrgaTEX Industrial MES (Native Tanpa Docker)
cd /d "%~dp0"

echo ======================================================================
echo   OpenOrgaTEX Industrial MES - Server Mode (Tanpa Docker)
echo ======================================================================
echo.

:: 1. Verifikasi Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python belum terpasang atau belum masuk PATH!
    echo Silakan jalankan INSTALL_DEPENDENSI.bat terlebih dahulu.
    echo.
    pause
    exit /b 1
)

:: 2. Tampilkan Info IP Mini PC agar mudah diakses dari browser lain
echo Mendeteksi alamat IP Mini PC...
for /f "tokens=4" %%a in ('route print ^| findstr 0.0.0.0 ^| findstr /v "0.0.0.0.*0.0.0.0"') do (
    set DEFAULT_IP=%%a
)

echo.
echo ======================================================================
echo   STATUS APLIKASI AKTIF:
echo   - Akses dari Mini PC ini : http://localhost:8743
echo   - Akses dari Browser Luar: http://%DEFAULT_IP%:8743  (atau IP Wi-Fi)
echo   - Koneksi Kabel LAN HMI  : 192.168.1.95:21 (FTP aktif)
echo ======================================================================
echo.
echo Membuka browser otomatis...
start http://localhost:8743

echo Memulai server backend dan frontend di port 8743...
echo Tekan Ctrl+C untuk menghentikan server.
echo.

set "PYTHONPATH=%~dp0;%~dp0..;%PYTHONPATH%"
python -m uvicorn open_orgatex.backend.app:app --host 0.0.0.0 --port 8743

pause
