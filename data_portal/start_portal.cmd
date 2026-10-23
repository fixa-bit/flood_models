@echo off
title Flood Data Observatory - Local
cd /d "%~dp0"
echo Starting your local portal. No login is required.
echo Open http://127.0.0.1:8787 in your browser.
python serve.py
if errorlevel 1 pause
