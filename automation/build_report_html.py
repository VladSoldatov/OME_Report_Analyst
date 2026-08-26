"""
Собирает единый HTML-файл "OME Report" — комментарий + пресс-релиз + транскрипт
на трёх вкладках, для локального чтения в браузере (не публикуется никуда).

Использование — см. функцию build() ниже, вызывать из Python напрямую
(комментарий собирается как HTML-таблица + текст, не только из markdown-файла).

Формат назван "OME Report". Имя файла-результата: "<Тикер> <квартал> - отчёт.html".
"""
import html
import re


ACCENT = "#1B2A6B"  # тот же тёмно-синий, что в существующих PPTX-материалах

# Мусор со страниц-источников (реклама, промо, виджеты котировок) — не часть
# ни самого звонка, ни саммари из первоисточника, поэтому вырезается при показе.
NOISE_PATTERNS = [
    r"^advertisement$",
    r"investingpro",
    r"follow\b.{0,20}analyze\b",
    r"real-time data",
    r"^most popular articles",
    r"included in our ai-picked strategies",
    r"review strategies",
    r"^\d{1,2}:\d{2}:\d{2}$",
    r"^(1D|1W|1M|6M|1Y|5Y|Max)(\s+(1D|1W|1M|6M|1Y|5Y|Max))*$",
    r"sign in",
    r"sign up",
    r"\d+%\s*off",
    r"discover today.?s top-performing stocks",
    r"see the list",
    r"^in this article:?$",
    r"^©\s*\w+$",
    r"^published\s+\d{1,2}/\d{1,2}/\d{2,4}",
    r"^markets$",
    r"^my watchlist$",
    r"^breaking news$",
    r"^stock screener$",
]
_noise_re = re.compile("|".join(NOISE_PATTERNS), re.I)

# Виджет котировки (тикер + мини-график) внедрён в тело статьи целиком одним
# блоком — если блок содержит несколько таких сигналов сразу, это виджет,
# даже если по отдельности каждая строка выглядит безобидно.
_WIDGET_SIGNALS_RE = re.compile(
    r"real-time data|analyze\b|review strategies|included in our ai-picked", re.I
)


def is_widget_block(block: str) -> bool:
    lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
    if len(lines) < 4:
        return False
    hits = sum(1 for ln in lines if _WIDGET_SIGNALS_RE.search(ln))
    short_numeric = sum(1 for ln in lines if re.match(r"^[\d.,▲▼+\-%() ]+$", ln))
    return hits >= 1 and short_numeric >= 3

# Шапка сайта (меню/промо/виджет котировки) перед реальным лид-абзацем статьи —
# короткие строки-чипы (пункты меню, бейджи), настоящий текст — длинные абзацы.
_MIN_REAL_PARAGRAPH = 120

# Стандартные заголовки секций в саммари investing.com/аналогичных сайтов —
# рендерим как <h3>, а не как обычный абзац, иначе структура текста теряется.
KNOWN_HEADERS = {
    "key takeaways", "company performance", "financial highlights",
    "earnings vs. forecast", "earnings vs forecast", "market reaction",
    "outlook & guidance", "outlook and guidance", "executive commentary",
    "risks and challenges", "q&a", "operational highlights",
    "major developments", "future developments", "strategic developments",
}
# Заголовки, за которыми в источнике идёт перечисление (буллеты) —
# оборачиваем последующие блоки в <ul><li>, пока не встретим следующий заголовок.
KNOWN_LIST_HEADERS = {"key takeaways", "risks and challenges", "financial highlights"}
_FULL_TRANSCRIPT_RE = re.compile(r"^full transcript\b", re.I)


def is_noise(block: str) -> bool:
    b = block.strip()
    if not b:
        return True
    if _noise_re.search(b):
        return True
    return is_widget_block(b)


def is_table_block(block: str) -> bool:
    lines = block.split("\n")
    tabbed = [ln for ln in lines if "\t" in ln]
    return len(lines) >= 2 and len(tabbed) >= len(lines) - 1


_table_seq = [0]


def _clean_cell(c: str) -> str:
    return c.replace("\xa0", " ").strip()


