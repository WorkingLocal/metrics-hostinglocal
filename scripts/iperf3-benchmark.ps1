# iPerf3 bandbreedte benchmark naar FILESERVER (Windows variant)
# Schrijft Prometheus textfile metrics voor windows_exporter textfile_collector
# Uitvoeren via Task Scheduler (elk uur)
#
# Vereiste: iperf3.exe aanwezig in $Iperf3Path

param(
    [string]$Iperf3Target    = "192.168.111.30",
    [string]$Iperf3Path      = "C:\tools\iperf3\iperf3.exe",
    [string]$TextfileDir     = "C:\ProgramData\windows_exporter\textfile_collector",
    [int]   $Duration        = 10
)

$ErrorActionPreference = "SilentlyContinue"
$hostname = $env:COMPUTERNAME.ToLower()
$promFile = Join-Path $TextfileDir "iperf3_benchmark.prom"
$tmpFile  = "$promFile.tmp"
$timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

# Detecteer interface richting FILESERVER
$route = Get-NetRoute -AddressFamily IPv4 |
    Where-Object { $_.DestinationPrefix -eq "192.168.111.0/24" } |
    Sort-Object RouteMetric |
    Select-Object -First 1

$ifaceType = "unknown"
$ifaceName = "none"

if ($route) {
    $adapter = Get-NetAdapter -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue
    if ($adapter) {
        $ifaceName = $adapter.Name

        $isWifi = $adapter.InterfaceDescription -match "Wireless|Wi-Fi|WiFi|802\.11"
        if ($isWifi) {
            $ifaceType = "wifi"
        } else {
            switch -Regex ($adapter.LinkSpeed) {
                "10 Gbps"  { $ifaceType = "lan_10gbe" }
                "2\.5 Gbps" { $ifaceType = "lan_2_5gbe" }
                "1 Gbps"   { $ifaceType = "lan_1gbe" }
                "100 Mbps" { $ifaceType = "lan_100mbe" }
                default    { $ifaceType = "lan" }
            }
        }
    }
}

# Voer iperf3 test uit
$bps     = 0
$success = 0

if (Test-Path $Iperf3Path) {
    $jsonOutput = & $Iperf3Path -c $Iperf3Target -t $Duration -J 2>$null

    if ($LASTEXITCODE -eq 0 -and $jsonOutput) {
        try {
            $data = $jsonOutput | ConvertFrom-Json
            $bps = [int64]$data.end.sum_received.bits_per_second
            if ($bps -gt 0) { $success = 1 }
        } catch {
            $bps = 0
        }
    }
} else {
    Write-Warning "iperf3.exe niet gevonden op $Iperf3Path"
}

$labels = "hostname=`"$hostname`",interface=`"$ifaceName`",interface_type=`"$ifaceType`""

$content = @"
# HELP network_iperf3_to_fileserver_bits_per_second Gemeten bandbreedte naar FILESERVER (bits/sec)
# TYPE network_iperf3_to_fileserver_bits_per_second gauge
network_iperf3_to_fileserver_bits_per_second{$labels} $bps
# HELP network_iperf3_to_fileserver_success 1=test geslaagd, 0=gefaald
# TYPE network_iperf3_to_fileserver_success gauge
network_iperf3_to_fileserver_success{$labels} $success
# HELP network_iperf3_to_fileserver_last_run_timestamp Unix timestamp van laatste test
# TYPE network_iperf3_to_fileserver_last_run_timestamp gauge
network_iperf3_to_fileserver_last_run_timestamp{$labels} $timestamp
"@

New-Item -ItemType Directory -Force -Path $TextfileDir | Out-Null
$content | Out-File -FilePath $tmpFile -Encoding utf8 -NoNewline
Move-Item -Path $tmpFile -Destination $promFile -Force

$mbps = [int]($bps / 1000000)
Write-Host "[$hostname] iperf3 -> FILESERVER: $mbps Mbps via $ifaceName ($ifaceType)"
