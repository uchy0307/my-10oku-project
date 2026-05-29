$ErrorActionPreference = 'Stop'
try {
    $pkg = Get-AppxPackage Claude
    if (-not $pkg) {
        Write-Output "NO_PACKAGE: Claude not installed"
        exit 2
    }
    $manifest = Join-Path $pkg.InstallLocation 'AppXManifest.xml'
    Write-Output ("Manifest: " + $manifest)
    Write-Output ("Exists: " + (Test-Path $manifest))
    Add-AppxPackage -DisableDevelopmentMode -Register $manifest
    Write-Output "RE-REGISTER OK"
} catch {
    Write-Output ("RE-REGISTER FAILED: " + $_.Exception.Message)
    exit 1
}