_TOTAL_ROW_RE = re.compile(
    r"^(total\b|net (loss|income|cash)\b|adjusted ebitda\b|ebitda\b)", re.I
)


def _merge_currency_cells(row):
    """"$" и следующая ячейка ("54.6") — одно значение, не две колонки."""
    out = []
    i = 0
    while i < len(row):
        if row[i] in ("$", "€", "£") and i + 1 < len(row):
            out.append(row[i] + row[i + 1])
            i += 2
        else:
            out.append(row[i])
            i += 1
    return out


def table_block_html(block: str) -> str:
    raw_rows = [ln.split("\t") for ln in block.split("\n") if ln.strip()]
    # Источник часто вставляет пустые &nbsp;-ячейки только для визуального отступа —
    # без реального значения. Дропаем такие ячейки построчно, иначе в таблице
    # появляется куча пустых колонок вместо реальных данных.
    rows = []
    for r in raw_rows:
        cleaned = [_clean_cell(c) for c in r]
        cleaned = [c for c in cleaned if c != ""]
        cleaned = _merge_currency_cells(cleaned)
        if cleaned:
            rows.append(cleaned)
    if not rows:
        return ""
    max_cols = max(len(r) for r in rows)

    # Заголовок с colspan в оригинале после очистки часто короче настоящих
    # колонок (напр. "Three Months Ended / Six Months Ended" — 2 ячейки на 7
    # колонок) — берём как надзаголовок-подпись, а не как <th>-строку; реальный
    # заголовок — следующая строка, если она уже покрывает все колонки.
    caption = None
    if len(rows) >= 2 and len(rows[0]) < max_cols and len(rows[1]) == max_cols:
        caption = rows[0]
        rows = rows[1:]

    rows = [r + [""] * (max_cols - len(r)) for r in rows]
    head, *body = rows
    _table_seq[0] += 1
    tid = f"tbl-{_table_seq[0]}"
    out = ['<div class="table-wrap">',
           f'<button class="copy-btn" onclick="copyTable(\'{tid}\', this)">📋 Копировать в Excel</button>']
    if caption:
        out.append(f'<div class="table-caption">{html.escape(" · ".join(caption))}</div>')
    out += [f'<table id="{tid}">', "<tr>"]
    out += [f"<th>{html.escape(c)}</th>" for c in head]
    out.append("</tr>")
    for r in body:
        row_cls = ' class="row-total"' if r and _TOTAL_ROW_RE.match(r[0]) else ""
        out.append(f"<tr{row_cls}>")
        out += [f"<td>{html.escape(c)}</td>" for c in r]
        out.append("</tr>")
    out.append("</table>")
    out.append("</div>")
    return "\n".join(out)


_MD_TABLE_SEP_RE = re.compile(r"^:?-+:?$")


