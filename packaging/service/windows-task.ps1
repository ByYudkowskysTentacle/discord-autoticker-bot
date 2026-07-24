<#
.SYNOPSIS
    Registers (or removes) a Windows scheduled task that keeps the bot running.

.DESCRIPTION
    Windows has no built-in service manager that can supervise a plain
    executable: a real service must answer the Service Control Manager, which a
    packaged Python program does not, so `sc create` would have Windows kill it
    as unresponsive. Task Scheduler is the supported way to do this without
    installing extra software.

    The task starts the bot at log on, restarts it up to 3 times if it stops,
    and has no execution time limit — Task Scheduler otherwise stops tasks
    after 3 days, which would silently kill a long-running bot.

.EXAMPLE
    .\windows-task.ps1
    Registers the task using autoticker-bot*.exe found in the current folder.

.EXAMPLE
    .\windows-task.ps1 -ExePath "C:\bots\autoticker-bot.exe"

.EXAMPLE
    .\windows-task.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [string]$ExePath,
    [string]$TaskName = "AutoTickerBot",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'."
    return
}

# Default to an autoticker-bot executable sitting next to this script.
if (-not $ExePath) {
    $candidate = Get-ChildItem -Path $PSScriptRoot -Filter "autoticker-bot*.exe" |
        Select-Object -First 1
    if (-not $candidate) {
        throw "No autoticker-bot*.exe found in $PSScriptRoot. Pass -ExePath instead."
    }
    $ExePath = $candidate.FullName
}

$ExePath = (Resolve-Path -LiteralPath $ExePath).Path
if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Executable not found: $ExePath"
}

$workDir = Split-Path -Parent $ExePath
$logPath = Join-Path $workDir "autoticker-bot.log"

$action = New-ScheduledTaskAction -Execute $ExePath `
    -Argument "--log-file `"$logPath`"" `
    -WorkingDirectory $workDir

$trigger = New-ScheduledTaskTrigger -AtLogOn

# ExecutionTimeLimit of zero means "run indefinitely"; the default would stop
# the bot after 3 days. RestartCount/RestartInterval supply the crash recovery.
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Discord auto-ticker bot (https://github.com/ByYudkowskysTentacle/discord-autoticker-bot)" `
    -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName'."
Write-Host "  Executable: $ExePath"
Write-Host "  Log file:   $logPath"
Write-Host ""
Write-Host "Start it now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Check it:      Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "Remove it:     .\windows-task.ps1 -Uninstall"
