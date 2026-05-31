# setup.ps1
# Script to bootstrap a portable Python and FFmpeg environment for the YouTube Karaoke Downloader.

$ErrorActionPreference = "Stop"

# Define Paths
$projDir = $PSScriptRoot
$binDir = Join-Path $projDir "bin"
$embedDir = Join-Path $projDir "python_embed"
$reqFile = Join-Path $projDir "requirements.txt"

# Create Directories if they don't exist
if (-not (Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir | Out-Null
}
if (-not (Test-Path $embedDir)) {
    New-Item -ItemType Directory -Path $embedDir | Out-Null
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "      YOUTUBE KARAOKE BOT - ENVIRONMENT SETUP     " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Download & Setup Portable Python
$pythonExe = Join-Path $embedDir "python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "[1/4] Downloading Portable Python 3.10.11..." -ForegroundColor Yellow
    $pyZipUrl = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip"
    $pyZipPath = Join-Path $projDir "python_embed.zip"
    
    Invoke-WebRequest -Uri $pyZipUrl -OutFile $pyZipPath -UseBasicParsing
    
    Write-Host "Extracting Python..." -ForegroundColor Yellow
    Expand-Archive -Path $pyZipPath -DestinationPath $embedDir -Force
    Remove-Item $pyZipPath -Force
    
    # Configure import site in python310._pth
    $pthFile = Join-Path $embedDir "python310._pth"
    if (Test-Path $pthFile) {
        Write-Host "Configuring Python site-packages..." -ForegroundColor Yellow
        $pthContent = Get-Content $pthFile
        # Uncomment "import site"
        $pthContent = $pthContent -replace "#import site", "import site"
        Set-Content -Path $pthFile -Value $pthContent
    }
    Write-Host "[OK] Portable Python installed successfully." -ForegroundColor Green
} else {
    Write-Host "[OK] Portable Python already exists." -ForegroundColor Green
}

# 2. Setup Pip
$hasPip = $false
try {
    $pipCheck = & $pythonExe -m pip --version 2>&1
    if ($LASTEXITCODE -eq 0) { $hasPip = $true }
} catch {}

if (-not $hasPip) {
    Write-Host "[2/4] Installing pip..." -ForegroundColor Yellow
    $getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
    $getPipPath = Join-Path $projDir "get-pip.py"
    
    Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath -UseBasicParsing
    & $pythonExe $getPipPath --no-warn-script-location
    Remove-Item $getPipPath -Force
    Write-Host "[OK] Pip installed successfully." -ForegroundColor Green
} else {
    Write-Host "[OK] Pip is already installed." -ForegroundColor Green
}

# 3. Install Python Libraries
Write-Host "[3/4] Installing required Python libraries from requirements.txt..." -ForegroundColor Yellow
& $pythonExe -m pip install -r $reqFile --no-warn-script-location
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] All Python libraries installed successfully." -ForegroundColor Green
} else {
    Write-Error "Failed to install Python libraries."
}

# 4. Download & Setup FFmpeg
$ffmpegExe = Join-Path $binDir "ffmpeg.exe"
$ffprobeExe = Join-Path $binDir "ffprobe.exe"

if (-not (Test-Path $ffmpegExe) -or -not (Test-Path $ffprobeExe)) {
    Write-Host "[4/4] Downloading FFmpeg and FFprobe (portabel)..." -ForegroundColor Yellow
    
    $ffmpegZipUrl = "https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffmpeg-4.4.1-win-64.zip"
    $ffprobeZipUrl = "https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffprobe-4.4.1-win-64.zip"
    
    $ffmpegZipPath = Join-Path $projDir "ffmpeg.zip"
    $ffprobeZipPath = Join-Path $projDir "ffprobe.zip"
    
    Write-Host "Downloading ffmpeg.zip..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $ffmpegZipUrl -OutFile $ffmpegZipPath -UseBasicParsing
    
    Write-Host "Downloading ffprobe.zip..." -ForegroundColor Gray
    Invoke-WebRequest -Uri $ffprobeZipUrl -OutFile $ffprobeZipPath -UseBasicParsing
    
    Write-Host "Extracting binaries..." -ForegroundColor Yellow
    Expand-Archive -Path $ffmpegZipPath -DestinationPath $binDir -Force
    Expand-Archive -Path $ffprobeZipPath -DestinationPath $binDir -Force
    
    Remove-Item $ffmpegZipPath -Force
    Remove-Item $ffprobeZipPath -Force
    
    Write-Host "[OK] FFmpeg and FFprobe downloaded and set up." -ForegroundColor Green
} else {
    Write-Host "[OK] FFmpeg and FFprobe already exist in bin/ folder." -ForegroundColor Green
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "      SETUP COMPLETED! BOT READY TO RUN           " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
