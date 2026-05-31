@echo off
title YouTube Karaoke - Song List Filter & Corrector Bot
cd /d "%~dp0"

echo Menyiapkan environment...
if not exist "..\\python_embed\\python.exe" (
    echo Python portabel tidak ditemukan. Menjalankan installer otomatis...
    powershell -NoProfile -ExecutionPolicy Bypass -File "..\\setup.ps1"
) else (
    echo Environment siap.
)

if %ERRORLEVEL% NEQ 0 (
    echo Gagal menyiapkan environment. Silakan periksa koneksi internet Anda.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Menjalankan Song List Filter & Corrector Bot...
..\python_embed\python.exe filter_songs.py
if %ERRORLEVEL% NEQ 0 (
    echo Terjadi kesalahan saat menjalankan filter bot.
)
echo.
echo Proses selesai atau dihentikan.
pause
