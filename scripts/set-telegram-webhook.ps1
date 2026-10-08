param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^https://')]
    [string] $SiteUrl
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repositoryRoot '.env'

function Get-ProjectSecret([string] $Name) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ($value) {
        return $value.Trim()
    }
    if (-not (Test-Path -LiteralPath $envFile)) {
        return ''
    }
    $escaped = [Regex]::Escape($Name)
    $line = Get-Content -LiteralPath $envFile |
        Where-Object { $_ -match "^\s*$escaped\s*=" } |
        Select-Object -Last 1
    if (-not $line) {
        return ''
    }
    return (($line -split '=', 2)[1]).Trim().Trim('"').Trim("'")
}

$token = Get-ProjectSecret 'TELEGRAM_BOT_TOKEN'
$secret = Get-ProjectSecret 'TELEGRAM_WEBHOOK_SECRET'
if (-not $token) {
    throw 'TELEGRAM_BOT_TOKEN is missing from the process environment or root .env.'
}
if ($secret -notmatch '^[A-Za-z0-9_-]{1,256}$') {
    throw 'TELEGRAM_WEBHOOK_SECRET must contain 1-256 letters, numbers, underscores, or hyphens.'
}

$webhookUrl = $SiteUrl.TrimEnd('/') + '/api/telegram'
$body = @{
    url                  = $webhookUrl
    secret_token         = $secret
    allowed_updates      = @('message')
    drop_pending_updates = $true
} | ConvertTo-Json -Compress

$apiBase = "https://api.telegram.org/bot$token"
$result = Invoke-RestMethod -Method Post -Uri "$apiBase/setWebhook" -ContentType 'application/json' -Body $body
if (-not $result.ok) {
    throw "Telegram rejected setWebhook: $($result.description)"
}

$info = Invoke-RestMethod -Method Get -Uri "$apiBase/getWebhookInfo"
[PSCustomObject]@{
    configured          = $result.ok
    url                 = $info.result.url
    pending_update_count = $info.result.pending_update_count
    last_error_message  = $info.result.last_error_message
}
