param(
    [string]$Python = "python"
)

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$command = @(
    $Python, "-m", "PyInstaller",
    "--clean",
    "--noconfirm",
    "--name", "QAFAXDesktop",
    "--windowed",
    "--add-data", "config;config",
    "--add-data", "docs;docs",
    "app\\ui\\__main__.py"
)

Write-Host "Running" ($command -join " ")
& $Python -m PyInstaller --clean --noconfirm --name QAFAXDesktop --windowed \
    --add-data "config;config" \
    --add-data "docs;docs" \
    app\\ui\\__main__.py
