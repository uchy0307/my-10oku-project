@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo === ボタンサーバー 常駐登録 ===
echo 管理者権限で実行してください
echo.

cd /d "%~dp0.."
set SCRIPT=%CD%\scripts\local_button_server.py
set TASK=UchyButtonServer

echo スクリプト: %SCRIPT%
echo.

REM pythonw.exe を検索（ウィンドウなし版）
set PYTHONW=
for /f "usebackq delims=" %%i in (`where pythonw.exe 2^>nul`) do (
    if "!PYTHONW!"=="" set PYTHONW=%%i
)

REM 見つからなければ python.exe の隣を見る
if "!PYTHONW!"=="" (
    for /f "usebackq delims=" %%i in (`where python.exe 2^>nul`) do (
        if "!PYTHONW!"=="" (
            set PYDIR=%%~dpi
            if exist "!PYDIR!pythonw.exe" set PYTHONW=!PYDIR!pythonw.exe
        )
    )
)

REM それでもなければ python.exe で代用（ウィンドウは出るが動く）
if "!PYTHONW!"=="" (
    for /f "usebackq delims=" %%i in (`where python.exe 2^>nul`) do (
        if "!PYTHONW!"=="" set PYTHONW=%%i
    )
)

if "!PYTHONW!"=="" (
    echo [ERROR] Python が見つかりません
    pause & exit /b 1
)
echo 使用Python: !PYTHONW!
echo.

REM タスク登録（既存は上書き）
schtasks /Delete /TN "%TASK%" /F >nul 2>&1
schtasks /Create /TN "%TASK%" /TR "\"!PYTHONW!\" \"%SCRIPT%\"" /SC ONLOGON /DELAY 0000:10 /RL HIGHEST /F

if errorlevel 1 (
    echo [ERROR] タスク登録失敗
    echo 右クリック → 管理者として実行 してください
    pause & exit /b 1
)

echo.
echo [OK] タスク "%TASK%" 登録完了
echo      次回ログイン時に自動起動されます（ウィンドウなし）
echo.

REM 今すぐ起動
echo === 今すぐ起動 ===
start "" "!PYTHONW!" "%SCRIPT%"
echo [OK] 起動コマンド送信済み
echo.
echo 数秒後に http://localhost:7373 または https://pc.uchy0307.uk で確認
pause
endlocal
