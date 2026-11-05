<#
.SYNOPSIS
    后端 CI 门禁的本地复现脚本:与 .github/workflows/backend-ci.yml 跑完全相同的命令。

.DESCRIPTION
    前置条件(和 CI 的 service 容器一致):
      cd backend && docker compose up -d      # mysql + redis 都起来
      .venv/Scripts/python.exe -m alembic upgrade head   # 首次或迁移后

    用法:
      pwsh backend/scripts/ci_check.ps1            # ruff + pytest(含覆盖率下限)
      pwsh backend/scripts/ci_check.ps1 -LintOnly  # 只跑 ruff(快速自检)
#>
[CmdletBinding()]
param(
    [switch]$LintOnly
)

$ErrorActionPreference = 'Stop'
$backendDir = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $backendDir

$python = Join-Path $backendDir '.venv/Scripts/python.exe'
if (-not (Test-Path $python)) {
    $python = 'python'
}

function Invoke-Step {
    param([string]$Name, [string[]]$Arguments)
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $python @Arguments
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Name (exit $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

# 1) lint:与 workflow 的 "Ruff lint" 步骤一致
Invoke-Step 'ruff check' @('-m', 'ruff', 'check', 'app', 'tests')

if ($LintOnly) {
    Write-Host 'OK (lint only)' -ForegroundColor Green
    exit 0
}

# 2) 测试 + 覆盖率下限:与 workflow 的 "Pytest + coverage gate" 步骤一致
Invoke-Step 'pytest' @(
    '-m', 'pytest', 'tests', '-q',
    '--cov=app', '--cov-report=term', '--cov-fail-under=60'
)

Write-Host 'OK: lint + tests passed' -ForegroundColor Green
exit 0
