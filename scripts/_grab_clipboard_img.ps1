Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$img = [System.Windows.Forms.Clipboard]::GetImage()
if ($img) {
    $p = 'C:\Users\user\Documents\10oku-project\assets\hp_landing\_grid.png'
    $img.Save($p, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output ('SAVED ' + $img.Width + 'x' + $img.Height + ' -> ' + $p)
} else {
    Write-Output 'NO_IMAGE_IN_CLIPBOARD'
}
