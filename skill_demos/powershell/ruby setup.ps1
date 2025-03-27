# Ensure Chocolatey is installed
if (!(Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Chocolatey..."
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
} else {
    Write-Host "Chocolatey is already installed."
}

# Refresh environment variables to include Chocolatey
$env:Path += ";C:\ProgramData\chocolatey\bin"

# Check if Ruby is installed
if (!(Get-Command ruby -ErrorAction SilentlyContinue)) {
    Write-Host "Ruby not found. Installing Ruby..."
    choco install ruby -y
    Write-Host "Ruby installation complete."
} else {
    Write-Host "Ruby is already installed."
}

# Determine Ruby installation path (different versions may install differently)
$rubyPath = Get-ChildItem "C:\Ruby*" -Directory | Select-Object -ExpandProperty FullName | Where-Object { $_ -match "Ruby" }

# Ensure Ruby is in the system PATH
if ($rubyPath -and !(Test-Path "$rubyPath\bin\ruby.exe")) {
    Write-Host "Ruby installation path not found. Reinstalling Ruby..."
    choco uninstall ruby -y
    choco install ruby -y
}

# Add Ruby to PATH permanently (if not already added)
if ($env:Path -notmatch [regex]::Escape("$rubyPath\bin")) {
    Write-Host "Adding Ruby to system PATH..."
    [System.Environment]::SetEnvironmentVariable("Path", "$env:Path;$rubyPath\bin", [System.EnvironmentVariableTarget]::Machine)
}

# Refresh session to recognize Ruby
$env:Path += ";$rubyPath\bin"

# Verify Ruby installation
Write-Host "Verifying Ruby installation..."
$RubyInstalled = Get-Command ruby -ErrorAction SilentlyContinue
if ($RubyInstalled) {
    ruby -v
} else {
    Write-Host "Ruby installation failed. Please check manually."
    exit
}

# Install Bundler (for managing gems)
Write-Host "Installing Bundler..."
Start-Process "cmd.exe" -ArgumentList "/c gem install bundler --no-document" -Wait -NoNewWindow

# Install Ruby on Rails
Write-Host "Installing Rails..."
Start-Process "cmd.exe" -ArgumentList "/c gem install rails --no-document" -Wait -NoNewWindow

# Install API-related gems
Write-Host "Installing API-related libraries..."
Start-Process "cmd.exe" -ArgumentList "/c gem install sinatra grape rack json rest-client --no-document" -Wait -NoNewWindow

# Verify installations
Write-Host "Verifying installations..."
Write-Host "Ruby Version: $(ruby -v)"
Write-Host "Rails Version: $(rails -v)"
Write-Host "Installed Gems:"
Start-Process "cmd.exe" -ArgumentList "/c gem list sinatra grape rack json rest-client" -Wait -NoNewWindow

Write-Host "Installation complete! Ruby, Rails, and API libraries are ready."
