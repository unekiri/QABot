# QABot の結合テストを Docker で実行する。
# 前提: Docker Desktop が起動している / Ollama がホストで起動し gemma3:1b を pull 済み
# 結果は tests/integration-result.log にも保存される。
$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$log = Join-Path $PSScriptRoot 'integration-result.log'
Start-Transcript -Path $log -Force | Out-Null
$compose = @('-f', 'tests/integration.compose.yml', '-p', 'qabot-it')

function Step([string]$name, [scriptblock]$block) {
    Write-Host "`n===== $name" -ForegroundColor Cyan
    $global:LASTEXITCODE = 0
    & $block
    if ($LASTEXITCODE -ne 0) { throw "FAILED: $name (exit $LASTEXITCODE)" }
}

$failed = $false
try {
    Step 'Ollama reachable' { Invoke-RestMethod http://localhost:11434/api/tags -ErrorAction Stop | Out-Null }
    Step 'Build API image' { docker build --target runtime -t qabot-api:latest ./api }
    Step 'Build importer image' { docker build --target runtime -t qabot-importer:latest ./importer }
    Step 'Unit tests (in API image)' {
        docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v "${root}:/src:ro" -w /src qabot-api:latest python tests/regression.py
    }
    Step 'Clean previous run' { docker compose @compose down -v --remove-orphans }
    Step 'Start ChromaDB 0.5.23' { docker compose @compose up -d chroma }
    Start-Sleep -Seconds 10
    Step 'Importer integration (client 0.5.23 -> server 0.5.23)' { docker compose @compose run --rm importer }
    Step 'Start API and Nginx' { docker compose @compose up -d --build api nginx }
    Step 'API with real LLM' { docker compose @compose run --rm --no-deps --entrypoint python api /tests/integration_api.py }
    Start-Sleep -Seconds 30
    Step 'Hybrid search (part numbers)' { docker compose @compose run --rm --no-deps --entrypoint python importer /tests/integration_hybrid.py }
    Start-Sleep -Seconds 30
    Step 'Security' { docker compose @compose run --rm --no-deps --entrypoint python api /tests/integration_security.py }
    Step 'Stop ChromaDB' { docker compose @compose stop chroma }
    Start-Sleep -Seconds 60
    Step 'Internal error hidden' { docker compose @compose run --rm --no-deps --entrypoint python api /tests/integration_error.py }
    Write-Host "`nALL INTEGRATION TESTS PASSED" -ForegroundColor Green
}
catch {
    $failed = $true
    Write-Host "`n$($_.Exception.Message)" -ForegroundColor Red
    docker compose @compose logs --no-color --tail 80 api
}
finally {
    docker compose @compose down -v --remove-orphans | Out-Null
    Stop-Transcript | Out-Null
}
if ($failed) { exit 1 }
