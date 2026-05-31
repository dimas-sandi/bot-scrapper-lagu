@echo off
title Chordtela Playlist Generator Bot
cd /d "%~dp0"
..\python_embed\python.exe generate_chordtela_list.py
pause
