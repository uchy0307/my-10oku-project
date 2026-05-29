@echo off
chcp 65001 > nul
title full_recovery
setlocal EnableExtensions

cd /d "%~dp0.."
echo === 既投稿タイトル修復 + 重複歴史削除/再投稿 一気通貫 ===
echo.
echo 前提: OAuth scope (youtube.force-ssl) 拡張済の refresh_token が .env にある
echo       未確認なら先に scripts\_oauth_test.py で動作確認
echo.

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
)

rem ---- Step 1: tokens OK ?
echo --- Step 1: OAuth test ---
python scripts\_oauth_test.py
if !errorlevel! neq 0 (
  echo [FATAL] OAuth test failed. scope 拡張を完了してから再実行してください。
  exit /b 1
)
echo.

rem ---- Step 2: 既投稿 7 本のタイトル update (psych_007 + otona_shorts 010-017)
echo --- Step 2: タイトル update ^(--apply^) ---
python scripts\_update_video_titles.py --apply
echo.

rem ---- Step 3: 歴史 010/016 削除 + uploaded.json 修正
echo --- Step 3: 歴史 010/016 削除 ^(--apply^) ---
python scripts\_delete_videos.py --apply
echo.

rem ---- Step 4: 歴史 010/016 を新タイトルで再アップロード
echo --- Step 4: 歴史 2本再アップロード ---
node scripts\upload_quarantine.mjs --kind history --count 2
echo.

rem ---- Step 5: 公開確認 (oEmbed)
echo --- Step 5: 公開状態 oEmbed 確認 ---
python scripts\_verify_uploads_oembed.py
echo.

echo === 完了 ===
endlocal
