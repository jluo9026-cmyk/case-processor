@echo off
chcp 65001 >nul
title 附件处理器合并版

cd /d "%~dp0"

echo ========================================
echo    附件处理器 - 一键连续流程版
echo    上传 → 映射 → Markdown → Word 一键完成
echo ========================================
echo.

:: 检查Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请先安装
    pause
    exit /b 1
)

:: 检查依赖
if not exist "node_modules" (
    echo [提示] 正在安装依赖...
    call npm install
)

echo.
echo [提示] 启动服务器中...
echo [提示] 访问地址: http://localhost:3000
echo [提示] 新增：一键连续流程 + SSE实时进度
echo [提示] 备份在 backup_20260602 目录中
echo [提示] 按 Ctrl+C 停止服务器
echo.

node server.js

pause
