param([string]$Out)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$img = [System.Windows.Forms.Clipboard]::GetImage()
if ($img) {
    $img.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output ('SAVED ' + $img.Width + 'x' + $img.Height + ' -> ' + $Out)
} else {
    Write-Output 'NO_IMAGE_IN_CLIPBOARD'
}
