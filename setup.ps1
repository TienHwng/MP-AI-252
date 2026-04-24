$ErrorActionPreference = "Stop"

$script:Step = 0
$script:Summary = @()

function Write-Banner {
    Clear-Host
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor DarkCyan
    Write-Host "║                    PROJECT SETUP WIZARD                  ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor DarkCyan
    Write-Host ""
}

function Write-Step {
    param([string]$Message)

    $script:Step++
    Write-Host ""
    Write-Host ("[{0}] {1}" -f $script:Step, $Message) -ForegroundColor Magenta
    Write-Host ("─" * 60) -ForegroundColor DarkGray
}

function Write-Info {
    param([string]$Message)
    Write-Host ("  • {0}" -f $Message) -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host ("  ✓ {0}" -f $Message) -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host ("  ! {0}" -f $Message) -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host ("  ✗ {0}" -f $Message) -ForegroundColor Red
}

function Add-Summary {
    param([string]$Key, [string]$Value)

    $script:Summary += [PSCustomObject]@{
        Key = $Key
        Value = $Value
    }
}

function Show-Summary {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor DarkCyan
    Write-Host "║                         SUMMARY                          ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor DarkCyan
    Write-Host ""

    foreach ($item in $script:Summary) {
        "{0,-18}: {1}" -f $item.Key, $item.Value | Write-Host -ForegroundColor White
    }

    Write-Host ""
    Write-Host "Setup completed successfully." -ForegroundColor Green
    Write-Host ""
}

