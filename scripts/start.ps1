param(
    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$User = 'qabot'
)

$securePassword = Read-Host 'QABot password (minimum 12 characters)' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)

try {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    if ($plainPassword.Length -lt 12) {
        throw 'Password must contain at least 12 characters.'
    }

    $env:QABOT_AUTH_USER = $User
    $env:QABOT_AUTH_PASSWORD = $plainPassword
    docker compose up -d --build
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed with exit code $LASTEXITCODE."
    }
}
finally {
    Remove-Item Env:QABOT_AUTH_USER -ErrorAction SilentlyContinue
    Remove-Item Env:QABOT_AUTH_PASSWORD -ErrorAction SilentlyContinue
    $plainPassword = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
}
