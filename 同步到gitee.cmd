@echo off
chcp 65001 >nul
setlocal
title Sync to Gitee
cd /d "%~dp0"
if "%~1"=="" ( set "MSG=update: %DATE% %TIME%" ) else ( set "MSG=%~1" )
git add -A
git diff --cached --quiet && ( echo [i] nothing to commit & goto push )
git -c user.name=Lilhand -c user.email=lilhand@users.noreply.gitee.com commit -m "%MSG%"
:push
git push gitee HEAD:main
exit /b %errorlevel%
