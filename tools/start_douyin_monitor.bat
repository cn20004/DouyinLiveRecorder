@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0.."
set "RUNTIME=%ROOT%\runtime"
set "DYHUB=%RUNTIME%\dyhub"
set "DYHUB_COMMIT=ad31eeaae91842a4fffc6c2415026e2bbf524126"

echo ================================================
echo   郑老师魔改版 - 抖音评论/在线人数采集服务
echo ================================================

where git >nul 2>nul || (
  echo [错误] 未找到 Git，请先安装 Git for Windows。
  pause
  exit /b 1
)
where node >nul 2>nul || (
  echo [错误] 未找到 Node.js，需要 Node.js 20 或更高版本。
  pause
  exit /b 1
)
where npm >nul 2>nul || (
  echo [错误] 未找到 npm。
  pause
  exit /b 1
)

if not exist "%RUNTIME%" mkdir "%RUNTIME%"

if not exist "%DYHUB%\.git" (
  echo [1/4] 首次安装 DyHub...
  git clone https://github.com/ymstar/dyhub.git "%DYHUB%"
  if errorlevel 1 goto :failed
)

cd /d "%DYHUB%"
echo [2/4] 固定到已验证版本 %DYHUB_COMMIT%...
git fetch --all --tags
git checkout %DYHUB_COMMIT%
if errorlevel 1 goto :failed

if not exist "%DYHUB%\node_modules" (
  echo [3/4] 安装依赖...
  call npm ci
  if errorlevel 1 goto :failed
) else (
  echo [3/4] 依赖已存在，跳过安装。
)

echo [4/4] 构建并启动...
call npm run build
if errorlevel 1 goto :failed

set "DYHUB_COLLECTOR=browser"
set "DYHUB_PORT=8757"
echo.
echo 采集服务地址: http://127.0.0.1:8757
echo 保持本窗口运行即可。DouyinLiveRecorder 会自动接入。
echo.
call npm start
goto :eof

:failed
echo.
echo [失败] 弹幕采集服务启动失败，请查看上面的错误信息。
pause
exit /b 1
