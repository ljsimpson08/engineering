# Define Paths
$BasePath = "C:\Users\ljsim\OneDrive\Documents\Engineering"
$Downloads = "$env:TEMP\DevSetupDownloads"

# Ensure Download Directory Exists
if (-Not (Test-Path $Downloads)) { New-Item -ItemType Directory -Path $Downloads | Out-Null }

# Define Software URLs
$Urls = @{
    "Python"     = "https://www.python.org/ftp/python/3.12.1/python-3.12.1-amd64.exe"
    "NodeJS"     = "https://nodejs.org/dist/latest/node-v20.5.1-x64.msi"
    "Ruby"       = "https://github.com/oneclick/rubyinstaller2/releases/download/RubyInstaller-3.2.2/rubyinstaller-3.2.2-1-x64.exe"
    "GoLang"     = "https://go.dev/dl/go1.21.4.windows-amd64.msi"
    "AWSCLI"     = "https://awscli.amazonaws.com/AWSCLIV2.msi"
    "VSCode"     = "https://code.visualstudio.com/sha/download?build=stable&os=win32-x64"
    "Terraform"  = "https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_windows_amd64.zip"
}

# Create Virtual Environment Folders
Write-Host "Creating Virtual Environment Folders..." -ForegroundColor Yellow
$folders = @("golang", "ruby", "javascript", "python", "terraform")
foreach ($folder in $folders) {
    $fullPath = "$BasePath\$folder"
    if (-Not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath | Out-Null
        Write-Host "Created folder: $fullPath" -ForegroundColor Green
    }
}

# Uninstall Software using winget
$Failures = @()
$UninstallList = @("AWS CLI", "Visual Studio Code", "Python", "Node.js", "Ruby", "Go")

Write-Host "Uninstalling existing software..." -ForegroundColor Red
foreach ($software in $UninstallList) {
    Write-Host "Uninstalling $software..." -ForegroundColor Yellow
    $uninstallResult = winget uninstall --exact --silent --accept-source-agreements $software 2>&1
    if ($uninstallResult -match "failed") {
        Write-Host "$software uninstallation failed!" -ForegroundColor Red
        $Failures += "$software uninstall failed"
    }
}

Start-Sleep -Seconds 5

# Function to retry downloads
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

# Install Software
foreach ($software in $Urls.Keys) {
    $file = "$Downloads\$software.exe"
    $url = $Urls[$software]

    Write-Host "Installing $software..." -ForegroundColor Green
    if (-Not (Test-Path $file)) {
        if (-Not (Download-File -url $url -destination $file)) {
            $Failures += "$software download failed"
            continue
        }
    }

    try {
        if ($software -eq "Python") {
            Start-Process -FilePath $file -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
        } elseif ($software -eq "NodeJS" -or $software -eq "GoLang" -or $software -eq "AWSCLI") {
            Start-Process msiexec.exe -ArgumentList "/i $file /quiet /norestart" -Wait
        } elseif ($software -eq "Ruby") {
            Start-Process -FilePath $file -ArgumentList "/verysilent /tasks=modpath" -Wait
        } elseif ($software -eq "Terraform") {
            Expand-Archive -Path $file -DestinationPath "$BasePath\terraform" -Force
        } elseif ($software -eq "VSCode") {
            Start-Process -FilePath $file -ArgumentList "/silent /mergetasks=!runcode" -Wait
        }
        Remove-Item $file
    } catch {
        Write-Host "$software installation failed" -ForegroundColor Red
        $Failures += "$software installation failed"
    }
}

# Refresh Environment Variables
$env:Path += ";C:\Python312\Scripts;$BasePath\terraform;$BasePath\golang"

# Ensure Windows recognizes new installations
Start-Sleep -Seconds 5
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine")

# Set up Python Virtual Environment
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "Setting up Python Virtual Environment..." -ForegroundColor Cyan
    python -m pip install --upgrade pip
    python -m pip install virtualenv
    python -m virtualenv "$BasePath\python\env"
    & "$BasePath\python\env\Scripts\pip" install fastapi uvicorn numpy pandas scipy scikit-learn boto3 requests flask sqlalchemy pytest black pylint mypy
} else {
    Write-Host "Python installation not found!" -ForegroundColor Red
    $Failures += "Python setup failed"
}

# Set up Node.js Virtual Environment
if (Get-Command node -ErrorAction SilentlyContinue) {
    Write-Host "Setting up Node.js Environment..." -ForegroundColor Cyan
    cd "$BasePath\javascript"
    npm init -y
    npm install express axios dotenv jest typescript ts-node @typescript-eslint/parser eslint
} else {
    Write-Host "Node.js installation not found!" -ForegroundColor Red
    $Failures += "Node.js setup failed"
}

# Set up Ruby Environment
if (Get-Command gem -ErrorAction SilentlyContinue) {
    Write-Host "Setting up Ruby Environment..." -ForegroundColor Cyan
    cd "$BasePath\ruby"
    gem install bundler
    bundle init
} else {
    Write-Host "Ruby installation not found!" -ForegroundColor Red
    $Failures += "Ruby setup failed"
}

# Set up GoLang Environment
if (Get-Command go -ErrorAction SilentlyContinue) {
    Write-Host "Setting up GoLang Environment..." -ForegroundColor Cyan
    $env:GOPATH = "$BasePath\golang"
    mkdir -Force "$env:GOPATH\src"
    go install golang.org/x/tools/cmd/goimports@latest
    go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
} else {
    Write-Host "GoLang installation not found!" -ForegroundColor Red
    $Failures += "GoLang setup failed"
}

# Final Verification
Write-Host "`n--- INSTALLATION SUMMARY ---" -ForegroundColor Yellow
Write-Host "`nSuccessful Installations:" -ForegroundColor Green
$Successes = @("Python", "Node.js", "Ruby", "GoLang", "AWSCLI", "Terraform", "VSCode")
foreach ($success in $Successes) { Write-Host "- $success" }

Write-Host "`nFailed Installations:" -ForegroundColor Red
if ($Failures.Count -eq 0) {
    Write-Host "No failures detected!" -ForegroundColor Green
} else {
    $Failures | ForEach-Object { Write-Host "- $_" }
}

Write-Host "`nEnvironment Setup Complete!" -ForegroundColor Green
