param(
    [ValidateSet('fuyao_validation','fuyao','mock')][string]$FinancialProvider = 'fuyao_validation',
    [string]$Model = 'Qwen/Qwen3-8B',
    [ValidateRange(1024,65535)][int]$Port = 8767,
    [string]$Database = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
# Refresh known credentials from Windows user settings without echoing values.
# An existing process credential remains usable if not stored at user scope.
foreach ($credentialName in @('SILICONFLOW_API_KEY','HITHINK_FINANCE_API_KEY')) {
    $configuredCredential = [Environment]::GetEnvironmentVariable($credentialName,'User')
    if (-not [string]::IsNullOrWhiteSpace($configuredCredential)) {
        [Environment]::SetEnvironmentVariable($credentialName,$configuredCredential,'Process')
    }
}
if ([string]::IsNullOrWhiteSpace($env:SILICONFLOW_API_KEY)) {
    throw 'SILICONFLOW_API_KEY is missing. Save the Windows user environment variable first.'
}
$env:STRATEGYLENS_COMPILER = 'llm'
$env:STRATEGYLENS_LLM_PROVIDER = 'siliconflow'
$env:STRATEGYLENS_LLM_MODEL = $Model
$env:STRATEGYLENS_PROVIDER = $FinancialProvider
if ($Database) { $env:STRATEGYLENS_DB = $Database }
Push-Location -LiteralPath $projectRoot
try {
    Write-Host "Compiler: siliconflow / $Model; financial provider: $FinancialProvider"
    & (Join-Path $projectRoot '.venv\Scripts\python.exe') -m uvicorn app.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Local server exited with an error. Check whether the port is already in use.' }
} finally { Pop-Location }
