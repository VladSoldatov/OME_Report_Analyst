"""
Надёжное получение страницы через реальный headless-браузер (Playwright/Chromium),
в обход ограничений WebFetch (который только пересказывает контент) и мягких
JS-проверок вроде Cloudflare "Just a moment..." (curl их не проходит, настоящий
браузер — как правило да).

Использование:
    python fetch_page.py <url> <output_prefix>

Создаёт:
    <output_prefix>.pdf   — PDF-снимок страницы как она выглядит в браузере
    <output_prefix>.txt   — извлечённый текст страницы (после полной отрисовки JS)
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright


def fetch(url: str, output_prefix: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        )
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # "load"/"networkidle" на страницах с тяжёлой рекламой/трекерами (PRNewswire и
        # похожие) могут не срабатывать вовсе — domcontentloaded надёжнее как база.

        # Cloudflare-подобные JS-проверки обычно решаются за несколько секунд —
        # даём странице немного времени и проверяем, не застряли ли на заглушке.
        page.wait_for_timeout(3000)
        title = page.title()
        if "just a moment" in title.lower() or "attention required" in title.lower():
            page.wait_for_timeout(7000)

        pdf_path = f"{output_prefix}.pdf"
        page.pdf(path=pdf_path, format="A4", print_background=True)

        text = page.inner_text("body")
        txt_path = f"{output_prefix}.txt"
        Path(txt_path).write_text(text, encoding="utf-8")

        print(f"OK title={page.title()!r}")
        print(f"saved: {pdf_path}")
        print(f"saved: {txt_path} ({len(text)} chars)")

        browser.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python fetch_page.py <url> <output_prefix>")
        sys.exit(1)
    fetch(sys.argv[1], sys.argv[2])
