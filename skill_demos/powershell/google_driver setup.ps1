# ---------------------------------------------------------------------------------------
# Set-ChromeDriverPath.ps1
#
# A script to configure the folder "C:\WebDrivers\ChromeDriver" in the user's PATH
# and verify ChromeDriver is accessible. 
# ---------------------------------------------------------------------------------------

$chromeDriverDir = "C:\WebDrivers\ChromeDriver"
$chromeDriverExe = Join-Path $chromeDriverDir "chromedriver.exe"

Write-Host "Ensuring '$chromeDriverDir' is in your user PATH..."

# 1. Check if the folder exists
if (!(Test-Path $chromeDriverExe)) {
    Write-Host "[ERROR] The file 'chromedriver.exe' was not found at:"
    Write-Host "        $chromeDriverExe"
    Write-Host "Please make sure you have placed ChromeDriver there before running this script."
    exit 1
}

# 2. Retrieve your current user PATH
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")

# 3. If it's not already in PATH, add it
if ($userPath -notlike "*$chromeDriverDir*") {
    Write-Host "[INFO] Adding '$chromeDriverDir' to the user PATH..."
    $newPath = $userPath.TrimEnd(';') + ";" + $chromeDriverDir
    [System.Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "[SUCCESS] Successfully added ChromeDriver path to user PATH."
} else {
    Write-Host "[INFO] '$chromeDriverDir' is already in your user PATH. Skipping addition."
}

# 4. Update the *current* PowerShell session's PATH variable
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User")

# 5. Verify we can run ChromeDriver from that location
Write-Host "`nVerifying ChromeDriver installation..."
try {
    $versionOutput = & "$chromeDriverExe" --version
    Write-Host "[SUCCESS] ChromeDriver is working: $versionOutput"
    Write-Host "[SUCCESS] You can now use ChromeDriver in your scripts!"
}
catch {
    Write-Host "[WARNING] Could not run ChromeDriver in this session. Error details:"
    Write-Host "          $_"
    Write-Host "[INFO] You may need to open a *new* PowerShell or CMD window for the updated PATH."
}

Write-Host "`nDone."
