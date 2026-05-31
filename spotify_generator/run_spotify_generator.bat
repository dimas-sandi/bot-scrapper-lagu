@echo off
title YouTube Karaoke - Music API Playlist Generator Bot (Deezer)
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
echo Menjalankan Spotify API Playlist Generator Bot...
..\python_embed\python.exe generate_spotify_list.py
if %ERRORLEVEL% NEQ 0 (
    echo Terjadi kesalahan saat menjalankan Spotify generator.
)
echo.
echo Proses selesai atau dihentikan.
pause
