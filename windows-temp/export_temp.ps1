# LibreHardwareMonitor Prometheus textfile exporter
# Bevraagt de LHM webserver (http://localhost:8085/data.json).
# Xeon Silver 4114 CPU-temperaturen niet beschikbaar (WinRing0 MSR beperking Skylake-SP).
# Beschikbare sensoren: GPU Core/Hot Spot, alle NVMe- en SATA-schijven.
# Scheduled Task: LHM-TempExporter - elke 5 minuten, als SYSTEM

$LHM_URL  = "http://localhost:8085/data.json"
$OUT_FILE = "C:\Program Files\windows_exporter\textfile_inputs\hardware_temp.prom"
$TMP_FILE = "$OUT_FILE.tmp"

function Sanitize($s) {
    return ($s -replace '[^a-zA-Z0-9_]', '_').Trim('_')
}

function Parse-Value($raw) {
    # "55,0 °C" eindigt op C; extraheer het getal
    if ($raw -like '*C' -and $raw -match '(\d+[,\.]\d+)') {
        return ($Matches[1] -replace ',', '.')
    }
    return $null
}

$script:hwCount = @{}

function Walk-Node($node, $depth, $hwLabel, [ref]$results) {
    $text     = $node.Text
    $value    = $node.Value
    $children = $node.Children

    if ($depth -eq 2) {
        # Nieuw hardware-device: label eenmalig toewijzen voor alle sensors hieronder
        $key = Sanitize $text
        if (-not $script:hwCount.ContainsKey($key)) { $script:hwCount[$key] = 0 }
        $idx = $script:hwCount[$key]
        $hwLabel = if ($idx -eq 0) { $key } else { "${key}_${idx}" }
        $script:hwCount[$key]++
    }

    $celsius = Parse-Value $value
    if ($null -ne $celsius -and $depth -eq 4) {
        $sen = Sanitize $text
        $results.Value.Add([PSCustomObject]@{ hardware = $hwLabel; sensor = $sen; value = $celsius })
    }

    foreach ($child in $children) {
        Walk-Node $child ($depth + 1) $hwLabel $results
    }
}

try {
    $resp = Invoke-WebRequest -Uri $LHM_URL -UseBasicParsing -TimeoutSec 5
    $json = $resp.Content | ConvertFrom-Json
} catch {
    Write-Warning "Kan LHM webserver niet bereiken: $_"
    exit 1
}

$results = [System.Collections.Generic.List[PSCustomObject]]::new()
$ref     = [ref]$results
foreach ($child in $json.Children) {
    Walk-Node $child 1 "" $ref  # root zelf is depth 0, children starten op 1
}

$lines = @(
    "# HELP windows_hardware_temperature_celsius Hardware temperature in Celsius (LibreHardwareMonitor)",
    "# TYPE windows_hardware_temperature_celsius gauge"
)
foreach ($r in $results) {
    $lines += "windows_hardware_temperature_celsius{hardware=""$($r.hardware)"",sensor=""$($r.sensor)""} $($r.value)"
}

$lines | Out-File -FilePath $TMP_FILE -Encoding ascii -Force
Move-Item -Path $TMP_FILE -Destination $OUT_FILE -Force
Write-Host "OK - $($results.Count) temperatuursensoren naar $OUT_FILE"
