# Push changes to GitHub fork
# Origin (fork):    https://github.com/aistuartai/dyness_battery_stu
# Upstream (source): https://github.com/shopf/dyness_battery

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$status = git status --porcelain
if (-not $status) {
    Write-Host "Nothing to commit — working tree clean."
    exit 0
}

git add custom_components push_to_fork.ps1 reset_fork.ps1

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "chore: Stu customisations [$timestamp]"
if ($LASTEXITCODE -ne 0) { Write-Error "git commit failed"; exit 1 }

git push origin main
if ($LASTEXITCODE -ne 0) { Write-Error "git push failed"; exit 1 }
Write-Host "Pushed to fork."
