# Define Paths
$GoFolder = "C:\Users\ljsim\OneDrive\Documents\Engineering\golang"
$GoInstaller = "$env:TEMP\golang-installer.msi"
$GoUrl = "https://go.dev/dl/go1.21.4.windows-amd64.msi"

# Uninstall Existing Go Installation
Write-Host "Uninstalling existing Go installation..." -ForegroundColor Red
$GoUninstall = winget uninstall --exact --silent --accept-source-agreements "Go Programming Language" 2>&1
if ($GoUninstall -match "failed") {
    Write-Host "Go uninstallation failed or Go not installed." -ForegroundColor Yellow
} else {
    Write-Host "Go uninstalled successfully." -ForegroundColor Green
}

Start-Sleep -Seconds 5

# Ensure Go Directory Exists
if (-Not (Test-Path $GoFolder)) {
    New-Item -ItemType Directory -Path $GoFolder | Out-Null
    Write-Host "Created Go directory: $GoFolder" -ForegroundColor Green
} else {
    Write-Host "Go directory already exists: $GoFolder" -ForegroundColor Cyan
}

# Download Go with Retry Logic
function Download-File($url, $destination) {
    $attempts = 3
    for ($i=0; $i -lt $attempts; $i++) {
        try {
            Invoke-WebRequest -Uri $url -OutFile $destination -ErrorAction Stop
            return $true
        } catch {
            Write-Host "Download failed for $url (Attempt $($i+1) of $attempts)" -ForegroundColor Red
            Start-Sleep -Seconds 2
        }
    }
    return $false
}

Write-Host "Downloading GoLang..." -ForegroundColor Yellow
if (-Not (Download-File -url $GoUrl -destination $GoInstaller)) {
    Write-Host "GoLang download failed. Exiting script." -ForegroundColor Red
    exit 1
}

# Install GoLang
Write-Host "Installing GoLang..." -ForegroundColor Green
Start-Process msiexec.exe -ArgumentList "/i $GoInstaller /quiet /norestart" -Wait
Remove-Item $GoInstaller

# Ensure Windows recognizes new installations
Start-Sleep -Seconds 5
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine")

# Set Up Go Environment Variables
$GoBin = "C:\Go\bin"
$ExistingPath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
if ($ExistingPath -notlike "*$GoBin*") {
    Write-Host "Adding Go to System PATH..." -ForegroundColor Cyan
    [System.Environment]::SetEnvironmentVariable("Path", "$ExistingPath;$GoBin", "Machine")
} else {
    Write-Host "Go is already in System PATH." -ForegroundColor Green
}

# Set GOPATH
Write-Host "Setting up Go workspace..." -ForegroundColor Yellow
[System.Environment]::SetEnvironmentVariable("GOPATH", $GoFolder, "Machine")
$env:GOPATH = $GoFolder

# Create Go Workspace Structure
$GoSrc = "$GoFolder\src"
$GoBin = "$GoFolder\bin"
$GoPkg = "$GoFolder\pkg"

foreach ($folder in @($GoSrc, $GoBin, $GoPkg)) {
    if (-Not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder | Out-Null
        Write-Host "Created: $folder" -ForegroundColor Green
    }
}

# Install Go Development Tools
Write-Host "Installing Go Development Tools..." -ForegroundColor Cyan
go install golang.org/x/tools/cmd/goimports@latest
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

# Verify Installation
Write-Host "Verifying Go Installation..." -ForegroundColor Cyan
$GoVersion = go version 2>&1
if ($GoVersion -match "go version") {
    Write-Host "`nGo successfully installed!" -ForegroundColor Green
    Write-Host $GoVersion
} else {
    Write-Host "`nGo installation failed!" -ForegroundColor Red
}

Write-Host "`nGoLang Setup Complete!" -ForegroundColor Green
