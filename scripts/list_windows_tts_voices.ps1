$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $synth.GetInstalledVoices() | ForEach-Object {
        $info = $_.VoiceInfo
        [PSCustomObject]@{
            Name = $info.Name
            Culture = $info.Culture
            Gender = $info.Gender
            Age = $info.Age
        }
    } | Format-Table -AutoSize
} finally {
    $synth.Dispose()
}
