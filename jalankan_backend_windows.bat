@echo off
title OpenOrgaTEX Backend (Native Windows)
cd /d "%~dp0"

echo ======================================================================
echo   OpenOrgaTEX Industrial MES Backend (Native Windows)
echo   Port: 8743 (Dukungan Penuh QueueTool.exe & BtrieveInterface.dll)
echo ======================================================================
echo.

:: Pastikan port 8743 tidak bentrok dengan container Docker lama
echo Menghentikan container backend Docker jika sedang aktif...
docker stop openorgatex_backend >nul 2>&1

echo.
echo Memulai backend server di http://localhost:8743 ...
python -m uvicorn open_orgatex.backend.app:app --host 0.0.0.0 --port 8743 --reload

pause
