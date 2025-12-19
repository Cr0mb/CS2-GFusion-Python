# GFusion Installer Script
# Installs all required dependencies for GFusion CS2 Cheat
# Run as Administrator

param(
    [switch]$SkipPython,
    [switch]$SkipDirectX,
    [switch]$SkipDotNet,
    [switch]$SkipVCRedist,
    [switch]$SkipPythonPackages
)

# ============================================
# Configuration
# ============================================
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$PYTHON_VERSION = "3.13.5"  
$PYTHON_URL = "https://www.python.org/ftp/python/3.13.5/python-3.13.5-amd64.exe"
$DIRECTX_URL = "https://download.microsoft.com/download/1/7/1/1718CCC4-6315-4D8E-9543-8E28A4E18C4C/dxwebsetup.exe"
$DOTNET_URL = "https://aka.ms/dotnet/8.0/dotnet-runtime-win-x64.exe"
$VCREDIST_2015_2022_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"

$TEMP_DIR = "$env:TEMP\GFusionInstall"
$SCRIPT_DIR = $PSScriptRoot

# ============================================
# Helper Functions
# ============================================

function Write-Status {
    param([string]$Message, [string]$Type = "INFO")
    $timestamp = Get-Date -Format "HH:mm:ss"
    switch ($Type) {
        "SUCCESS" { Write-Host "[$timestamp] [✓] $Message" -ForegroundColor Green }
        "ERROR"   { Write-Host "[$timestamp] [✗] $Message" -ForegroundColor Red }
        "WARNING" { Write-Host "[$timestamp] [!] $Message" -ForegroundColor Yellow }
        "INFO"    { Write-Host "[$timestamp] [i] $Message" -ForegroundColor Cyan }
        "STEP"    { Write-Host "`n[$timestamp] [$Message]" -ForegroundColor Magenta }
    }
}

function Test-AdminPrivileges {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}


function Download-File {
    param([string]$Url, [string]$OutFile)
    try {
        Write-Status "Downloading from $Url..." "INFO"
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($Url, $OutFile)
        Write-Status "Downloaded to $OutFile" "SUCCESS"
        return $true
    } catch {
        Write-Status "Failed to download: $_" "ERROR"
        return $false
    }
}

function Test-PythonInstalled {
    try {
        # Check for python command
        $pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
        if ($pythonPath) {
            $version = python --version 2>&1
            Write-Status "Python found: $version at $pythonPath" "INFO"
            
            # Check for multiple Python installations (unique paths only)
            $pythonPaths = @()
            $uniquePaths = @{}
            
            # Check common installation paths
            $commonPaths = @(
                "${env:LOCALAPPDATA}\Programs\Python",
                "${env:ProgramFiles}\Python*",
                "${env:ProgramFiles(x86)}\Python*",
                "C:\Python*"
            )
            
            foreach ($pattern in $commonPaths) {
                $found = Get-ChildItem -Path $pattern -Directory -ErrorAction SilentlyContinue
                foreach ($dir in $found) {
                    $pythonExe = Join-Path $dir.FullName "python.exe"
                    if (Test-Path $pythonExe) {
                        # Only add unique installation directories
                        $installDir = $dir.FullName
                        if (-not $uniquePaths.ContainsKey($installDir)) {
                            $uniquePaths[$installDir] = $pythonExe
                            $pythonPaths += $pythonExe
                        }
                    }
                }
            }
            
            # Only warn if there are actually multiple different installations
            if ($pythonPaths.Count -gt 1) {
                Write-Status "WARNING: Multiple Python installations detected!" "WARNING"
                Write-Host ""
                Write-Host "  Found Python installations:" -ForegroundColor Yellow
                foreach ($path in $pythonPaths) {
                    Write-Host "    - $path" -ForegroundColor Yellow
                }
                Write-Host ""
                Write-Status "This may cause conflicts. Consider uninstalling unused versions." "WARNING"
                Write-Status "Current active Python: $pythonPath" "INFO"
                Write-Host ""
            }
            
            return $true
        }
        return $false
    } catch {
        return $false
    }
}

function Test-DotNetInstalled {
    try {
        $dotnetPath = (Get-Command dotnet -ErrorAction SilentlyContinue).Source
        if ($dotnetPath) {
            $version = dotnet --version 2>&1
            Write-Status ".NET found: $version" "INFO"
            return $true
        }
        return $false
    } catch {
        return $false
    }
}