def markdown_tables_to_tabsep(text: str) -> str:
    """PDF-источники (через Read-тул) часто дают готовые markdown-таблицы
    (| a | b |) — конвертируем в тот же таб-разделённый формат, что и
    HTML-таблицы, чтобы дальше работал один и тот же table_block_html
    (копирование в Excel, подсветка Total-строк и т.д.)."""
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            rows = []
            for tl in table_lines:
                cells = [c.strip() for c in tl.strip().strip("|").split("|")]
                if all(_MD_TABLE_SEP_RE.match(c) for c in cells if c) and any(cells):
                    continue
                rows.append("\t".join(cells))
            out.append("\n".join(rows))
            out.append("")
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def paragraphs_html(text: str, bold_speakers: bool = False) -> str:
    blocks = [b.strip("\n") for b in re.split(r"\n\s*\n", text) if b.strip()]
    out = []
    speaker_re = re.compile(r"^([A-Z][\w'.\- ]{2,60}?,\s[^:]{2,80}?)\s?:\s(.*)$", re.S)

    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for b in blocks:
        if is_noise(b):
            continue
        stripped = b.strip()

        first_line = stripped.split("\n", 1)[0].strip()
        rest_after_header = stripped[len(first_line):].strip()
        header_hit = (
            stripped.lower() in KNOWN_HEADERS
            or first_line.lower() in KNOWN_HEADERS
            or _FULL_TRANSCRIPT_RE.match(first_line)
        )
        if header_hit:
            close_list()
            # Заголовок иногда склеен с посторонним хвостом (напр. "Advertisement")
            # без пустой строки между ними — рендерим только сам заголовок,
            # хвост либо отбрасываем как шум, либо выводим отдельным абзацем.
            header_text = first_line if first_line.lower() in KNOWN_HEADERS or _FULL_TRANSCRIPT_RE.match(first_line) else stripped
            out.append(f"<h3>{html.escape(header_text)}</h3>")
            in_list = header_text.lower() in KNOWN_LIST_HEADERS
            if in_list:
                out.append("<ul>")
            if rest_after_header and not is_noise(rest_after_header):
                out.append(f"<p>{inline_md(rest_after_header)}</p>")
            continue

        if is_table_block(b):
            close_list()
            out.append(table_block_html(b))
            continue

        # Заголовок/преамбула иногда склеены с самой таблицей в один блок без
        # пустой строки между ними — ищем, с какой строки реально начинаются
        # табличные (табулированные) строки и идут без перерыва до конца блока.
        lines = b.split("\n")
        tab_lines = [i for i, ln in enumerate(lines) if "\t" in ln]
        if tab_lines:
            cut = tab_lines[0]
            tail_lines = lines[cut:]
            if cut > 0 and len(tail_lines) >= 2 and all("\t" in ln for ln in tail_lines):
                close_list()
                head = "\n".join(lines[:cut]).strip()
                tail = "\n".join(tail_lines)
                if head and not is_noise(head):
                    out.append(f"<p>{inline_md(head)}</p>")
                out.append(table_block_html(tail))
                continue

        b_esc = inline_md(stripped)
        if bold_speakers:
            m = speaker_re.match(b_esc)
            if m:
                close_list()
                out.append(
                    f'<p><span class="speaker">{m.group(1)}:</span> {m.group(2)}</p>'
                )
                continue

        if in_list:
            # Источник иногда разделяет пункты списка одинарным переносом
            # (не пустой строкой) — блок целиком выглядит как один пункт.
            # Раз мы уже знаем, что это список (после заголовка из
            # KNOWN_LIST_HEADERS) — дробим построчно на реальные пункты.
            items = [ln.strip() for ln in stripped.split("\n") if ln.strip() and not is_noise(ln)]
            for item in items:
                out.append(f"<li>{inline_md(item)}</li>")
        else:
            out.append(f"<p>{b_esc}</p>")

    close_list()
    return "\n".join(out)


def trim_transcript(text: str) -> str:
    """Оставляет саммари сайта (если есть) + сам транскрипт; отрезает шапку
    сайта в начале (меню/промо/виджет котировки) и подвал/диск в конце."""
    end_markers = ["This article was generated", "generated with the support of AI"]
    end = len(text)
    for m in end_markers:
        i = text.find(m)
        if i != -1:
            end = min(end, i)
    text = text[:end]

    # Шапка сайта — короткие строки-чипы; ищем первый блок, который похож на
    # настоящий текст статьи (длинный абзац), и отрезаем всё до него.
    blocks = [b for b in re.split(r"\n\s*\n", text)]
    start_idx = 0
    for i, b in enumerate(blocks):
        clean = b.strip()
        if len(clean) >= _MIN_REAL_PARAGRAPH and not is_noise(clean):
            start_idx = i
            break
    text = "\n\n".join(blocks[start_idx:])
    return text.strip()


def markdown_lite_html(text: str) -> str:
    lines = text.split("\n")
    html_out = []
    in_list = False
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            if in_list:
                html_out.append("</ul>")
                in_list = False
            continue
        if line_stripped.startswith("## "):
            if in_list:
                html_out.append("</ul>"); in_list = False
            html_out.append(f"<h2>{html.escape(line_stripped[3:])}</h2>")
        elif line_stripped.startswith("# "):
            if in_list:
                html_out.append("</ul>"); in_list = False
            html_out.append(f"<h1>{html.escape(line_stripped[2:])}</h1>")
        elif line_stripped.startswith("- "):
            if not in_list:
                html_out.append("<ul>"); in_list = True
            html_out.append(f"<li>{inline_md(line_stripped[2:])}</li>")
        else:
            if in_list:
                html_out.append("</ul>"); in_list = False
            html_out.append(f"<p>{inline_md(line_stripped)}</p>")
    if in_list:
        html_out.append("</ul>")
    return "\n".join(html_out)


