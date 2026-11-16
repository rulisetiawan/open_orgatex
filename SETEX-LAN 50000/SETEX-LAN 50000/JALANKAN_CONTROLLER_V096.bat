@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 setex_reader.py
  goto selesai
)
where python >nul 2>nul
if not errorlevel 1 (
  python setex_reader.py
  goto selesai
)
set "BUNDLED=C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1105-1297-0_26.1105.1297.0_x64__3k8sg7r9htsxt\dependencies\python\python.exe"
if exist "%BUNDLED%" (
  "%BUNDLED%" setex_reader.py
  goto selesai
)
echo Python tidak ditemukan. Instal Python 3.10 atau lebih baru dengan Tcl/Tk.
:selesai
if errorlevel 1 pause