function Install-Python {
    Write-Status "INSTALLING PYTHON $PYTHON_VERSION" "STEP"
    
    $installerPath = "$TEMP_DIR\python-installer.exe"
    
    if (-not (Download-File -Url $PYTHON_URL -OutFile $installerPath)) {
        Write-Status "Failed to download Python installer" "ERROR"
        return $false
    }
    
    Write-Status "Running Python installer..." "INFO"
    $installArgs = @(
        "/quiet",
        "InstallAllUsers=1",
        "PrependPath=1",
        "Include_test=0",
        "Include_pip=1",
        "Include_doc=0"
    )
    
    $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru -NoNewWindow
    
    if ($process.ExitCode -eq 0) {
        Write-Status "Python installed successfully" "SUCCESS"
        
        # Refresh environment variables
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        return $true
    } else {
        Write-Status "Python installation failed with exit code $($process.ExitCode)" "ERROR"
        return $false
    }
}

function Install-DirectX {
    Write-Status "INSTALLING DIRECTX RUNTIME" "STEP"
    
    $installerPath = "$TEMP_DIR\dxwebsetup.exe"
    
    if (-not (Download-File -Url $DIRECTX_URL -OutFile $installerPath)) {
        Write-Status "Failed to download DirectX installer" "ERROR"
        return $false
    }
    
    Write-Status "Running DirectX installer..." "INFO"
    # Use /Q for quiet mode instead of /silent
    $process = Start-Process -FilePath $installerPath -ArgumentList "/Q" -Wait -PassThru -NoNewWindow
    
    if ($process.ExitCode -eq 0) {
        Write-Status "DirectX installed successfully" "SUCCESS"
        return $true
    } else {
        Write-Status "DirectX installation completed with code $($process.ExitCode)" "WARNING"
        return $true  # DirectX often returns non-zero even on success
    }
}

function Install-DotNet {
    Write-Status "INSTALLING .NET RUNTIME" "STEP"
    
    $installerPath = "$TEMP_DIR\dotnet-runtime-installer.exe"
    
    if (-not (Download-File -Url $DOTNET_URL -OutFile $installerPath)) {
        Write-Status "Failed to download .NET Runtime installer" "ERROR"
        return $false
    }
    
    Write-Status "Running .NET Runtime installer..." "INFO"
    $process = Start-Process -FilePath $installerPath -ArgumentList "/quiet", "/norestart" -Wait -PassThru -NoNewWindow
    
    if ($process.ExitCode -eq 0 -or $process.ExitCode -eq 3010) {
        Write-Status ".NET Runtime installed successfully" "SUCCESS"
        return $true
    } else {
        Write-Status ".NET Runtime installation failed with exit code $($process.ExitCode)" "ERROR"
        return $false
    }
}

function Install-VCRedist {
    Write-Status "INSTALLING VISUAL C++ REDISTRIBUTABLE" "STEP"
    
    $installerPath = "$TEMP_DIR\vc_redist.x64.exe"
    
    if (-not (Download-File -Url $VCREDIST_2015_2022_URL -OutFile $installerPath)) {
        Write-Status "Failed to download VC++ Redistributable installer" "ERROR"
        return $false
    }
    
    Write-Status "Running VC++ Redistributable installer..." "INFO"
    $process = Start-Process -FilePath $installerPath -ArgumentList "/install", "/quiet", "/norestart" -Wait -PassThru -NoNewWindow
    
    if ($process.ExitCode -eq 0 -or $process.ExitCode -eq 3010 -or $process.ExitCode -eq 1638) {
        Write-Status "VC++ Redistributable installed successfully" "SUCCESS"
        return $true
    } else {
        Write-Status "VC++ Redistributable installation completed with code $($process.ExitCode)" "WARNING"
        return $true  # Often returns non-zero if already installed
    }
}

