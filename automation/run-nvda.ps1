<#
    Тонкий диспетчер для одноразового прогона по NVDA (2К FY27) — 27 августа 2026, 02:30 мск.
    Нужен отдельным файлом, чтобы командная строка Планировщика задач (/tr) не упёрлась
    в лимит 261 символ при передаче -PromptFile напрямую.
#>
& "C:\Users\vladislav.soldatov\OME_Report_Analyst-1\automation\run-claude-task.ps1" `
    -PromptFile "C:\Users\vladislav.soldatov\OME_Report_Analyst-1\automation\nvda-2q27-prompt.txt"
