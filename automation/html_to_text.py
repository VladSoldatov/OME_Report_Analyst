"""
Разбор сохранённого HTML в читаемый текст — с абзацами и таблицами,
а не сплошным потоком. Использовать, когда fetch_page.py (Playwright)
не смог подключиться к странице и пришлось скачать её обычным curl.

Использование:
    python html_to_text.py <input.html> <output.txt>
"""
import re
import sys
import html


def convert(input_path: str, output_path: str) -> None:
    with open(input_path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    content = re.sub(r"<script.*?</script>", "", content, flags=re.S)
    content = re.sub(r"<style.*?</style>", "", content, flags=re.S)

    # Жирный/курсив — в markdown-разметку ДО того, как теги пропадут, иначе
    # выделение важного (например, в буллетах пресс-релиза) теряется бесследно.
    content = re.sub(r"<(strong|b)\b[^>]*>(.*?)</\1>", r"**\2**", content, flags=re.I | re.S)
    content = re.sub(r"<(em|i)\b[^>]*>(.*?)</\1>", r"_\2_", content, flags=re.I | re.S)

    # Переносы строк — ДО того, как остальные теги превратятся в пустоту.
    # Именно это пропускалось раньше и давало "стену текста".
    # </li> — двойной перенос: пункты списка в источнике разделены ОДИНАРНЫМ
    # переносом, а не пустой строкой, и без этого все буллеты слипаются в один
    # абзац (перечисление визуально пропадает, даже когда список распознан).
    content = re.sub(r"</li\s*>", "\n\n", content, flags=re.I)
    content = re.sub(r"</(p|div|tr|h[1-6]|br)\s*>", "\n", content, flags=re.I)
    content = re.sub(r"<br\s*/?>", "\n", content, flags=re.I)
    content = re.sub(r"<td[^>]*>", "\t", content, flags=re.I)

    text = re.sub(r"<[^>]+>", "", content)
    text = html.unescape(text)
    # Схлопывать только ПРОБЕЛЫ — таб нарочно расставлен как разделитель колонок
    # таблицы на предыдущем шаге, схлопывать его в пробел — терять всю таблицу.
    text = re.sub(r"[ ]{2,}", " ", text)
    text = "\n".join(line.strip("\r\n ") for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text.strip())

    print(f"OK: {len(text)} chars -> {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python html_to_text.py <input.html> <output.txt>")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
