@echo off
chcp 65001 >nul
setlocal
title Sync to Gitee + GitHub
cd /d "%~dp0"
git add -A
git diff --cached --quiet
if errorlevel 1 (
  if not "%~1"=="" (
    git -c user.name=Lilhand -c user.email=lilhand@users.noreply.gitee.com commit -q -m "%~1"
  ) else if exist "commitmsg.txt" (
    git -c user.name=Lilhand -c user.email=lilhand@users.noreply.gitee.com commit -q -F commitmsg.txt
  ) else (
    git -c user.name=Lilhand -c user.email=lilhand@users.noreply.gitee.com commit -q -m "update: %DATE% %TIME%"
  )
  if errorlevel 1 ( echo [!] commit failed & exit /b 1 )
) else (
  echo [i] no changes to commit
)
git push gitee HEAD:main
if errorlevel 1 ( echo [!] gitee push failed & exit /b 1 )
git push github HEAD:main
if errorlevel 1 ( echo [!] github push failed & exit /b 1 )
echo [OK] https://gitee.com/lilhand/simple-3d-game
echo [OK] https://github.com/2680419938-wq/simple-3d-game
exit /b 0
