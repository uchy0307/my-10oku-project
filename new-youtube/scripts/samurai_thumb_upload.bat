@echo off
cd /d "%~dp0"
REM === credentials を環境変数に set (この行は user PC でのみ実体値に置換) ===
REM   note-auto\youtube_tokens.json から値をコピーして以下を埋める:
REM   set SAMURAI_YOUTUBE_CLIENT_ID=<ここに client_id>
REM   set SAMURAI_YOUTUBE_CLIENT_SECRET=<ここに client_secret>
REM   set SAMURAI_YOUTUBE_REFRESH_TOKEN=<ここに refresh_token>
REM
REM この .bat を git に commit する前に **secrets を直書きしないこと**。
REM secrets を直書きすると GitHub push protection / Secret Scanning が trigger され、
REM 漏洩リスクが生じる。
python samurai_thumb_upload.py
echo.
echo === log: samurai_thumb_upload.log ===
type samurai_thumb_upload.log
pause
