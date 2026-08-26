<#
    Обёртка для запуска Claude Code без участия человека (Планировщик задач).
    - Пишет полный вывод в лог-файл через Start-Process (прямая запись байтов в файл,
      в обход перехвата вывода через переменную PowerShell — там на этой машине
      обнаружился обрыв кириллицы после первых ASCII-символов).
    - Если в ответе встречается "⚠️" (конвенция эскалации из agent/escalation.md) — пытается показать
      уведомление через встроенный msg.exe (без сторонних модулей). Если и это не сработает — эскалация
      всё равно останется явной строкой в логе, ничего не потеряется.
#>
param(
    [string]$PromptFile = "C:\Users\vladislav.soldatov\OME_Report_Analyst-1\automation\test-heartbeat-prompt.txt",
    [string]$WorkDir = "C:\Users\vladislav.soldatov\OME_Report_Analyst-1",
    [string]$LogDir = "C:\Users\vladislav.soldatov\OME_Coverage_Staging\_task-logs"
)

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

$claudeCmd = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claudeCmd) {
    "claude executable not found in PATH for this process context." | Out-File -FilePath (Join-Path $LogDir "run-error.log") -Append -Encoding utf8
    exit 1
}

$stamp     = Get-Date -Format "yyyyMMdd-HHmmss"
$logFile   = Join-Path $LogDir "run-$stamp.log"
$stdoutTmp = Join-Path $LogDir "run-$stamp.stdout.txt"
$stderrTmp = Join-Path $LogDir "run-$stamp.stderr.txt"
$prompt    = Get-Content -Raw -Path $PromptFile -Encoding UTF8

$argList = @(
    '-p', $prompt,
    '--add-dir', 'X:\Research\VS',
    '--add-dir', "$env:USERPROFILE\Desktop",
    '--allowedTools', 'Read,Write,Edit,Bash,WebSearch,WebFetch',
    '--permission-mode', 'dontAsk',
    '--output-format', 'text'
)

Push-Location $WorkDir
try {
    $proc = Start-Process -FilePath $claudeCmd -ArgumentList $argList -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $stdoutTmp -RedirectStandardError $stderrTmp
    $exitCode = $proc.ExitCode
} finally {
    Pop-Location
}

$stdoutText = Get-Content -Raw -Path $stdoutTmp -Encoding UTF8 -ErrorAction SilentlyContinue
$stderrText = Get-Content -Raw -Path $stderrTmp -Encoding UTF8 -ErrorAction SilentlyContinue

$logBody = @"
=== $stamp === exit code: $exitCode ===
--- stdout ---
$stdoutText
--- stderr ---
$stderrText
"@
[System.IO.File]::WriteAllText($logFile, $logBody, [System.Text.Encoding]::UTF8)
Remove-Item $stdoutTmp, $stderrTmp -ErrorAction SilentlyContinue

if ($stdoutText -match "⚠️") {
    $msg = "OME агент: нужно твоё решение. Смотри $logFile"
    try {
        & msg.exe $env:USERNAME $msg 2>&1 | Out-Null
        Add-Content -Path $logFile -Value "`n[уведомление: msg.exe отправлен]" -Encoding utf8
    } catch {
        Add-Content -Path $logFile -Value "`n[уведомление НЕ отправлено: $($_.Exception.Message)]" -Encoding utf8
    }
}
