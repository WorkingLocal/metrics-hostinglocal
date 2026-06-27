# iPerf3 multi-target bandbreedte benchmark (Windows)
# Schrijft Prometheus textfile metrics voor windows_exporter textfile_collector
# Uitvoeren via Task Scheduler (elk uur)

param(
    [string]$Iperf3Path  = "C:\tools\iperf3\iperf3.exe",
    [string]$TextfileDir = "C:\ProgramData\windows_exporter\textfile_collector",
    [int]   $Duration    = 10
)

$ErrorActionPreference = "SilentlyContinue"
$hostname  = $env:COMPUTERNAME.ToLower()
$promFile  = Join-Path $TextfileDir "iperf3_benchmark.prom"
$tmpFile   = "$promFile.tmp"
$timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

# Targets: niet naar zichzelf testen
$Targets = @(
    @{ Ip = "192.168.111.30"; Name = "fileserver"     },
    @{ Ip = "100.119.137.54"; Name = "networkserver"  }
)

function Get-IfaceInfo {
    param([string]$DestIp)
    $subnet = $DestIp.Substring(0, $DestIp.LastIndexOf('.'))
    $route  = Get-NetRoute -AddressFamily IPv4 |
              Where-Object { $_.DestinationPrefix -like "$subnet.*" } |
              Sort-Object RouteMetric | Select-Object -First 1
    if (-not $route) {
        $route = Get-NetRoute -AddressFamily IPv4 -DestinationPrefix "0.0.0.0/0" |
                 Sort-Object RouteMetric | Select-Object -First 1
    }
    $name = "none"; $type = "unknown"
    if ($route) {
        $adapter = Get-NetAdapter -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue
        if ($adapter) {
            $name = $adapter.Name
            $type = if ($adapter.InterfaceDescription -match "Wireless|Wi-Fi|WiFi|802\.11") {
                "wifi"
            } else {
                switch -Regex ($adapter.LinkSpeed) {
                    "10 Gbps"    { "lan_10gbe"  }
                    "2\.5 Gbps"  { "lan_2_5gbe" }
                    "1 Gbps"     { "lan_1gbe"   }
                    "100 Mbps"   { "lan_100mbe" }
                    default      { "lan"         }
                }
            }
        }
    }
    return @{ Name = $name; Type = $type }
}

New-Item -ItemType Directory -Force -Path $TextfileDir | Out-Null

$lines = @(
    "# HELP network_iperf3_bits_per_second Gemeten bandbreedte naar target (bits/sec)",
    "# TYPE network_iperf3_bits_per_second gauge",
    "# HELP network_iperf3_success 1=test geslaagd, 0=gefaald",
    "# TYPE network_iperf3_success gauge",
    "# HELP network_iperf3_last_run_timestamp Unix timestamp van laatste test",
    "# TYPE network_iperf3_last_run_timestamp gauge"
)

foreach ($target in $Targets) {
    $iface   = Get-IfaceInfo -DestIp $target.Ip
    $bps     = 0
    $success = 0

    if (Test-Path $Iperf3Path) {
        $json = & $Iperf3Path -c $target.Ip -t $Duration -J 2>$null
        if ($LASTEXITCODE -eq 0 -and $json) {
            try {
                $data = $json | ConvertFrom-Json
                $bps  = [int64]$data.end.sum_received.bits_per_second
                if ($bps -gt 0) { $success = 1 }
            } catch { $bps = 0 }
        }
    } else {
        Write-Warning "iperf3.exe niet gevonden op $Iperf3Path"
    }

    $labels  = "hostname=`"$hostname`",target=`"$($target.Name)`",interface=`"$($iface.Name)`",interface_type=`"$($iface.Type)`""
    $lines  += "network_iperf3_bits_per_second{$labels} $bps"
    $lines  += "network_iperf3_success{$labels} $success"
    $lines  += "network_iperf3_last_run_timestamp{$labels} $timestamp"

    $mbps = [int]($bps / 1000000)
    Write-Host "[$hostname] iperf3 -> $($target.Name) ($($target.Ip)): $mbps Mbps via $($iface.Name) ($($iface.Type))"
}

$lines -join "`n" | Out-File -FilePath $tmpFile -Encoding utf8 -NoNewline
Move-Item -Path $tmpFile -Destination $promFile -Force
