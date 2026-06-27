# Installeer iperf3 als server op WINDOWSSERVER via Scheduled Task
# Uitvoeren als Administrator op WINDOWSSERVER (100.92.201.100)
# Vereiste: iperf3.exe op $Iperf3Path
# Download: https://github.com/ar51an/iperf3-win-builds/releases

param(
    [string]$Iperf3Path = "C:\tools\iperf3\iperf3.exe",
    [int]   $Port       = 5201
)

$taskName = "iperf3-server"

# Controleer/installeer iperf3
if (-not (Test-Path $Iperf3Path)) {
    Write-Host "iperf3.exe niet gevonden op $Iperf3Path"
    Write-Host "Probeer winget..."
    winget install --id "iperf3" --silent 2>$null
    if (-not (Test-Path $Iperf3Path)) {
        Write-Warning "Plaats iperf3.exe handmatig op $Iperf3Path en herstart dit script."
        Write-Warning "Download: https://github.com/ar51an/iperf3-win-builds/releases"
        exit 1
    }
}
Write-Host "✓ iperf3.exe aanwezig: $Iperf3Path"

# Firewall regel
$fwRule = Get-NetFirewallRule -DisplayName "iperf3 server" -ErrorAction SilentlyContinue
if (-not $fwRule) {
    New-NetFirewallRule -DisplayName "iperf3 server" -Direction Inbound `
        -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
    Write-Host "✓ Firewall regel aangemaakt (TCP $Port inbound)"
} else {
    Write-Host "✓ Firewall regel al aanwezig"
}

# Verwijder bestaande taak
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action    = New-ScheduledTaskAction -Execute $Iperf3Path -Argument "-s --port $Port"
$trigger   = New-ScheduledTaskTrigger -AtStartup
$settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 5 `
                 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable $true
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Description "iPerf3 server daemon poort $Port" `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null

Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 2

$task = Get-ScheduledTask -TaskName $taskName
Write-Host "✓ Scheduled Task '$taskName' aangemaakt (status: $($task.State))"
Write-Host ""
Write-Host "Test vanaf een andere host:"
Write-Host "  iperf3 -c 100.92.201.100 -t 5    (via Tailscale)"