function Test-CommandExists {
    param([string]$CommandName)

    try {
        $null = Get-Command $CommandName -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Test-GitInstalled {
    if (-not (Test-CommandExists "git")) {
        return $false
    }

    try {
        $version = git --version 2>$null
        return ($LASTEXITCODE -eq 0 -and $version)
    } catch {
        return $false
    }
}

function Install-GitIfMissing {
    if (Test-GitInstalled) {
        $gitVersion = git --version
        Write-Ok "Git detected: $gitVersion"
        Add-Summary "Git" $gitVersion
        return
    }

    Write-Warn "Git was not found."
    Write-Info "Attempting to install Git with winget..."

    if (-not (Test-CommandExists "winget")) {
        Write-Err "winget is not available."
        Write-Host "Please install Git manually, then run this script again." -ForegroundColor Yellow
        exit 1
    }

    winget install --id Git.Git --exact --source winget --accept-package-agreements --accept-source-agreements | Out-Null

    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"

    if (-not (Test-GitInstalled)) {
        Write-Err "Git seems installed, but is not available in PATH yet."
        Write-Host "Please reopen the terminal and run this script again." -ForegroundColor Yellow
        exit 1
    }

    $gitVersion = git --version
    Write-Ok "Git installed successfully: $gitVersion"
    Add-Summary "Git" $gitVersion
}

function Find-Python312 {
    try {
        $pythonPath = py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $pythonPath) {
            return $pythonPath.Trim()
        }
    } catch {}

    try {
        $pythonCmd = Get-Command python -ErrorAction Stop
        $versionOutput = & $pythonCmd.Source --version 2>&1
        if ($versionOutput -match "Python 3\.12") {
            return $pythonCmd.Source
        }
    } catch {}

    return $null
}

function Test-Python312Installed {
    $pythonPath = Find-Python312
    return -not [string]::IsNullOrWhiteSpace($pythonPath)
}

function Install-Python312IfMissing {
    if (Test-Python312Installed) {
        $pythonPath = Find-Python312
        $pythonVersion = & $pythonPath --version
        Write-Ok "Python 3.12 detected: $pythonVersion"
        Add-Summary "Python" $pythonVersion
        return
    }

    Write-Warn "Python 3.12.x was not found."
    Write-Info "Attempting to install the latest available Python 3.12.x with winget..."

    if (-not (Test-CommandExists "winget")) {
        Write-Err "winget is not available."
        Write-Host "Please install Python 3.12 manually, then run this script again." -ForegroundColor Yellow
        exit 1
    }

    try {
        winget install --id Python.Python.3.12 --exact --source winget --accept-package-agreements --accept-source-agreements | Out-Null
    } catch {
        Write-Err "Automatic Python 3.12.x installation failed."
        Write-Host "Please install Python 3.12 manually, then run this script again." -ForegroundColor Yellow
        exit 1
    }

    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"

    $pythonPath = Find-Python312
    if (-not $pythonPath) {
        Write-Err "Python 3.12.x seems installed, but is not available in PATH yet."
        Write-Host "Please reopen the terminal and run this script again." -ForegroundColor Yellow
        exit 1
    }

    $pythonVersion = & $pythonPath --version
    Write-Ok "Python installed successfully: $pythonVersion"
    Add-Summary "Python" $pythonVersion
}

function Test-VenvIsPython312 {
    param([string]$PythonExe)

    if (-not (Test-Path $PythonExe)) {
        return $false
    }

    try {
        $version = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        return $version.Trim() -eq "3.12"
    } catch {
        return $false
    }
}

function Normalize-PackageName {
    param([string]$Name)
    return $Name.Trim().ToLower().Replace("_", "-")
}

function Parse-RequirementLine {
    param([string]$Line)

    $trimmed = $Line.Trim()

    if (-not $trimmed) { return $null }
    if ($trimmed.StartsWith("#")) { return $null }

    if ($trimmed -match '^\s*([A-Za-z0-9._\-]+)\s*==\s*([^\s;]+)') {
        return [PSCustomObject]@{
            Name = $matches[1]
            Version = $matches[2]
            Raw = $trimmed
            ExactPin = $true
        }
    }

    if ($trimmed -match '^\s*([A-Za-z0-9._\-]+)') {
        return [PSCustomObject]@{
            Name = $matches[1]
            Version = ""
            Raw = $trimmed
            ExactPin = $false
        }
    }

    return $null
}

function Get-InstalledPackagesMap {
    param([string]$PythonExe)

    $map = @{}
    $output = & $PythonExe -m pip list --format=freeze 2>$null

    foreach ($line in $output) {
        if ($line -match '^([A-Za-z0-9._\-]+)==(.+)$') {
            $pkgName = Normalize-PackageName $matches[1]
            $pkgVersion = $matches[2].Trim()
            $map[$pkgName] = $pkgVersion
        }
    }

    return $map
}

function Get-RequirementsStatus {
    param(
        [string]$RequirementsPath,
        [string]$PythonExe
    )

    $requirements = Get-Content $RequirementsPath
    $installedMap = Get-InstalledPackagesMap -PythonExe $PythonExe
    $rows = @()

    foreach ($line in $requirements) {
        $req = Parse-RequirementLine -Line $line
        if ($null -eq $req) { continue }

        $normalized = Normalize-PackageName $req.Name
        $installedVersion = $null

        if ($installedMap.ContainsKey($normalized)) {
            $installedVersion = $installedMap[$normalized]
        }

        $status = ""
        if (-not $installedVersion) {
            $status = "MISSING"
        } elseif ($req.ExactPin -and $installedVersion -eq $req.Version) {
            $status = "OK"
        } elseif ($req.ExactPin -and $installedVersion -ne $req.Version) {
            $status = "UPDATE"
        } else {
            $status = "INSTALLED"
        }

        $rows += [PSCustomObject]@{
            Package   = $req.Name
            Required  = $(if ($req.Version) { $req.Version } else { "-" })
            Installed = $(if ($installedVersion) { $installedVersion } else { "-" })
            Status    = $status
            Raw       = $req.Raw
        }
    }

    return $rows
}

function Show-RequirementsStatusTable {
    param([array]$Rows)

    if ($Rows.Count -eq 0) {
        Write-Warn "No valid package lines found in requirements.txt"
        return
    }

    Write-Host ""
    Write-Host ("{0,-28} {1,-14} {2,-14} {3,-10}" -f "PACKAGE", "REQUIRED", "INSTALLED", "STATUS") -ForegroundColor Cyan
    Write-Host ("{0,-28} {1,-14} {2,-14} {3,-10}" -f ("-"*28), ("-"*14), ("-"*14), ("-"*10)) -ForegroundColor DarkGray

    foreach ($row in $Rows) {
        $color = "White"
        switch ($row.Status) {
            "OK"        { $color = "Green" }
            "INSTALLED" { $color = "Green" }
            "UPDATE"    { $color = "Yellow" }
            "MISSING"   { $color = "Red" }
        }

        Write-Host ("{0,-28} {1,-14} {2,-14} {3,-10}" -f $row.Package, $row.Required, $row.Installed, $row.Status) -ForegroundColor $color
    }

    $okCount = ($Rows | Where-Object { $_.Status -eq "OK" -or $_.Status -eq "INSTALLED" }).Count
    $changeCount = ($Rows | Where-Object { $_.Status -eq "MISSING" -or $_.Status -eq "UPDATE" }).Count

    Write-Host ""
    Write-Info "$okCount package(s) already satisfied, $changeCount package(s) need install/update."
}

function Get-CurrentPipVersion {
    param([string]$PythonExe)

    try {
        $version = & $PythonExe -c "import importlib.metadata as m; print(m.version('pip'))" 2>$null
        if ($LASTEXITCODE -eq 0 -and $version) {
            return $version.Trim()
        }
    } catch {}

    return $null
}

function Get-LatestPipVersion {
    param([string]$PythonExe)

    try {
        $json = & $PythonExe -m pip index versions pip --json 2>$null
        if ($LASTEXITCODE -eq 0 -and $json) {
            $data = $json | ConvertFrom-Json
            if ($data.versions -and $data.versions.Count -gt 0) {
                return [string]$data.versions[0]
            }
        }
    } catch {}

    return $null
}

function Install-RequirementsSelective {
    param(
        [string]$PythonExe,
        [array]$Rows
    )

    $toInstall = $Rows | Where-Object { $_.Status -ne "OK" }

    if ($toInstall.Count -eq 0) {
        Write-Ok "All packages from requirements.txt are already satisfied."
        return
    }

    $total = $toInstall.Count
    $index = 0

    foreach ($row in $toInstall) {
        $index++

        $title = "[{0}/{1}] Installing: {2}" -f $index, $total, $row.Raw
        if ($title.Length -gt 54) {
            $title = $title.Substring(0, 51) + "..."
        }

        Write-Host ""
        Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor DarkCyan

        $line = "║ " + $title.PadRight(56) + " ║"
        
        Write-Host $line -ForegroundColor Cyan
        Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor DarkCyan
        Write-Host ("Status    : {0}" -f $row.Status) -ForegroundColor Yellow
        Write-Host ("Installed : {0}" -f $row.Installed) -ForegroundColor DarkGray
        Write-Host ("Required  : {0}" -f $row.Required) -ForegroundColor DarkGray
        Write-Host ""

        try {
            Write-Info ("Running pip install for {0}" -f $row.Package)
            & $PythonExe -m pip install $row.Raw
            Write-Host ""
            Write-Ok ("{0} installed/updated." -f $row.Package)
        } catch {
            Write-Host ""
            Write-Err ("Failed to install {0}" -f $row.Package)
            throw
        }

        if ($index -lt $total) {
            $percent = [int](($index / $total) * 100)
            Write-Host ("Progress  : {0}% ({1}/{2})" -f $percent, $index, $total) -ForegroundColor Magenta
        } else {
            Write-Host "Progress  : 100% (completed)" -ForegroundColor Green
        }

        Write-Host ""
    }
}

function Enable-VenvInCurrentSession {
    param([string]$ProjectRoot)

    $activateScript = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"

    if (-not (Test-Path $activateScript)) {
        Write-Warn "Could not find Activate.ps1"
        return
    }

    . $activateScript
    Set-Location $ProjectRoot
    Write-Ok "Virtual environment activated in current terminal."
}

function Show-FinishTransition {
    param([bool]$WillExit = $true)

    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor DarkCyan
    Write-Host "║                    SETUP COMPLETED                       ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor DarkCyan
    Write-Host ""

    Write-Ok "Setup has completed successfully."

    if ($WillExit) {
        Write-Info "Preparing to exit the setup program..."
        Start-Sleep -Milliseconds 900
    } else {
        Write-Info "The setup process is complete. You can continue using the current terminal."
    }

    Write-Host ""
}

Write-Banner

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$venvPath = Join-Path $projectRoot ".venv"
$requirementsPath = Join-Path $projectRoot "requirements.txt"
$preCommitConfigPath = Join-Path $projectRoot ".pre-commit-config.yaml"
$gitHookPath = Join-Path $projectRoot ".git\hooks\pre-commit"

$pythonExeInVenv = Join-Path $venvPath "Scripts\python.exe"
$preCommitExeInVenv = Join-Path $venvPath "Scripts\pre-commit.exe"

Add-Summary "Project root" $projectRoot

Write-Step "Checking Git"
Install-GitIfMissing

Write-Step "Checking Python 3.12.x"
Install-Python312IfMissing
$python312 = Find-Python312

Write-Step "Preparing virtual environment"
$needCreateVenv = $true

if (Test-Path $pythonExeInVenv) {
    if (Test-VenvIsPython312 -PythonExe $pythonExeInVenv) {
        Write-Ok ".venv already exists and uses Python 3.12"
        Add-Summary "Virtual env" "Reused existing .venv"
        $needCreateVenv = $false
    } else {
        Write-Warn ".venv exists but does not use Python 3.12"
        Write-Info "Recreating .venv..."
        Remove-Item -Recurse -Force $venvPath
    }
}

if ($needCreateVenv) {
    Write-Info "Creating .venv"
    & $python312 -m venv $venvPath | Out-Null
    Write-Ok ".venv created."
    Add-Summary "Virtual env" "Created new .venv"
}

Write-Step "Checking pip"
$currentPipVersion = Get-CurrentPipVersion -PythonExe $pythonExeInVenv
$latestPipVersion = Get-LatestPipVersion -PythonExe $pythonExeInVenv

if (-not $currentPipVersion) {
    Write-Warn "Could not determine current pip version. Attempting upgrade..."
    & $pythonExeInVenv -m pip install --upgrade pip | Out-Null
    $currentPipVersion = Get-CurrentPipVersion -PythonExe $pythonExeInVenv

    if ($currentPipVersion) {
        Write-Ok "pip is now available at version $currentPipVersion"
    } else {
        Write-Warn "pip upgrade ran, but current version is still unknown."
    }
} elseif (-not $latestPipVersion) {
    Write-Warn "Could not determine latest pip version online. Keeping current pip $currentPipVersion"
    Write-Ok "Current pip version: $currentPipVersion"
} elseif ($currentPipVersion -eq $latestPipVersion) {
    Write-Ok "pip is already up to date ($currentPipVersion)"
} else {
    Write-Warn "pip is outdated ($currentPipVersion -> $latestPipVersion)"
    & $pythonExeInVenv -m pip install --upgrade pip | Out-Null
    $currentPipVersion = Get-CurrentPipVersion -PythonExe $pythonExeInVenv
    Write-Ok "pip upgraded to $currentPipVersion"
}

Add-Summary "pip" $(if ($currentPipVersion) { $currentPipVersion } else { "unknown" })

Write-Step "Installing project dependencies"
if (Test-Path $requirementsPath) {
    $reqRows = Get-RequirementsStatus -RequirementsPath $requirementsPath -PythonExe $pythonExeInVenv
    Show-RequirementsStatusTable -Rows $reqRows
    Install-RequirementsSelective -PythonExe $pythonExeInVenv -Rows $reqRows
    Add-Summary "Dependencies" "Processed requirements.txt"
} else {
    Write-Warn "requirements.txt not found. Skipping dependency installation."
    Add-Summary "Dependencies" "Skipped (requirements.txt not found)"
}

Write-Step "Setting up pre-commit"
if (Test-Path $preCommitExeInVenv) {
    Write-Ok "pre-commit is already installed in .venv"
    Add-Summary "pre-commit" "Already installed"
} else {
    Write-Info "Installing pre-commit"
    & $pythonExeInVenv -m pip install pre-commit | Out-Null
    Write-Ok "pre-commit installed."
    Add-Summary "pre-commit" "Installed"
}

if (Test-Path $preCommitConfigPath) {
    if (Test-Path $gitHookPath) {
        Write-Ok "pre-commit hook is already installed"
        Add-Summary "Git hook" "Already installed"
    } else {
        Write-Info "Installing pre-commit hook"
        & $pythonExeInVenv -m pre_commit install | Out-Null
        Write-Ok "pre-commit hook installed."
        Add-Summary "Git hook" "Installed"
    }
} else {
    Write-Warn ".pre-commit-config.yaml not found. Skipping hook installation."
    Add-Summary "Git hook" "Skipped (.pre-commit-config.yaml not found)"
}

Show-Summary

if ($MyInvocation.InvocationName -eq ".") {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor DarkCyan
    Write-Host "║                    VENV ACTIVATION                       ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor DarkCyan
    Write-Host ""

    Write-Info "Script was run with dot-sourcing: . .\setup.ps1"
    Write-Info "Activating .venv in the current terminal..."
    Enable-VenvInCurrentSession -ProjectRoot $projectRoot
} else {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor DarkCyan
    Write-Host "║                    VENV ACTIVATION                       ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor DarkCyan
    Write-Host ""

    Write-Warn "You are running the script with: .\setup.ps1"
    Write-Warn "In this mode, PowerShell cannot keep .venv activated in the current terminal after the script finishes."
    Write-Host ""

    Write-Host "To activate the virtual environment manually, run:" -ForegroundColor Cyan
    Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host ""

    Write-Host "If you want the script to activate .venv automatically in the current terminal, run it with:" -ForegroundColor Cyan
    Write-Host "  . .\setup.ps1" -ForegroundColor White
    Write-Host ""
}

Show-FinishTransition -WillExit ($MyInvocation.InvocationName -ne ".")
