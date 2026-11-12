@echo off
chcp 65001 >nul
setlocal
title Sync to Gitee
cd /d "%~dp0"
if "%~1"=="" ( set "MSG=update: %DATE% %TIME%" ) else ( set "MSG=%~1" )
git add -A
git diff --cached --quiet
if errorlevel 1 (
  git -c user.name=Lilhand -c user.email=lilhand@users.noreply.gitee.com commit -q -m "%MSG%"
  if errorlevel 1 ( echo [!] commit failed & exit /b 1 )
) else (
  echo [i] no changes to commit
)
git push gitee HEAD:main
if errorlevel 1 ( echo [!] push failed & exit /b 1 )
echo [OK] pushed to https://gitee.com/lilhand/simple-3d-game
exit /b 0
