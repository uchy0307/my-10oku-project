# scripts/setup_otona_token.ps1
# Get refresh token for @Otona_Psychology YouTube channel via loopback OAuth.
# Uses TcpListener (no URL ACL needed).

$ErrorActionPreference = 'Stop'
$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$envFile = Join-Path $ROOT '.env'

# Read client id / secret from .env
$cid = $null; $csec = $null
foreach ($line in Get-Content $envFile -Encoding UTF8) {
    if ($line -match '^YOUTUBE_CLIENT_ID=(.+)$')     { $cid  = $matches[1].Trim() }
    if ($line -match '^YOUTUBE_CLIENT_SECRET=(.+)$') { $csec = $matches[1].Trim() }
}
if (-not $cid -or -not $csec) {
    Write-Host "YOUTUBE_CLIENT_ID / _SECRET not in .env. Abort." -ForegroundColor Red
    exit 1
}

# Find a free local port via TcpListener
function Get-FreePort {
    foreach ($p in 8765, 8766, 8767, 8768, 53210, 53211, 53212, 53213) {
        $tl = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $p)
        try {
            $tl.Start()
            $tl.Stop()
            return $p
        } catch {}
    }
    return $null
}
$port = Get-FreePort
if (-not $port) {
    Write-Host "No free port found among candidates." -ForegroundColor Red
    exit 1
}
$redirect = "http://127.0.0.1:$port/"
Write-Host "Using redirect: $redirect" -ForegroundColor Gray

# Build auth URL
Add-Type -AssemblyName System.Web
$scope = [System.Web.HttpUtility]::UrlEncode("https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube")
$ru = [System.Web.HttpUtility]::UrlEncode($redirect)
$cidEnc = [System.Web.HttpUtility]::UrlEncode($cid)
$authUrl = "https://accounts.google.com/o/oauth2/v2/auth?client_id=$cidEnc&redirect_uri=$ru&response_type=code&scope=$scope&access_type=offline&prompt=consent"

Write-Host ""
Write-Host "=== OTONA YouTube channel OAuth ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Browser will open Google login" -ForegroundColor Yellow
Write-Host "2. PICK the account that owns @Otona_Psychology" -ForegroundColor Yellow
Write-Host "3. If channel chooser appears: PICK @Otona_Psychology (NOT the samurai one)" -ForegroundColor Red
Write-Host "4. Click 'Allow'"
Write-Host ""
Write-Host "If you get 'redirect_uri_mismatch':" -ForegroundColor Gray
Write-Host "  Open https://console.cloud.google.com/apis/credentials" -ForegroundColor Gray
Write-Host "  Edit OAuth client -> add '$redirect' to allowed redirect URIs" -ForegroundColor Gray
Write-Host ""

# Start TCP listener
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
$listener.Start()
Write-Host "Listening on $redirect ..." -ForegroundColor Gray

Start-Process $authUrl

# Accept one connection, parse HTTP request line
$client = $listener.AcceptTcpClient()
$stream = $client.GetStream()
$reader = [System.IO.StreamReader]::new($stream)
$firstLine = $reader.ReadLine()  # e.g. GET /?code=XXX&scope=... HTTP/1.1
$listener.Stop()

# Extract query string
$code = $null; $err = $null
if ($firstLine -match 'GET\s+(\S+)\s+HTTP') {
    $path = $matches[1]
    if ($path -match '[?&]code=([^&\s]+)') { $code = [System.Web.HttpUtility]::UrlDecode($matches[1]) }
    if ($path -match '[?&]error=([^&\s]+)') { $err = [System.Web.HttpUtility]::UrlDecode($matches[1]) }
}

# Send response
$bodyHtml = if ($code) {
    "<html><body style='font-family:sans-serif;padding:40px;background:#fef3c7;'><h1>OK</h1><p>Token captured. You can close this tab.</p></body></html>"
} else {
    "<html><body style='font-family:sans-serif;padding:40px;background:#fee2e2;'><h1>ERROR: $err</h1></body></html>"
}
$bytes = [System.Text.Encoding]::UTF8.GetBytes($bodyHtml)
$resp = "HTTP/1.1 200 OK`r`nContent-Type: text/html; charset=utf-8`r`nContent-Length: $($bytes.Length)`r`nConnection: close`r`n`r`n"
$writer = [System.IO.StreamWriter]::new($stream)
$writer.Write($resp)
$writer.Flush()
$stream.Write($bytes, 0, $bytes.Length)
$stream.Flush()
$client.Close()

if (-not $code) {
    Write-Host "OAuth failed: $err" -ForegroundColor Red
    exit 1
}

Write-Host "Code captured. Exchanging for refresh_token..." -ForegroundColor Cyan

# Exchange code for tokens
$body = @{
    code          = $code
    client_id     = $cid
    client_secret = $csec
    redirect_uri  = $redirect
    grant_type    = "authorization_code"
}
try {
    $tok = Invoke-RestMethod -Uri "https://oauth2.googleapis.com/token" -Method POST -Body $body
} catch {
    Write-Host "Token exchange ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host $_.ErrorDetails.Message
    exit 1
}

if (-not $tok.refresh_token) {
    Write-Host "No refresh_token in response. Response:" -ForegroundColor Red
    $tok | ConvertTo-Json
    exit 1
}

# Verify which channel
$headers = @{ Authorization = "Bearer $($tok.access_token)" }
try {
    $ch = Invoke-RestMethod -Uri "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true" -Headers $headers
    $chName = $ch.items[0].snippet.title
    Write-Host "Authorized channel: $chName" -ForegroundColor Green
    if ($chName -match "Samurai|侍|Japanese\.Samurai") {
        Write-Host "WARNING: Looks like HISTORY channel, not @Otona_Psychology!" -ForegroundColor Red
        Write-Host "Save anyway? (y/N): " -NoNewline -ForegroundColor Yellow
        $ans = Read-Host
        if ($ans -ne 'y') {
            Write-Host "Aborted." -ForegroundColor Red
            exit 1
        }
    }
} catch {
    Write-Host "Could not verify channel name (saving anyway): $($_.Exception.Message)" -ForegroundColor Yellow
}

# Save to .env (remove old line first)
$existing = Get-Content $envFile -Encoding UTF8
$filtered = $existing | Where-Object { $_ -notmatch '^OTONA_YOUTUBE_REFRESH_TOKEN=' }
$filtered + "OTONA_YOUTUBE_REFRESH_TOKEN=$($tok.refresh_token)" | Set-Content -Path $envFile -Encoding UTF8

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Green
Write-Host "OTONA_YOUTUBE_REFRESH_TOKEN saved to .env" -ForegroundColor Green
Write-Host "From now on, 大人 / 大人ショート uploads run autonomously." -ForegroundColor Green
