[CmdletBinding()]
param([switch]$Inspect, [switch]$InstallShortcut)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
try {
    if (-not ('PaitGpuAdapters' -as [type])) { Add-Type -Path (Join-Path $PSScriptRoot 'GpuAdapters.cs') }
    $adapters = @([PaitGpuAdapters]::Read())
    $selected = $adapters | Sort-Object VideoMemory -Descending | Select-Object -First 1
    if (-not $selected) { throw 'No hardware graphics adapter was found.' }
    $chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe", "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $chrome) { throw 'Please install Google Chrome first.' }
    # Keep the previous dedicated profile, including login and microphone permissions.
    $profile = Join-Path $env:LOCALAPPDATA 'PetChatSystem\ChromeGpuDiagnostic'
    $url = 'http://127.0.0.1:5002/den'
    $browserArgs = @("--user-data-dir=`"$profile`"", '--no-first-run', '--no-default-browser-check', '--disable-background-mode', '--use-angle=d3d11', "--use-adapter-luid=$($selected.Luid)", '--force_high_performance_gpu', '--new-window', $url)
    if ($Inspect) {
        [pscustomobject]@{Selected=$selected; Adapters=$adapters; Chrome=$chrome; Profile=$profile; Arguments=$browserArgs} | ConvertTo-Json -Depth 5
        exit 0
    }
    New-Item -ItemType Directory -Path $profile -Force | Out-Null
    # Chrome reuses a running profile, ignoring new GPU arguments. Never kill user windows.
    $running = @(Get-CimInstance Win32_Process -Filter "name='chrome.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($profile) -and $_.CommandLine -notmatch '--type=' })
    foreach ($process in $running) {
        if ($process.CommandLine -notmatch ([regex]::Escape("--use-adapter-luid=$($selected.Luid)") + '(\s|$)')) {
            throw 'Please close the PetChat GPU browser window, then open this shortcut again. Ordinary Chrome windows can stay open.'
        }
    }
    $reg = 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences'
    if (-not (Test-Path -LiteralPath $reg)) { New-Item -Path $reg | Out-Null }
    $old = (Get-ItemProperty -Path $reg).PSObject.Properties[$chrome].Value
    $preference = if ($old -match 'GpuPreference=\d+;') { $old -replace 'GpuPreference=\d+;', 'GpuPreference=2;' } else { "$old" + 'GpuPreference=2;' }
    New-ItemProperty -Path $reg -Name $chrome -Value $preference -PropertyType String -Force | Out-Null
    if ($InstallShortcut) {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) '派特岛（自动独显）.lnk'))
        $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
        $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`""
        $shortcut.WorkingDirectory = $projectRoot
        $shortcut.IconLocation = "$chrome,0"
        $shortcut.Description = '自动识别当前高性能显卡，启动本地服务并打开派特岛'
        $shortcut.Save()
    }
    $ready = $false
    try { $ready = (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch {}
    if (-not $ready) {
        if (Get-NetTCPConnection -LocalPort 5002 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 5002 is occupied but the island is not responding. Please check the local service.' }
        $python = @((Join-Path $projectRoot '.venv\Scripts\python.exe'), (Join-Path $projectRoot 'venv\Scripts\python.exe'), (Join-Path $env:USERPROFILE '.conda\envs\qijin666\python.exe')) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (-not $python) { $python = (Get-Command python -ErrorAction Stop).Source }
        $logRoot = Join-Path $env:LOCALAPPDATA 'PetChatSystem'
        $service = Start-Process -FilePath $python -ArgumentList @('-X','utf8','-m','flask','--app','run:app','run','--host','127.0.0.1','--port','5002','--no-debugger','--no-reload') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot 'service.out.log') -RedirectStandardError (Join-Path $logRoot 'service.err.log') -PassThru
        for ($attempt=0; $attempt -lt 40; $attempt++) {
            try { $ready = (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch {}
            if ($ready -or $service.HasExited) { break }
            Start-Sleep -Milliseconds 500
        }
        if (-not $ready) { throw "Local service did not start. See $logRoot\service.err.log" }
    }
    [pscustomobject]@{Time=(Get-Date).ToString('o'); Adapter=$selected; Profile=$profile; Url=$url} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $env:LOCALAPPDATA 'PetChatSystem\last-gpu-launch.json') -Encoding UTF8
    $focused = $false
    if ($running.Count -gt 0) {
        $windowShell = New-Object -ComObject WScript.Shell
        $focused = $windowShell.AppActivate([int]$running[0].ProcessId)
    }
    if (-not $focused) { Start-Process -FilePath $chrome -ArgumentList $browserArgs -WindowStyle Hidden | Out-Null }
    Write-Output "Opened island with adapter: $($selected.Name) ($($selected.Luid))"
} catch {
    if ($Inspect) { Write-Error $_; exit 1 }
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Pet Island startup') | Out-Null
    exit 1
}
