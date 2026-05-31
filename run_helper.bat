@echo off
title YouTube Karaoke Downloader - Laptop Helper
cd /d "%~dp0"

echo Menyiapkan environment di Laptop Helper...
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
    echo Gagal menyiapkan environment di Laptop. Silakan periksa koneksi internet Anda.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Menjalankan YouTube Karaoke Downloader - LAPTOP HELPER...
python_embed\python.exe src\main.py --role client
if %ERRORLEVEL% NEQ 0 (
    echo Terjadi kesalahan saat menjalankan helper.
    pause
)
