@echo off
chcp 65001 >nul
title Download Paket Offline untuk Mini PC (Jalankan di Laptop Ber-Internet)
cd /d "%~dp0"

echo ======================================================================
echo   Download Dependensi Python untuk Instalasi Offline di Mini PC
echo   (Jalankan file ini di Laptop/PC yang memiliki koneksi internet)
echo ======================================================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak terdeteksi di laptop ini!
    pause
    exit /b 1
)

echo Membuat folder 'offline_packages'...
if not exist "offline_packages" mkdir "offline_packages"

echo.
echo Sedang mendownload file wheel (.whl) untuk Windows 64-bit...
echo Mohon tunggu beberapa saat...
echo.

:: Opsi 1: Coba download khusus target Python 3.11 win_amd64
python -m pip download -r open_orgatex\backend\requirements.txt -d offline_packages --only-binary=:all: --python-version 3.11 --platform win_amd64

if %errorlevel% neq 0 (
    echo.
    echo [INFO] Mencoba metode download standar sesuai environment lokal...
    python -m pip download -r open_orgatex\backend\requirements.txt -d offline_packages
)

echo.
echo ======================================================================
echo [SELESAI] Semua file .whl telah tersimpan di folder 'offline_packages'!
echo.
echo Langkah selanjutnya:
echo 1. Salin seluruh folder DA-TEX ini ke Flashdisk.
echo 2. Colokkan Flashdisk ke Mini PC.
echo 3. Di Mini PC, cukup klik 2x: INSTALL_DEPENDENSI.bat
echo    (Proses instalasi akan otomatis berjalan 100%% OFFLINE tanpa internet!)
echo ======================================================================
echo.
pause
