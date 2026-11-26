# Genera la narración con una voz de Windows (OneCore).
# Uso: powershell -ExecutionPolicy Bypass -File tts.ps1 -Lista lista.json -Voz "Raul"
# lista.json: [{ "id": "s01p01", "ssml": "<speak ...>...</speak>", "out": "C:\\...\\s01p01.wav" }, ...]
param(
    [Parameter(Mandatory = $true)][string]$Lista,
    [string]$Voz = "Raul"
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]
function Wait-Op($op, [Type]$type) {
    $task = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op))
    $null = $task.Wait(-1)
    return $task.Result
}

$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -like "*$Voz*" } | Select-Object -First 1
if (-not $voice) { throw "No encontré la voz '$Voz'." }
$synth.Voice = $voice

$items = Get-Content -Raw -Encoding UTF8 $Lista | ConvertFrom-Json
foreach ($it in $items) {
    $stream = Wait-Op ($synth.SynthesizeSsmlToStreamAsync($it.ssml)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
    $reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
    $size = [uint32]$stream.Size
    $null = Wait-Op ($reader.LoadAsync($size)) ([uint32])
    $bytes = New-Object byte[] $size
    $reader.ReadBytes($bytes)
    [IO.File]::WriteAllBytes($it.out, $bytes)
    $reader.Dispose(); $stream.Dispose()
    Write-Output ("ok " + $it.id)
}
