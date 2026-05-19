@echo off
REM ============================================================
REM  register_auto_git_sync.bat - Windows Task Scheduler に
REM    auto_git_sync.bat を 5 分おき実行で登録する（初回 1 回だけ実行）
REM
REM  使い方:
REM    このファイルを **管理者として実行** ダブルクリック
REM    または cmd を管理者で開いて C:\Users\user\Documents\10oku-project\
REM    で _register_auto_git_sync.bat を叩く
REM
REM  確認方法:
REM    schtasks /Query /TN ClaudeAutoGitSync
REM
REM  解除方法:
REM    schtasks /Delete /TN ClaudeAutoGitSync /F
REM
REM  ログ確認:
REM    type C:\Users\user\Documents\10oku-project\_auto_git_sync.log
REM ============================================================

set REPO=C:\Users\user\Documents\10oku-project
set SCRIPT=%REPO%\_auto_git_sync.bat
set TASK=ClaudeAutoGitSync

echo Registering task '%TASK%' to run %SCRIPT% every 5 minutes...

schtasks /Create /SC MINUTE /MO 5 /TN "%TASK%" /TR "\"%SCRIPT%\"" /F /RL LIMITED

if errorlevel 1 (
    echo.
    echo Registration FAILED.
    echo Try running this .bat AS ADMINISTRATOR.
    echo Or run manually:
    echo   schtasks /Create /SC MINUTE /MO 5 /TN "%TASK%" /TR "%SCRIPT%" /F
    pause
    exit /b 1
)

echo.
echo Task '%TASK%' registered. Verifying...
schtasks /Query /TN "%TASK%"
echo.
echo Done. The task will run every 5 minutes and auto git push.
echo Log will be written to: %REPO%\_auto_git_sync.log
echo.
echo To stop:   schtasks /Delete /TN "%TASK%" /F
echo To test now: schtasks /Run /TN "%TASK%"
pause
