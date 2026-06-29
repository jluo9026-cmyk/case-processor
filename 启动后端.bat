@echo off
chcp 65001 >nul
title 案件处理系统
cd /d "%~dp0"
echo ========================================
echo     案件处理系统 - 启动器
echo ========================================
echo.
echo 后端服务已内置于 Electron 应用，
echo 无需单独启动后端。
echo.
echo 正在启动应用...
echo.
npm start
pause
