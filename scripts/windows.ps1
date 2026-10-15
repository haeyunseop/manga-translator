# Native Windows helper. Not executed on the Linux development machine.
param([ValidateSet('setup','start','phone','update')][string]$Action='start')
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python=Join-Path $Root '.venv\Scripts\python.exe'
function Check-Exit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed (exit $LASTEXITCODE)." }
}
function Refresh-Path {
    $env:Path=[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')
    $Tesseract=Join-Path $env:ProgramFiles 'Tesseract-OCR'
    if (Test-Path (Join-Path $Tesseract 'tesseract.exe')) { $env:Path += ';'+$Tesseract }
    $Tailscale=Join-Path $env:ProgramFiles 'Tailscale'
    if (Test-Path (Join-Path $Tailscale 'tailscale.exe')) { $env:Path += ';'+$Tailscale }
}
function Need-Tool([string]$Command,[string]$Package) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw 'Windows App Installer (winget) is required. Install it from Microsoft Store, then reopen this helper.'
        }
        & winget install --exact --id $Package --source winget --accept-source-agreements --accept-package-agreements
        Check-Exit "Install $Package"
        Refresh-Path
    }
}
function Assert-PortsFree {
    foreach ($Port in @(3000,8000)) {
        if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
            throw 'MangaTrans ports are already in use. Stop its running window with Ctrl+C before updating or starting again.'
        }
    }
}
function Need-VCRuntime {
    if (-not (Test-Path (Join-Path $env:WINDIR 'System32\vcruntime140.dll'))) {
        & winget install --exact --id 'Microsoft.VCRedist.2015+.x64' --source winget --accept-source-agreements --accept-package-agreements
        Check-Exit 'Install official Microsoft C++ runtime'
    }
}
Refresh-Path
if ($Action -eq 'setup') {
    Need-Tool 'py' 'Python.Python.3.12'
    & py -3.12 --version
    if ($LASTEXITCODE -ne 0) {
        & winget install --exact --id Python.Python.3.12 --source winget --accept-source-agreements --accept-package-agreements
        Check-Exit 'Install Python 3.12'
        Refresh-Path
    }
    Need-Tool 'node' 'OpenJS.NodeJS.LTS'
    $NodeVersion=[version]((& node --version).Trim().TrimStart('v'))
    if ($NodeVersion -lt [version]'22.9.0') { throw 'Upgrade Node.js to version 22.9+ LTS, then reopen this helper.' }
    Need-Tool 'tesseract' 'UB-Mannheim.TesseractOCR'
    if (-not (Test-Path $Python)) { & py -3.12 -m venv .venv; Check-Exit 'Create Python environment' }
    & $Python -m pip install -r backend/requirements.lock
    Check-Exit 'Install Python dependencies'
    & $Python -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
    Check-Exit 'Install official CPU PyTorch'
    $Font=Join-Path $Root 'models\fonts\NotoSansCJK-Regular.ttc'
    New-Item -ItemType Directory -Force (Split-Path -Parent $Font) | Out-Null
    if (-not (Test-Path $Font)) {
        [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/notofonts/noto-cjk/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Sans/OTC/NotoSansCJK-Regular.ttc' -OutFile ($Font+'.part')
        $Hash=(Get-FileHash ($Font+'.part') -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($Hash -ne 'b76b0433203017ca80401b2ee0dd69350349871c4b19d504c34dbdd80541690a') {
            Remove-Item ($Font+'.part'); throw 'Official font checksum mismatch; download removed.'
        }
        Move-Item ($Font+'.part') $Font
    }
    & $Python scripts/init_env.py --password-prompt --font $Font
    Check-Exit 'Create private settings'
    # Remove inherited access to the local credential file. Does not print its contents.
    & icacls.exe (Join-Path $Root '.env') /inheritance:r /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):(F)" | Out-Null
    Check-Exit 'Restrict credential-file permissions'
    Need-VCRuntime
    & $Python scripts/download_models.py
    Check-Exit 'Download and verify local OCR/translation models'
    Push-Location frontend
    try {
        & npm.cmd ci; Check-Exit 'Install web dependencies'
        & npm.cmd run build; Check-Exit 'Build web interface'
    } finally { Pop-Location }
    Write-Host 'Setup complete. Your chosen password is used on the login page.'
} elseif ($Action -eq 'update') {
    if (-not (Test-Path $Python)) { throw 'Run setup-windows.bat first.' }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Node.js is missing. Run setup-windows.bat first.' }
    # Refuse to rebuild a running instance. This also prevents port collisions
    # that could leave an older Python process serving a newer web interface.
    Assert-PortsFree
    & $Python scripts/init_env.py
    Check-Exit 'Check private settings encoding'
    Need-VCRuntime
    & $Python scripts/download_quality.py
    Check-Exit 'Download and verify local quality models'
    Push-Location frontend
    try {
        if (-not (Test-Path node_modules)) { throw 'Web dependencies are missing. Run setup-windows.bat first.' }
        & npm.cmd run build; Check-Exit 'Update web interface'
    } finally { Pop-Location }
    & $Python scripts/activate_quality.py
    Check-Exit 'Activate local quality models'
    Write-Host 'Update complete. Run start-windows.bat. Existing password and pages were preserved. MangaOCR and Qwen3 4B are now selected.'
} elseif ($Action -eq 'start') {
    if (-not (Test-Path $Python)) { throw 'Run setup-windows.bat first.' }
    Assert-PortsFree
    $Api=$null; $Web=$null
    try {
        $Api=Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $Root -NoNewWindow -PassThru
        $Next=Join-Path $Root 'frontend\node_modules\next\dist\bin\next'
        $Frontend=Join-Path $Root 'frontend'
        $Web=Start-Process -FilePath (Get-Command node).Source -ArgumentList @(('"'+$Next+'"'),'start',('"'+$Frontend+'"'),'--hostname','127.0.0.1','--port','3000') -WorkingDirectory $Root -NoNewWindow -PassThru
        $Ready=$false
        for ($i=0; $i -lt 60; $i++) {
            if ($Api.HasExited -or $Web.HasExited) { throw 'Server stopped during startup. Read the error above.' }
            try {
                $Response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:3000' -TimeoutSec 2
                if ($Response.StatusCode -eq 200) { $Ready=$true; break }
            } catch { Start-Sleep -Milliseconds 500 }
        }
        if (-not $Ready) { throw 'Web interface did not start within the timeout.' }
        $Address='http://127.0.0.1:3000'
        if (Test-Path 'data\phone-origin.txt') { $Address=(Get-Content 'data\phone-origin.txt' -Raw).Trim() }
        Start-Process $Address
        Write-Host 'Keep this window open while reading. Press Ctrl+C here to stop MangaTrans.'
        while (-not $Api.HasExited -and -not $Web.HasExited) { Start-Sleep -Seconds 1 }
    } finally {
        # The API now owns a bounded llama.cpp subprocess. Stop only our process
        # trees so inference cannot keep running after the application closes.
        if ($Api -and -not $Api.HasExited) { Start-Process -FilePath (Join-Path $env:WINDIR 'System32\taskkill.exe') -ArgumentList @('/PID',[string]$Api.Id,'/T','/F') -NoNewWindow -Wait -ErrorAction SilentlyContinue }
        if ($Web -and -not $Web.HasExited) { Start-Process -FilePath (Join-Path $env:WINDIR 'System32\taskkill.exe') -ArgumentList @('/PID',[string]$Web.Id,'/T','/F') -NoNewWindow -Wait -ErrorAction SilentlyContinue }
        if ($Api) { & $Python scripts/cleanup_quality_cache.py ([string]$Api.Id) }
    }
} else {
    if (-not (Test-Path '.env')) { throw 'Run setup-windows.bat first.' }
    Need-Tool 'tailscale' 'Tailscale.Tailscale'
    $TailCommand=Get-Command tailscale -ErrorAction SilentlyContinue
    $TailPath=if ($TailCommand) { $TailCommand.Source } else { $null }
    if (-not $TailPath) {
        $Candidate=Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
        if (Test-Path $Candidate) { $TailPath=$Candidate }
    }
    if (-not $TailPath) { throw 'Reopen this helper after installing Tailscale.' }
    & $TailPath up
    Check-Exit 'Tailscale login; complete sign-in in the official browser page'
    $Status=(& $TailPath status --json) | ConvertFrom-Json
    Check-Exit 'Read your Tailscale device address'
    $HostName=$Status.Self.DNSName.TrimEnd('.')
    if (-not $HostName.EndsWith('.ts.net')) { throw 'A Tailscale HTTPS device name is required.' }
    & $TailPath serve --bg http://127.0.0.1:3000
    Check-Exit 'Enable private HTTPS serving'
    $Origin='https://'+$HostName
    # Pass non-secret settings to dotenv; never emit or copy session/password values.
    & $Python scripts/configure_phone.py $Origin
    Check-Exit 'Save HTTPS cookie/origin settings'
    New-Item -ItemType Directory -Force data | Out-Null
    [IO.File]::WriteAllText((Join-Path $Root 'data\phone-origin.txt'),$Origin)
    Write-Host 'Install the official Tailscale app on your phone and sign in to the SAME account.'
    Write-Host 'Restart MangaTrans, then open this private address in phone Chrome:'
    Write-Host $Origin
    Write-Host 'Do not enable Tailscale Funnel. The PC must remain awake and MangaTrans must be running.'
}
