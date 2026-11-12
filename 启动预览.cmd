@echo off
chcp 65001 >nul
setlocal
title DragonMan Preview
cd /d "%~dp0web-preview"

set "NODE="
for %%I in (node.exe) do if not defined NODE set "NODE=%%~$PATH:I"
if not defined NODE if exist "C:\Program Files\nodejs\node.exe" set "NODE=C:\Program Files\nodejs\node.exe"
if not defined NODE if exist "%LOCALAPPDATA%\Programs\nodejs\node.exe" set "NODE=%LOCALAPPDATA%\Programs\nodejs\node.exe"
if not defined NODE if exist "C:\Users\26804\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe" set "NODE=C:\Users\26804\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"

if not defined NODE (
  echo [x] node.exe not found. Install Node.js ^(https://nodejs.org^) and run again.
  pause
  exit /b 1
)

if not exist "node_modules\vite\bin\vite.js" (
  echo [x] web-preview\node_modules is missing. Run "pnpm install" inside web-preview first.
  pause
  exit /b 1
)

echo Building latest page...
"%NODE%" "node_modules\vite\bin\vite.js" build --logLevel warn
if errorlevel 1 echo [!] build failed - serving the previous dist instead

if defined PREVIEW_NOOPEN (
  "%NODE%" "tools\serve.mjs" --no-open
) else (
  "%NODE%" "tools\serve.mjs"
)

echo.
pause
