# Activeer thermalzone collector in windows_exporter
# Uitvoeren als Administrator op WINDOWSSERVER2025
# Gebruik: .\setup.ps1

$ErrorActionPreference = "Stop"

# Huidige windows_exporter service configuratie opzoeken
$svc = Get-Service -Name "windows_exporter" -ErrorAction SilentlyContinue
if (-not $svc) {
    Write-Error "windows_exporter service niet gevonden. Is windows_exporter geïnstalleerd?"
    exit 1
}

$imagePath = (Get-WmiObject Win32_Service -Filter "Name='windows_exporter'").PathName
Write-Host "Huidige service path: $imagePath"

# Bestaande collectors uit service path halen
if ($imagePath -match '--collectors\.enabled\s+"?([^"]+)"?') {
    $currentCollectors = $Matches[1]
} else {
    # Default collectors als er geen --collectors.enabled vlag is
    $currentCollectors = "cpu,cs,logical_disk,memory,net,os,process,service,system"
}

Write-Host "Huidige collectors: $currentCollectors"

# thermalzone toevoegen als nog niet aanwezig
if ($currentCollectors -notmatch "thermalzone") {
    $newCollectors = "$currentCollectors,thermalzone"
} else {
    $newCollectors = $currentCollectors
    Write-Host "thermalzone is al geconfigureerd."
}

Write-Host "Nieuwe collectors: $newCollectors"

# Service stoppen
Stop-Service -Name "windows_exporter" -Force
Write-Host "Service gestopt."

# windows_exporter binary path (zonder argumenten)
$exePath = ($imagePath -split ' --')[0].Trim('"')

# Service registratie updaten via sc.exe
$newBinPath = "`"$exePath`" --collectors.enabled `"$newCollectors`" --telemetry.addr 0.0.0.0:9182"
& sc.exe config windows_exporter binPath= $newBinPath

# Service starten
Start-Service -Name "windows_exporter"
Write-Host "Service herstart."

# Verificatie
Start-Sleep -Seconds 3
$metrics = Invoke-WebRequest -Uri "http://localhost:9182/metrics" -UseBasicParsing -ErrorAction SilentlyContinue
if ($metrics -and $metrics.Content -match "windows_thermalzone") {
    Write-Host "OK: thermalzone metrics beschikbaar"
    $metrics.Content -split "`n" | Select-String "windows_thermalzone_temperature_kelvin" | Select-Object -First 5
} else {
    Write-Warning "Geen thermalzone metrics gevonden — hardware ondersteunt mogelijk geen WMI thermalzone data"
    Write-Warning "Controleer via: Invoke-WebRequest http://localhost:9182/metrics | Select-String thermalzone"
}
