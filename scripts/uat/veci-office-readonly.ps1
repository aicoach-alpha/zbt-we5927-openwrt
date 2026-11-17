#requires -Version 5.1
<#
VeCI WE5927 physical UAT collector on a Windows wired laptop.
READ ONLY: does not change router settings, interfaces, processes, drivers,
SIM, Wi-Fi, watchdog, firmware, or SSH host trust.
Remote commands are literals without shell pipes, redirects or command chains.
Wi-Fi beacon proof requires an independently verified SSID AND BSSID.
LAN ports without connected cables remain unverified, not failed.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$')]
    [string]$Router = '192.168.1.1',
    [ValidateRange(1,20)][int]$Samples = 3,
    [ValidateRange(10,300)][int]$IntervalSeconds = 30,
    [string]$ExpectedSSID = '',
    [string]$ExpectedBSSID = '',
    [string]$Output = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ([bool]$ExpectedSSID -xor [bool]$ExpectedBSSID) {
    throw 'ExpectedSSID and ExpectedBSSID must both be provided, or both omitted.'
}
if ($ExpectedBSSID -and $ExpectedBSSID -notmatch '^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$') {
    throw 'ExpectedBSSID must be a verified hardware MAC formatted as aa:bb:cc:dd:ee:ff.'
}
if (-not (Get-Command ssh.exe -ErrorAction SilentlyContinue)) {
    throw 'Windows OpenSSH ssh.exe is required.'
}
function Read-Router([string]$Command) {
    # These are fixed literals below; no user-supplied data enters remote shell.
    $result = & ssh.exe -T -o BatchMode=yes -o ConnectTimeout=8 -o ConnectionAttempts=1 -o StrictHostKeyChecking=yes "root@$Router" $Command 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return ($result -join [Environment]::NewLine)
}
function Read-RouterJson([string]$Command) {
    $raw = Read-Router $Command
    if (-not $raw) { return $null }
    try { return (ConvertFrom-Json -InputObject $raw -ErrorAction Stop) }
    catch { return $null }
}
function Find-SwitchPorts([string]$Raw) {
    $ports = @{}
    $current = -1
    foreach ($line in ($Raw -split '\r?\n')) {
        if ($line -match '^Port ([0-9]+):') {
            $current = [int]$Matches[1]
        } elseif ($current -ge 0 -and $line -match 'link: port:[0-9]+ link:(up|down)') {
            if ($current -le 4) {
                $ports["$current"] = $Matches[1]
            }
            $current = -1
        }
    }
    return $ports
}
function External-APSeen([string]$Name, [string]$Mac) {
    if (-not $Name -or -not $Mac) { return $null }
    $scan = & netsh.exe wlan show networks mode=bssid 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $scan) { return $null }
    $lookingAtSSID = $false
    $wanted = $Mac.ToLowerInvariant().Replace('-', ':')
    foreach ($line in $scan) {
        if ($line -match '^\s*SSID\s+[0-9]+\s*:\s*(.*)$') {
            $lookingAtSSID = ($Matches[1].Trim() -ceq $Name)
        } elseif ($lookingAtSSID -and $line -match '^\s*BSSID\s+[0-9]+\s*:\s*([0-9a-fA-F:-]+)\s*$') {
            if ($Matches[1].ToLowerInvariant().Replace('-', ':') -eq $wanted) { return $true }
        }
    }
    return $false
}
function New-Observation {
    $pidsText = Read-Router 'pidof netifd'
    $pids = @()
    if ($pidsText) { $pids = @($pidsText.Trim() -split '\s+' | Where-Object { $_ -match '^[0-9]+$' }) }
    $lte = Read-RouterJson "ubus -S -t 4 call network.interface.lte status '{}'"
    $wireless = Read-RouterJson "ubus -S -t 4 call network.wireless status '{}'"
    $ap = Read-RouterJson "ubus -S -t 4 call hostapd.phy0-ap0 get_status '{}'"
    $route = Read-Router 'ip -4 route show default dev usb0'
    $gatewayPing = Read-Router 'ping -I usb0 -c 2 -W 2 192.168.7.1'
    $internetPing = Read-Router 'ping -I usb0 -c 2 -W 2 1.1.1.1'
    $dns = Read-Router 'nslookup cloudflare.com'
    $switch = Read-Router 'swconfig dev switch0 show'
    $guardian = Read-Router 'cat /tmp/veci-wifi-performance.state'
    $ports = if ($switch) { Find-SwitchPorts $switch } else { @{} }
    $cablePorts = @($ports.Keys | Where-Object { $_ -in @('0','1','2','3') -and $ports[$_] -eq 'up' } | Sort-Object)
    $apState = $null
    if ($null -ne $wireless -and $null -ne $wireless.radio0) { $apState = ($wireless.radio0.up -eq $true) }
    $hostapdState = $null
    if ($null -ne $ap) { $hostapdState = ($ap.status -eq 'ENABLED') }
    $gatewayOkay = $null
    if ($gatewayPing) { $gatewayOkay = ($gatewayPing -match '2 packets received, 0% packet loss') }
    $internetOkay = $null
    if ($internetPing) { $internetOkay = ($internetPing -match '2 packets received, 0% packet loss') }
    $externalSeen = External-APSeen $ExpectedSSID $ExpectedBSSID
    return [pscustomobject]@{
        observed_utc = [DateTime]::UtcNow.ToString('o')
        netifd_instance_count = $pids.Count
        netifd_single = ($pids.Count -eq 1)
        lte_up = $(if ($lte) { [bool]$lte.up } else { $null })
        lte_usb0 = $(if ($lte) { ($lte.l3_device -eq 'usb0') } else { $null })
        lte_default_route = $(if ($route) { $route -match '^default via .* dev usb0' } else { $false })
        gateway_two_ping_pass = $gatewayOkay
        internet_two_ping_pass = $internetOkay
        dns_resolution_pass = $(if ($dns) { $dns -match 'Name:[ ]*cloudflare.com' } else { $null })
        wireless_control_plane_up = $apState
        hostapd_enabled = $hostapdState
        wifi_guardian_observe_only = $(if ($guardian) { $guardian -match 'auto_recover=0' } else { $null })
        external_verified_bssid_visible = $externalSeen
        lan_connected_port_count = $cablePorts.Count
        lan_connected_ports = $cablePorts
        ethernet_ports = $ports
        all_lan_ports_physical_tested = $false
        internet_pass = (($pids.Count -eq 1) -and $route -and $gatewayOkay -and $internetOkay)
        wifi_runtime_pass = (($apState -eq $true) -and ($hostapdState -eq $true))
        wifi_beacon_pass = $externalSeen
    }
}
if (-not $Output) {
    $Output = Join-Path $PSScriptRoot ("veci-office-uat-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".json")
}
if (Test-Path -LiteralPath $Output) { throw 'Refusing to overwrite existing UAT report.' }
$observations = @()
for ($i = 1; $i -le $Samples; $i++) {
    $item = New-Observation
    $observations += $item
    Write-Host ("Sample {0}/{1}: Router-LTE-uplink={2} Wi-Fi runtime={3} Wi-Fi beacon={4} netifd={5} connected LAN ports={6}" -f
        $i, $Samples, $item.internet_pass, $item.wifi_runtime_pass,
        $item.wifi_beacon_pass, $item.netifd_instance_count, $item.lan_connected_port_count)
    if ($i -lt $Samples) { Start-Sleep -Seconds $IntervalSeconds }
}
$report = [ordered]@{
    schema = 1
    scope = 'READ_ONLY_FIELD_OBSERVATION'
    router_configuration_modified = $false
    firmware_flash_authorized = $false
    independent_wifi_beacon_evidence = ([bool]$ExpectedSSID -and [bool]$ExpectedBSSID)
    # Router-originated ICMP does not prove NAT/forwarding from a LAN client.
    wired_client_internet_verified = $null
    wifi_client_internet_verified = $null
    all_lan_ports_physical_tested = $false
    all_samples_lte_pass = (@($observations | Where-Object { $_.internet_pass -ne $true }).Count -eq 0)
    all_samples_wifi_runtime_pass = (@($observations | Where-Object { $_.wifi_runtime_pass -ne $true }).Count -eq 0)
    all_samples_wifi_beacon_pass = $(if (-not $ExpectedBSSID) { $null } else { (@($observations | Where-Object { $_.wifi_beacon_pass -ne $true }).Count -eq 0) })
    observations = $observations
}
$json = $report | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText($Output, $json, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "SAVED_REPORT=$Output"
Write-Host 'NOTE: disconnected Ethernet ports cannot be certified without a physical cable test.'
Write-Host 'ROUTER_CHANGES=NONE'