def inline_md(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def metric_row(label, current, vs_consensus, prior_q, year_ago, yoy_growth=None):
    """Одна метрика earnings-review таблицы + опциональная строка 'рост г/г'."""
    def growth_cls(g):
        if g is None or g in ("", "н/д", "--"):
            return ""
        return "up" if str(g).strip().startswith("+") else ("down" if str(g).strip().startswith("-") else "")

    rows = [
        f"<tr><td>{html.escape(label)}</td>"
        f"<td class=\"num\">{html.escape(str(current))}</td>"
        f"<td class=\"num {growth_cls(vs_consensus)}\">{html.escape(str(vs_consensus))}</td>"
        f"<td class=\"num\">{html.escape(str(current))}</td>"
        f"<td class=\"num\">{html.escape(str(prior_q))}</td>"
        f"<td class=\"num\">{html.escape(str(year_ago))}</td></tr>"
    ]
    if yoy_growth is not None:
        rows.append(
            f"<tr class=\"growth-row\"><td></td><td></td><td></td><td></td><td></td>"
            f"<td class=\"num {growth_cls(yoy_growth)}\">{html.escape(str(yoy_growth))}</td></tr>"
        )
    return "\n".join(rows)


def earnings_review_table(rows_html: str, quarter_label: str, prior_label: str, year_ago_label: str,
                           consensus_note: str = "") -> str:
    _table_seq[0] += 1
    tid = f"tbl-{_table_seq[0]}"
    note = f'<div class="doc-note">{html.escape(consensus_note)}</div>' if consensus_note else ""
    return f"""
{note}
<div class="table-wrap">
<button class="copy-btn" onclick="copyTable('{tid}', this)">📋 Копировать в Excel</button>
<table id="{tid}" class="earnings-review">
<tr><th>Метрика</th><th>Факт</th><th>% сюрприз (BBG)</th><th>{html.escape(quarter_label)}</th><th>{html.escape(prior_label)}</th><th>{html.escape(year_ago_label)}</th></tr>
{rows_html}
</table>
</div>
"""


PAGE_TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{ticker} {quarter} — отчёт</title>
<style>
  :root {{
    --accent: {accent};
    --bg: #fafaf8;
    --panel: #ffffff;
    --text: #1a1a1a;
    --muted: #6b7280;
    --border: #e5e5e0;
    --up: #1a8a4a;
    --down: #c0392b;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #14151a;
      --panel: #1c1e26;
      --text: #e8e8ea;
      --muted: #9a9aa5;
      --border: #2c2e38;
      --up: #3ec478;
      --down: #e0584a;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0;
    background: var(--bg); color: var(--text);
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  header {{
    padding: 28px 32px 20px; border-bottom: 1px solid var(--border);
    background: var(--panel);
  }}
  header .ticker {{
    display: inline-block; background: var(--accent); color: #fff;
    font-weight: 700; font-size: 13px; letter-spacing: .04em;
    padding: 3px 10px; border-radius: 4px; margin-bottom: 10px;
  }}
  header h1 {{ margin: 0 0 4px; font-size: 22px; }}
  header .meta {{ color: var(--muted); font-size: 13px; }}
  nav.tabs {{
    display: flex; gap: 4px; padding: 0 32px; background: var(--panel);
    border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10;
  }}
  nav.tabs button {{
    appearance: none; border: none; background: transparent; color: var(--muted);
    font-size: 14px; font-weight: 600; padding: 14px 18px; cursor: pointer;
    border-bottom: 2px solid transparent; font-family: inherit;
  }}
  nav.tabs button.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
  main {{ max-width: 820px; margin: 0 auto; padding: 32px; }}
  .tabpanel {{ display: none; }}
  .tabpanel.active {{ display: block; }}
  h1, h2, h3 {{ line-height: 1.3; }}
  h2 {{ font-size: 17px; margin: 28px 0 10px; color: var(--accent); }}
  h3 {{
    font-size: 13px; margin: 26px 0 10px; color: var(--accent); text-transform: uppercase;
    letter-spacing: .04em; border-bottom: 1px solid var(--border); padding-bottom: 6px;
  }}
  p {{ line-height: 1.65; font-size: 15px; margin: 0 0 14px; }}
  ul {{ padding-left: 20px; }}
  li {{ line-height: 1.6; font-size: 15px; margin-bottom: 6px; }}
  strong {{ font-weight: 700; }}
  code {{ background: var(--border); padding: 1px 5px; border-radius: 3px; font-size: 13px; }}
  .speaker {{ color: var(--accent); font-weight: 700; }}
  .source-link {{
    display: inline-block; margin-bottom: 16px; font-size: 13px;
  }}
  .source-link a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
  .source-link a:hover {{ text-decoration: underline; }}
  .table-wrap {{ position: relative; margin: 12px 0 22px; }}
  .copy-btn {{
    position: absolute; top: -30px; right: 0; font-size: 12px; font-family: inherit;
    background: var(--panel); color: var(--accent); border: 1px solid var(--border);
    border-radius: 5px; padding: 4px 9px; cursor: pointer;
  }}
  .copy-btn:hover {{ border-color: var(--accent); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{ padding: 7px 10px; border-bottom: 1px solid var(--border); text-align: right; font-variant-numeric: tabular-nums; }}
  th:first-child, td:first-child {{ text-align: left; font-variant-numeric: normal; }}
  th {{ color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; }}
  tr:nth-child(even) td {{ background: color-mix(in srgb, var(--border) 35%, transparent); }}
  tr.row-total td {{ font-weight: 700; border-top: 1px solid var(--muted); }}
  .table-caption {{ font-size: 12px; color: var(--muted); font-style: italic; margin: 8px 0 -6px; }}
  td.up {{ color: var(--up); font-weight: 600; }}
  td.down {{ color: var(--down); font-weight: 600; }}
  tr.growth-row td {{ font-style: italic; font-size: 13px; border-bottom: 1px solid var(--border); padding-top: 0; background: none; }}
  table.earnings-review {{ margin-top: 6px; }}
  table.earnings-review tr:nth-child(even) td {{ background: none; }}
  .sources {{ font-size: 13px; color: var(--muted); margin-top: 30px; }}
  .sources a {{ color: var(--accent); }}
  .doc-note {{
    font-size: 13px; color: var(--muted); background: var(--panel);
    border: 1px solid var(--border); border-radius: 6px; padding: 10px 14px; margin-bottom: 16px;
  }}
  .pdf-frame {{ width: 100%; height: 85vh; border: 1px solid var(--border); border-radius: 8px; }}
  .pdf-fallback {{ font-size: 13px; margin-top: 10px; }}
  .pdf-fallback a {{ color: var(--accent); }}
  .pill-toggle {{
    display: inline-flex; background: var(--border); border-radius: 8px; padding: 3px;
    margin: 18px 0 20px; gap: 2px;
  }}
  .pill-toggle button {{
    appearance: none; border: none; background: transparent; color: var(--muted);
    font-size: 13px; font-weight: 600; padding: 7px 14px; border-radius: 6px;
    cursor: pointer; font-family: inherit;
  }}
  .pill-toggle button.active {{ background: var(--panel); color: var(--accent); }}
  .subpanel {{ display: none; }}
  .subpanel.active {{ display: block; }}
</style>
</head>
<body>
<header>
  <span class="ticker">{ticker}</span>
  <h1>{company_name}</h1>
  <div class="meta">{quarter} · {date_label}</div>
</header>
<nav class="tabs">
  <button class="active" data-tab="comment">Комментарий</button>
  <button data-tab="release">Пресс-релиз</button>
  <button data-tab="transcript">Транскрипт</button>
  {presentation_tab_button}
</nav>
<main>
  <section id="comment" class="tabpanel active">
    {earnings_table_html}
    <div class="pill-toggle">
      <button class="active" data-sub="pub">Публикация</button>
      <button data-sub="process">Как собран</button>
    </div>
    <div id="pub" class="subpanel active">
      {publication_html}
    </div>
    <div id="process" class="subpanel">
      {commentary_html}
    </div>
  </section>
  <section id="release" class="tabpanel">
    <div class="source-link">Источник: <a href="{release_url}" target="_blank" rel="noopener">{release_url}</a></div>
    {release_html}
  </section>
  <section id="transcript" class="tabpanel">
    <div class="source-link">Источник: <a href="{transcript_url}" target="_blank" rel="noopener">{transcript_url}</a></div>
    {transcript_html}
  </section>
  {presentation_section}
</main>
<script>
  document.querySelectorAll('nav.tabs button').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('nav.tabs button').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tabpanel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
      window.scrollTo(0, 0);
    }});
  }});

  document.querySelectorAll('.pill-toggle button').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.pill-toggle button').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.subpanel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.sub).classList.add('active');
    }});
  }});

  function copyTable(tableId, btn) {{
    const table = document.getElementById(tableId);
    const tsv = Array.from(table.querySelectorAll('tr')).map(tr =>
      Array.from(tr.querySelectorAll('th,td')).map(c => c.textContent.trim()).join('\\t')
    ).join('\\n');
    const ta = document.createElement('textarea');
    ta.value = tsv;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {{ document.execCommand('copy'); }} catch (e) {{}}
    document.body.removeChild(ta);
    const orig = btn.textContent;
    btn.textContent = 'Скопировано ✓';
    setTimeout(() => {{ btn.textContent = orig; }}, 1500);
  }}
