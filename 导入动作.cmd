@echo off
chcp 65001 >nul
setlocal
title Import an animation clip onto DragonMan
set "HERE=%~dp0"
set "BLENDER=D:\steam\steamapps\common\Blender\blender.exe"
set "SCRIPT=%HERE%AnimLib\retarget_import.py"
set "INBOX=%HERE%AnimLib\in"
if not exist "%INBOX%" mkdir "%INBOX%"

if not "%~1"=="" (
  call :one "%~1"
) else (
  set "FOUND="
  for %%F in ("%INBOX%\*.fbx") do if exist "%%~F" call :one "%%~F"
  for %%F in ("%INBOX%\*.bvh") do if exist "%%~F" call :one "%%~F"
)
echo.
pause
exit /b 0

:one
set "SRC=%~1"
set "NAME=%~n1"
set "NAME=%NAME: =_%"
echo ---- %SRC%  ->  clip %NAME%
"%BLENDER%" -b --factory-startup --python "%SCRIPT%" -- --src "%SRC%" --clip "%NAME%"
if errorlevel 1 (
  echo [!] %NAME% failed
  exit /b 1
)
copy /y "%HERE%AnimLib\out\DragonMan_Std_%NAME%.glb" "%HERE%dragon-man-final\DragonMan_Std_%NAME%.glb" >nul
if not exist "%HERE%web-preview\public" mkdir "%HERE%web-preview\public"
copy /y "%HERE%AnimLib\out\DragonMan_Std_%NAME%.glb" "%HERE%web-preview\public\DragonMan_Std_%NAME%.glb" >nul
echo [OK] %NAME%  -^>  AnimLib\out\DragonMan_Std_%NAME%.glb
echo      preview: http://127.0.0.1:5199/?glb=/DragonMan_Std_%NAME%.glb
exit /b 0
