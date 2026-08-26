<#
    OME Report Analyst — синхронизация локального стейджинга на диск X, когда он доступен.
    Никогда не удаляет и не перезаписывает более новые файлы на X (нет /MIR).
    Направление одностороннее: StagingRoot -> TargetRoot.
#>

$StagingRoot = "C:\Users\vladislav.soldatov\OME_Coverage_Staging"
$TargetRoot  = "X:\Research\VS"
$LogFile     = Join-Path $StagingRoot "_sync-log.txt"

if (-not (Test-Path $StagingRoot)) {
    New-Item -ItemType Directory -Path $StagingRoot -Force | Out-Null
}

function Write-Log([string]$msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Add-Content -Path $LogFile -Value $line
}

if (-not (Test-Path $TargetRoot)) {
    Write-Log "Диск X недоступен ($TargetRoot) — пропуск."
    exit 0
}

$hasContent = Get-ChildItem -Path $StagingRoot -Directory -ErrorAction SilentlyContinue
if (-not $hasContent) {
    Write-Log "Стейджинг пуст — синхронизировать нечего."
    exit 0
}

robocopy $StagingRoot $TargetRoot /E /XO /R:1 /W:1 /NP /LOG+:$LogFile /TEE
$code = $LASTEXITCODE

if ($code -le 7) {
    Write-Log "Синхронизация выполнена, код robocopy = $code (0-7 = успех/нет изменений)."
} else {
    Write-Log "Синхронизация с ошибкой, код robocopy = $code — см. лог robocopy выше."
}