</script>
</body>
</html>
"""


def build(ticker, company_name, quarter, date_label, publication_path, commentary_path,
          release_path, transcript_path, release_url, transcript_url, earnings_rows_html,
          prior_label, year_ago_label, consensus_note, output_path, presentation_pdf=None):
    """
    publication_path — готовый к публикации комментарий (дом. стиль, см.
        examples/report-style-templates.md), markdown.
    commentary_path — рабочие заметки: как собран комментарий, расхождения,
        что не проверено (то, что раньше было единственной версией).
    presentation_pdf — путь к PDF инвесторской презентации ОТНОСИТЕЛЬНО папки,
        где лежит output_path (напр. "Отчеты + презы/XE presentation 2Q26.pdf").
        Показывается как есть, оригиналом, во вкладке "Презентация" — не
        пересобирается в текст. None/не передан — вкладка не добавляется.
    """
    with open(publication_path, encoding="utf-8") as f:
        publication_md = f.read()
    with open(commentary_path, encoding="utf-8") as f:
        commentary_md = f.read()
    with open(release_path, encoding="utf-8") as f:
        release_text = f.read()
    with open(transcript_path, encoding="utf-8") as f:
        transcript_text = trim_transcript(f.read())

    earnings_table_html = earnings_review_table(
        earnings_rows_html, quarter, prior_label, year_ago_label, consensus_note
    )

    if presentation_pdf:
        pdf_href = html.escape(presentation_pdf)
        presentation_tab_button = '<button data-tab="presentation">Презентация</button>'
        presentation_section = f'''
  <section id="presentation" class="tabpanel">
    <div class="source-link"><a href="{pdf_href}" target="_blank" rel="noopener">Открыть PDF в отдельной вкладке ↗</a></div>
    <iframe class="pdf-frame" src="{pdf_href}"></iframe>
    <div class="pdf-fallback">Если PDF не отобразился встроенно — используйте ссылку выше. Файл — оригинал, как опубликован компанией, без обработки.</div>
  </section>'''
    else:
        presentation_tab_button = ""
        presentation_section = ""

    page = PAGE_TEMPLATE.format(
        ticker=ticker,
        company_name=html.escape(company_name),
        quarter=html.escape(quarter),
        date_label=html.escape(date_label),
        accent=ACCENT,
        earnings_table_html=earnings_table_html,
        publication_html=markdown_lite_html(publication_md),
        commentary_html=markdown_lite_html(commentary_md),
        release_html=paragraphs_html(markdown_tables_to_tabsep(release_text)),
        transcript_html=paragraphs_html(transcript_text, bold_speakers=True),
        release_url=html.escape(release_url),
        transcript_url=html.escape(transcript_url),
        presentation_tab_button=presentation_tab_button,
        presentation_section=presentation_section,
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"OK -> {output_path}")
