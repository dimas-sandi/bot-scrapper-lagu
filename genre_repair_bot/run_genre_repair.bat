@echo off
title Karaoke Genre Repair Bot
cd /d "%~dp0"
..\python_embed\python.exe repair_genres.py
pause