function Install-PythonPackages {
    Write-Status "INSTALLING PYTHON PACKAGES" "STEP"
    
    # Hardcoded package list
    $packages = @(
        "PyQt5",
        "Pillow",
        "comtypes",
        "cryptography",
        "keyboard",
        "matplotlib",
        "psutil",
        "requests",
        "pywin32",
        "numpy"
    )
    
    try {
        # Upgrade pip first
        Write-Status "Upgrading pip..." "INFO"
        python -m pip install --upgrade pip 2>&1 | Out-Null
        
        # Install each package
        foreach ($package in $packages) {
            Write-Status "Installing $package..." "INFO"
            $result = python -m pip install $package 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Status "$package installed successfully" "SUCCESS"
            } else {
                Write-Status "Failed to install $package" "WARNING"
            }
        }
        
        Write-Status "Python packages installation completed" "SUCCESS"
        return $true
    } catch {
        Write-Status "Failed to install Python packages: $_" "ERROR"
        return $false
    }
}

function Initialize-TempDirectory {
    if (Test-Path $TEMP_DIR) {
        Remove-Item -Path $TEMP_DIR -Recurse -Force
    }
    New-Item -ItemType Directory -Path $TEMP_DIR -Force | Out-Null
    Write-Status "Temporary directory created: $TEMP_DIR" "INFO"
}

function Cleanup-TempDirectory {
    if (Test-Path $TEMP_DIR) {
        try {
            Remove-Item -Path $TEMP_DIR -Recurse -Force
            Write-Status "Temporary files cleaned up" "INFO"
        } catch {
            Write-Status "Failed to clean up temporary files: $_" "WARNING"
        }
    }
}

# ============================================
# Main Installation Process
# ============================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "    GFusion CS2 Cheat - Installer" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check admin privileges
if (-not (Test-AdminPrivileges)) {
    Write-Status "This script requires Administrator privileges!" "ERROR"
    Write-Status "Please run PowerShell as Administrator and try again." "ERROR"
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Status "Running with Administrator privileges" "SUCCESS"
Write-Host ""

# Initialize temp directory
Initialize-TempDirectory

$installationSuccess = $true

# Install Python
if (-not $SkipPython) {
    if (Test-PythonInstalled) {
        Write-Status "Python is already installed, skipping..." "INFO"
    } else {
        if (-not (Install-Python)) {
            $installationSuccess = $false
        }
    }
} else {
    Write-Status "Skipping Python installation (--SkipPython)" "WARNING"
}

# Install DirectX
if (-not $SkipDirectX) {
    if (-not (Install-DirectX)) {
        Write-Status "DirectX installation had issues, but continuing..." "WARNING"
    }
} else {
    Write-Status "Skipping DirectX installation (--SkipDirectX)" "WARNING"
}

# Install .NET Runtime
if (-not $SkipDotNet) {
    if (Test-DotNetInstalled) {
        Write-Status ".NET Runtime is already installed, skipping..." "INFO"
    } else {
        if (-not (Install-DotNet)) {
            Write-Status ".NET installation failed, but continuing..." "WARNING"
        }
    }
} else {
    Write-Status "Skipping .NET installation (--SkipDotNet)" "WARNING"
}

# Install Visual C++ Redistributable
if (-not $SkipVCRedist) {
    if (-not (Install-VCRedist)) {
        Write-Status "VC++ Redistributable installation had issues, but continuing..." "WARNING"
    }
} else {
    Write-Status "Skipping VC++ Redistributable installation (--SkipVCRedist)" "WARNING"
}

# Install Python packages
if (-not $SkipPythonPackages) {
    if (Test-PythonInstalled) {
        if (-not (Install-PythonPackages)) {
            $installationSuccess = $false
        }
    } else {
        Write-Status "Python not found, cannot install packages" "ERROR"
        $installationSuccess = $false
    }
} else {
    Write-Status "Skipping Python package installation (--SkipPythonPackages)" "WARNING"
}

# Cleanup
Cleanup-TempDirectory

# Final status
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan

if ($installationSuccess) {
    Write-Status "INSTALLATION COMPLETED SUCCESSFULLY!" "SUCCESS"
    Write-Host ""
    Write-Status "You can now run GFusion.py" "INFO"
    Write-Status "Command: python GFusion.py" "INFO"
} else {
    Write-Status "INSTALLATION COMPLETED WITH ERRORS" "WARNING"
    Write-Host ""
    Write-Status "Some components failed to install." "WARNING"
    Write-Status "Please check the output above for details." "WARNING"
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Keep window open
Read-Host "Press Enter to exit"
