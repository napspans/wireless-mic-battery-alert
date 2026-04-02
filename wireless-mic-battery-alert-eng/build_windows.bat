@echo off
setlocal

cd /d "%~dp0"

set "LOG_DIR=build\windows"
set "BUILD_LOG=%LOG_DIR%\build.txt"
set "DIST_DIR=dist\WirelessMicBatteryAlert"
set "EXE_PATH=%DIST_DIR%\WirelessMicBatteryAlert.exe"
set "ASSET_DIR=%DIST_DIR%\_internal\assets"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo === Step 35 Windows Build Start === > "%BUILD_LOG%"
echo Working Directory: %CD% >> "%BUILD_LOG%"
echo. >> "%BUILD_LOG%"

echo [1/4] Python version check
python --version >> "%BUILD_LOG%" 2>&1
if errorlevel 1 goto :fail

echo [2/4] Install dependencies from requirements.txt
python -m pip install -r requirements.txt >> "%BUILD_LOG%" 2>&1
if errorlevel 1 goto :fail

echo [3/4] Run PyInstaller on Windows
python -m PyInstaller --noconfirm --clean build.spec >> "%BUILD_LOG%" 2>&1
if errorlevel 1 goto :fail

echo [4/4] Verify build outputs
if not exist "%EXE_PATH%" (
    echo Missing EXE: %EXE_PATH% >> "%BUILD_LOG%"
    goto :fail
)
if not exist "%ASSET_DIR%\alert_chime.wav" (
    echo Missing asset: %ASSET_DIR%\alert_chime.wav >> "%BUILD_LOG%"
    goto :fail
)
if not exist "%ASSET_DIR%\alert_error.wav" (
    echo Missing asset: %ASSET_DIR%\alert_error.wav >> "%BUILD_LOG%"
    goto :fail
)
if not exist "%ASSET_DIR%\alert_marimba.wav" (
    echo Missing asset: %ASSET_DIR%\alert_marimba.wav >> "%BUILD_LOG%"
    goto :fail
)
if not exist "%ASSET_DIR%\notify_04.wav" (
    echo Missing asset: %ASSET_DIR%\notify_04.wav >> "%BUILD_LOG%"
    goto :fail
)
if not exist "%ASSET_DIR%\notify_11.wav" (
    echo Missing asset: %ASSET_DIR%\notify_11.wav >> "%BUILD_LOG%"
    goto :fail
)

echo. >> "%BUILD_LOG%"
echo EXE_PATH=%EXE_PATH% >> "%BUILD_LOG%"
echo ASSET_DIR=%ASSET_DIR% >> "%BUILD_LOG%"
echo RESULT=SUCCESS >> "%BUILD_LOG%"

echo Build completed successfully.
echo Log: %BUILD_LOG%
exit /b 0

:fail
echo RESULT=FAILED >> "%BUILD_LOG%"
echo Build failed. See %BUILD_LOG%
exit /b 1
