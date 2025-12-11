@echo off
chcp 65001 > nul
title MapTrack Bot Runner
cd /d "%~dp0"
python bot.py
python bot_runner.py
pause
