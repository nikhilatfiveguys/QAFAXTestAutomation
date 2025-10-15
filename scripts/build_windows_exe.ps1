param(
    [string]$Python = "python"
)

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$specPath = Resolve-Path (Join-Path $PSScriptRoot "qafax_desktop.spec")
$command = @(
    $Python, "-m", "PyInstaller",
    "--clean",
    "--noconfirm",
    $specPath
)

Write-Host "Running" ($command -join " ")
& $Python -m PyInstaller --clean --noconfirm $specPath
