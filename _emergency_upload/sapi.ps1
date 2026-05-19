
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
# Try to find Japanese voice
$jp = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'ja*' } | Select-Object -First 1
if ($jp) { $synth.SelectVoice($jp.VoiceInfo.Name) }
$synth.Rate = -1
$synth.SetOutputToWaveFile("C:\Users\user\Documents\10oku-project\_emergency_upload\narration.wav")
$synth.Speak(@"
天正三年、五月二十一日。三河国、設楽原。織田信長、徳川家康の連合軍と、武田勝頼率いる精鋭騎馬軍団が、この地で対峙した。三千挺の鉄砲、三重に巡らされた馬防柵——。戦の常識を、ただ一日にして覆した合戦。長篠の戦い、その真実を、まもなくお届けする。
"@)
$synth.Dispose()
Write-Host "SAPI WAV written"
