$ErrorActionPreference = 'Stop'

function Invoke-Git {
    param([string[]]$GitArguments)

    & git @GitArguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArguments -join ' ') failed with exit code $LASTEXITCODE."
    }
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$vendorPath = Join-Path $repositoryRoot 'vendor'
$checkoutPath = Join-Path $vendorPath 'cacheus'
$repositoryUrl = 'https://github.com/sylab/cacheus.git'
$commit = '1eec63ce166502be33ddd1f35bc041ed73a24f4d'

New-Item -ItemType Directory -Path $vendorPath -Force | Out-Null

if (Test-Path (Join-Path $checkoutPath '.git')) {
    Invoke-Git -GitArguments @('-C', $checkoutPath, 'remote', 'set-url', 'origin', $repositoryUrl)
    Invoke-Git -GitArguments @('-C', $checkoutPath, 'fetch', '-q', 'origin')
} else {
    Invoke-Git -GitArguments @('clone', '-q', $repositoryUrl, $checkoutPath)
}

Invoke-Git -GitArguments @('-C', $checkoutPath, 'checkout', '-q', $commit)
Write-Output "vendor/cacheus -> $commit"