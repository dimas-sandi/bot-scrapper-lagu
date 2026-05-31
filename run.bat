@echo off
title YouTube Karaoke Downloader Bot
cd /d "%~dp0"

echo Menyiapkan environment...
if not exist "python_embed\python.exe" (
    echo Python portabel tidak ditemukan. Menjalankan installer otomatis...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
) else if not exist "bin\ffmpeg.exe" (
    echo FFmpeg portabel tidak ditemukan. Menjalankan installer otomatis...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
) else (
    echo Environment siap.
)

if %ERRORLEVEL% NEQ 0 (
    echo Gagal menyiapkan environment. Silakan periksa koneksi internet Anda.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Menjalankan YouTube Karaoke Downloader Bot...
python_embed\python.exe src\main.py --role server
if %ERRORLEVEL% NEQ 0 (
    echo Terjadi kesalahan saat menjalankan bot.
    pause
)
