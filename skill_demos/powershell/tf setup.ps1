# Define Paths
$TerraformFolder = "C:\Users\ljsim\OneDrive\Documents\Engineering\terraform"
$TerraformZip = "$env:TEMP\terraform.zip"
$TerraformUrl = "https://releases.hashicorp.com/terraform/1.7.0/terraform_1.7.0_windows_amd64.zip"

# Ensure Terraform Directory Exists
if (-Not (Test-Path $TerraformFolder)) {
    New-Item -ItemType Directory -Path $TerraformFolder | Out-Null
    Write-Host "Created Terraform directory: $TerraformFolder" -ForegroundColor Green
} else {
    Write-Host "Terraform directory already exists: $TerraformFolder" -ForegroundColor Cyan
}

# Download Terraform with Retry Logic
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

Write-Host "Downloading Terraform..." -ForegroundColor Yellow
if (-Not (Download-File -url $TerraformUrl -destination $TerraformZip)) {
    Write-Host "Terraform download failed. Exiting script." -ForegroundColor Red
    exit 1
}

# Extract Terraform to Destination Folder
Write-Host "Extracting Terraform to $TerraformFolder..." -ForegroundColor Yellow
Expand-Archive -Path $TerraformZip -DestinationPath $TerraformFolder -Force

# Clean up the ZIP file
Remove-Item $TerraformZip

# Add Terraform to System PATH
$ExistingPath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
if ($ExistingPath -notlike "*$TerraformFolder*") {
    Write-Host "Adding Terraform to System PATH..." -ForegroundColor Cyan
    [System.Environment]::SetEnvironmentVariable("Path", "$ExistingPath;$TerraformFolder", "Machine")
} else {
    Write-Host "Terraform is already in System PATH." -ForegroundColor Green
}

# Reload Environment Variables
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine")

# Verify Terraform Installation
Write-Host "Verifying Terraform Installation..." -ForegroundColor Cyan
$TerraformVersion = terraform --version 2>&1

if ($TerraformVersion -match "Terraform v") {
    Write-Host "`nTerraform successfully installed!" -ForegroundColor Green
    Write-Host $TerraformVersion
} else {
    Write-Host "`nTerraform installation failed!" -ForegroundColor Red
}

Write-Host "`nTerraform Setup Complete!" -ForegroundColor Green
