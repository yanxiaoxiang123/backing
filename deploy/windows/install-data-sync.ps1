param(
    [string]$Python = 'D:\anaconda3\envs\backing\python.exe',
    [string]$At = '17:00'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$backendRoot = Join-Path $repoRoot 'backend'
$pythonPath = (Resolve-Path -LiteralPath $Python).Path
$scriptPath = Join-Path $backendRoot 'data_sync_cli.py'
$reportPath = Join-Path $backendRoot 'data\sync\daily-report.json'
$arguments = '"{0}" --all --days 730 --report-file "{1}"' -f $scriptPath, $reportPath
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $arguments -WorkingDirectory $backendRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 8)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'Backing-MarketDataSync' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Versioned raw A-share history and verified calendar refresh' -Force
