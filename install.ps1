# Installs Kitden on Windows: uv when it is missing, then Kitden as a uv tool, then opens the page.
# One line:  powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/install.ps1 | iex"
# It never changes anything in Claude Code, Codex or Cursor.
$ErrorActionPreference = "Stop"

$KitdenRef = "v0.2.0"
$KitdenSource = "git+https://github.com/KonstantinStarovoytov/kitden@$KitdenRef"
$FollowUp = "https://github.com/KonstantinStarovoytov/kitden#linux-and-windows"

# 1. Windows support is a later feature. Steps 2 to 5 run once it lands.
$WindowsSupported = $false
if (-not $WindowsSupported) {
    Write-Host "Kitden runs on macOS today. Linux and Windows are coming: $FollowUp. Nothing was installed."
    exit 1
}

# 2. Find uv, or install it with uv's own installer.
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) {
    $uv = $uvCommand.Source
} else {
    $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (-not (Test-Path $uv)) {
        Write-Host "Installing uv..."
        try { irm https://astral.sh/uv/install.ps1 | iex } catch { }
        if (-not (Test-Path $uv)) {
            Write-Host "Could not install uv. See https://docs.astral.sh/uv/getting-started/installation/"
            exit 2
        }
    }
}

# 3. Install or update Kitden in its own environment.
Write-Host "Installing Kitden..."
& $uv tool install $KitdenSource
if ($LASTEXITCODE -ne 0) {
    Write-Host "Could not install Kitden. See the uv output above."
    exit 3
}

# 4. Open the page. The command returns at once and prints the link.
$bin = (& $uv tool dir --bin).Trim()
$kitden = Join-Path $bin "kitden.exe"
Write-Host "Opening the Kitden page..."
& $kitden
Write-Host "Kitden is installed: $kitden"

# 5. Say how to get the kitden command on PATH when it is not there yet.
if (($env:Path -split ";") -notcontains $bin) {
    Write-Host "To use the kitden command from any terminal, run: uv tool update-shell, then open a new terminal."
}
