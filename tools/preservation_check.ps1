param(
    [string]$PythonPath = "python"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$CheckExitCode = 1
$LogExitCode = 1

Push-Location $RepositoryRoot
try {
    & $PythonPath tools/preservation_manifest.py check-current
    $CheckExitCode = $LASTEXITCODE

    & $PythonPath tools/preservation_manifest.py verify-log
    $LogExitCode = $LASTEXITCODE
}
catch {
    [Console]::Error.WriteLine($_.ToString())
}
finally {
    Pop-Location
}

if ($CheckExitCode -ne 0) {
    exit $CheckExitCode
}
exit $LogExitCode
