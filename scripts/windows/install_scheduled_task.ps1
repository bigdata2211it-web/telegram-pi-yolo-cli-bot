$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$TaskName = "telegram-pi-yolo-cli-bot"
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }

$Action = New-ScheduledTaskAction `
    -Execute $PythonBin `
    -Argument "`"$RootDir\bot.py`"" `
    -WorkingDirectory $RootDir

$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Telegram bridge for PI high-autonomy run" `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Get-ScheduledTask -TaskName $TaskName
