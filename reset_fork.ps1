# Reset fork to match upstream exactly, wiping all previous fork history.
# Run this once to clean up the fork after a bad force-push.
#
# WARNING: This rewrites the fork's history. Any commits on the fork
# that aren't in upstream will be permanently lost.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Fetching latest upstream..."
git fetch upstream

Write-Host "Resetting local main to upstream/main..."
git checkout main
git reset --hard upstream/main

Write-Host "Force-pushing clean history to fork..."
git push origin main --force

Write-Host ""
Write-Host "Done. Fork is now in sync with upstream."
Write-Host "Run push_to_fork.ps1 after applying your customisations."
