@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PolySub 智能同传启动器

if not exist "setting.json" (
    if exist "setting.example.json" (
        copy "setting.example.json" "setting.json" >nul
        echo [INFO] 已自动根据模板初始化 setting.json
    )
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "app.pyw"
    exit /b
)
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" "app.pyw"
    exit /b
)
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw "app.pyw"
    exit /b
)
where python >nul 2>nul
if %errorlevel% equ 0 (
    start "" python "app.pyw"
    exit /b
)

echo [ERROR] 未检测到 Python 环境，请安装 Python 3.10+ 并执行 pip install -r requirements.txt
pause
