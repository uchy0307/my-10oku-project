# scripts/add_lp_dns.ps1
# Add CNAME lp.uchy0307.uk -> samurai-lab.pages.dev via Cloudflare API
#
# How to use:
#   1. Open https://dash.cloudflare.com/profile/api-tokens (script will open it)
#   2. Create token: Zone -> DNS -> Edit, zone uchy0307.uk
#   3. COPY the token (Ctrl+C on the displayed string)
#   4. Run: & C:\Users\user\Documents\10oku-project\scripts\add_lp_dns.ps1
#      (script reads from clipboard automatically)

$ErrorActionPreference = 'Stop'
$ROOT = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$envFile = Join-Path $ROOT '.env'

# 1. Try .env first
$token = $null
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile -Encoding UTF8) {
        if ($line -match '^CLOUDFLARE_API_TOKEN=(.+)$') {
            $token = $matches[1].Trim()
            break
        }
    }
}

# 2. Try clipboard
if (-not $token) {
    Write-Host ""
    Write-Host "=== No token in .env, reading from clipboard ===" -ForegroundColor Yellow
    try {
        $clip = (Get-Clipboard -Raw).Trim()
    } catch {
        $clip = ""
    }
    if ($clip -match '^[A-Za-z0-9_\-\.]{30,}$') {
        $token = $clip
        Write-Host "OK: found token-like string in clipboard ($($token.Length) chars)" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "Clipboard does not contain a valid token." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Steps:" -ForegroundColor Cyan
        Write-Host "  1. Browser will open Cloudflare API tokens page"
        Write-Host "  2. Click 'Create Token' -> 'Create Custom Token' -> 'Get started'"
        Write-Host "  3. Token name: claude-dns-edit"
        Write-Host "  4. Permission: Zone -> DNS -> Edit"
        Write-Host "  5. Zone Resources: Include -> Specific zone -> uchy0307.uk"
        Write-Host "  6. Continue to summary -> Create Token"
        Write-Host "  7. COPY the displayed token (Ctrl+C)"
        Write-Host "  8. Run this script again: & scripts\add_lp_dns.ps1"
        Write-Host ""
        Start-Process "https://dash.cloudflare.com/profile/api-tokens"
        exit 0
    }
}

# 3. Verify
$zone = '284f4d15fedcf4f390d26f8d446c70cd'
$headers = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }
Write-Host ""
Write-Host "=== Verify token ===" -ForegroundColor Cyan
try {
    $verify = Invoke-RestMethod -Uri "https://api.cloudflare.com/client/v4/user/tokens/verify" -Headers $headers -Method GET
    if (-not $verify.success) {
        Write-Host "Invalid token." -ForegroundColor Red
        exit 1
    }
    Write-Host "OK: status=$($verify.result.status)" -ForegroundColor Green
} catch {
    Write-Host "Verify error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host $_.ErrorDetails.Message
    exit 1
}

# 4. Save to .env if not already there
$envHas = $false
if (Test-Path $envFile) {
    if ((Get-Content $envFile -Encoding UTF8 -Raw) -match 'CLOUDFLARE_API_TOKEN=') {
        $envHas = $true
    }
}
if (-not $envHas) {
    Add-Content -Path $envFile -Value "CLOUDFLARE_API_TOKEN=$token" -Encoding UTF8
    Write-Host "Token saved to .env" -ForegroundColor Green
}

# 5. Check existing record
Write-Host ""
Write-Host "=== Check existing lp record ===" -ForegroundColor Cyan
$existing = Invoke-RestMethod -Uri "https://api.cloudflare.com/client/v4/zones/$zone/dns_records?name=lp.uchy0307.uk" -Headers $headers -Method GET
if ($existing.result.Count -gt 0) {
    Write-Host "Already exists -> deleting first:" -ForegroundColor Yellow
    foreach ($r in $existing.result) {
        Invoke-RestMethod -Uri "https://api.cloudflare.com/client/v4/zones/$zone/dns_records/$($r.id)" -Headers $headers -Method DELETE | Out-Null
        Write-Host "  removed: $($r.type) $($r.name) -> $($r.content)" -ForegroundColor Gray
    }
}

# 6. Add CNAME
Write-Host ""
Write-Host "=== Add CNAME lp -> samurai-lab.pages.dev ===" -ForegroundColor Cyan
$body = @{
    type    = "CNAME"
    name    = "lp"
    content = "samurai-lab.pages.dev"
    proxied = $true
    ttl     = 1
    comment = "samurai-lab Pages (claude auto)"
} | ConvertTo-Json
$add = Invoke-RestMethod -Uri "https://api.cloudflare.com/client/v4/zones/$zone/dns_records" -Headers $headers -Method POST -Body $body
if ($add.success) {
    Write-Host "OK: lp.uchy0307.uk -> samurai-lab.pages.dev (proxied)" -ForegroundColor Green
} else {
    Write-Host "FAILED:" -ForegroundColor Red
    $add.errors | ConvertTo-Json
    exit 1
}

Write-Host ""
Write-Host "=== DONE. https://lp.uchy0307.uk will work in 2-5 minutes ===" -ForegroundColor Green
