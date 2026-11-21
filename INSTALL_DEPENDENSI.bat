@echo off
chcp 65001 >nul
title OpenOrgaTEX - Installer Dependensi Mini PC (Otomatis Offline / Online)
cd /d "%~dp0"

echo ======================================================================
echo   OpenOrgaTEX - Setup & Install Dependensi Mini PC
echo ======================================================================
echo.

:: 1. Cek Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak terdeteksi di sistem ini!
    echo Silakan install Python 3.11 dari installer offline yang Anda bawa.
    echo PENTING: Saat instalasi, pastikan centang opsi "Add python.exe to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo [OK] Menggunakan: %PY_VER%
echo.

:: 2. Cek apakah ada folder offline_packages
set OFFLINE_MODE=0
if exist "offline_packages\*.whl" (
    set OFFLINE_MODE=1
)

if %OFFLINE_MODE%==1 (
    echo ======================================================================
    echo [MODE OFFLINE TERDETEKSI]
    echo Ditemukan file paket di folder 'offline_packages'.
    echo Memasang paket secara OFFLINE (tanpa memerlukan koneksi internet)...
    echo ======================================================================
    echo.
    python -m pip install --no-index --find-links=offline_packages -r open_orgatex\backend\requirements.txt
) else (
    echo ======================================================================
    echo [MODE ONLINE]
    echo Folder 'offline_packages' tidak ditemukan. Mencoba via internet...
    echo ======================================================================
    echo.
    python -m pip install --upgrade pip
    python -m pip install -r open_orgatex\backend\requirements.txt
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Gagal memasang dependensi!
    if %OFFLINE_MODE%==0 (
        echo Karena Mini PC tidak terhubung internet, silakan:
        echo 1. Jalankan DOWNLOAD_DEPENDENSI_OFFLINE.bat di laptop yang ber-internet.
        echo 2. Copy folder 'offline_packages' ke Mini PC ini.
        echo 3. Jalankan kembali script ini.
    )
    echo.
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo [BERHASIL] Semua dependensi telah terpasang dengan sempurna!
echo Anda sekarang bisa langsung menjalankan aplikasi dengan klik:
echo   --> JALANKAN_APLIKASI.bat
echo ======================================================================
echo.
pause
