@echo off
chcp 65001 >nul
title OpenOrgaTEX - Installer Dependensi Mini PC
cd /d "%~dp0"

echo ======================================================================
echo   OpenOrgaTEX - Setup & Install Dependensi (Tanpa Docker)
echo ======================================================================
echo.

:: 1. Cek Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak terdeteksi di sistem ini!
    echo Silakan install Python 3.10 atau 3.11 dari https://www.python.org/
    echo PENTING: Saat instalasi, pastikan centang opsi "Add python.exe to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo [OK] Menggunakan: %PY_VER%
echo.

:: 2. Upgrade pip & install requirements
echo Mengunduh dan memasang paket dependensi backend...
python -m pip install --upgrade pip
python -m pip install -r open_orgatex\backend\requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Gagal memasang beberapa dependensi. Pastikan Mini PC terhubung ke internet.
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo [BERHASIL] Semua dependensi telah terpasang dengan sukses!
echo Anda sekarang bisa langsung menjalankan aplikasi dengan klik:
echo   --> JALANKAN_APLIKASI.bat
echo ======================================================================
echo.
pause
