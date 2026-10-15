# Сборка HTML-читалки конспектов (один файл, работает офлайн, открывается на телефоне).
#
#   python scripts/build_html.py "<корень>/<Предмет>"       -> <корень>/Конспекты/<Предмет>.html
#   python scripts/build_html.py --all "<корень>"            -> каждый готовый предмет
#                                                               + <корень>/Конспекты/Все предметы.html
#   python scripts/build_html.py "demo/Основы Python" --out demo/demo.html
# Опции:
#   --check            только проверка вопросов (объёмы, число предложений в «Кратко»), без записи файлов
#   --out <файл>       для одного предмета: куда записать HTML (вместо <корень>/Конспекты/<Предмет>.html)
#   --min-full N       порог «Подробно короткий» для --check, знаков (по умолчанию 2500)
#   --webfonts         подключить шрифты Literata / Old Standard TT из Google Fonts (по умолчанию — только системные)
#   --kratko           дополнительно версия без «Подробно»: «<Предмет> (кратко).html»
#   --artifact <файл>  дополнительно вариант для публикации как Artifact (без <html>/<head>/<body>)
#   --title "<имя>"    заголовок общего файла (по умолчанию «Конспекты к сессии»)
#   --only "А,Б"       с --all: в общий файл только названные предметы (по которым зачёт в эту сессию)
#   <корень>/_Сессия.md если есть — табло сессии: | Папка | Название | Форма | Что нужно | В сборку |; задаёт состав
#                      и порядок общего файла (строки с «да» и готовыми вопросами), в JSON — D.session (все строки:
#                      title, control, todo, sid или null) и s.control/s.todo/s.display у включённых предметов
#
# Источник данных — <Предмет>\Конспект\Вопросы\NN. Название.md (формат — docs/формат-вопроса.md)
# и, если есть, <Предмет>\Конспект\_Вопросы.md (строки «Охват: …», «Курс: …») и <Предмет>\Тесты\*.md.
import os, re, sys, json, glob, html, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_FULL = 2500  # «Подробно» короче — замечание в отчёте (--min-full)
TEMPLATE = os.path.normpath(os.path.join(HERE, "..", "assets", "reader.html"))

SECTIONS = {
    "кратко": "short", "краткий ответ": "short", "ответ": "short",
    "план": "plan", "план ответа": "plan",
    "подробно": "full", "подробный ответ": "full", "конспект": "full",
    "термины": "terms", "понятия": "terms", "термины и понятия": "terms",
    "цитаты": "quotes", "цитаты и тексты": "quotes",
    "уточнения": "qa", "если спросят": "qa", "дополнительные вопросы": "qa", "возможные уточнения": "qa",
    "даты": "dates", "хронология": "dates", "опорные даты": "dates",
    "источники": "sources", "литература": "sources", "источники и литература": "sources",
}
META = {"раздел": "section", "тема": "section", "занятия": "lectures", "занятие": "lectures",
        "лекции": "lectures", "лекция": "lectures", "ключевые слова": "keywords"}
ABBR = set("""свт св прп ап апп блж сщмч мч мц вмч равноап прав митр архиеп еп патр прот протопресв протоиер иер свящ диак
игум архим иером мон схиигум т е г гг в вв н э р х см ср др пр им ок гл кн ч с стр ст л тт тыс млн руб проф
мф мк лк ин деян иак пет рим кор гал еф флп кол фес тим тит флм евр откр быт исх лев чис втор нав суд руф цар пар
езд неем есф иов пс притч еккл песн ис иер плач иез дан ос иоил ам авд иона мих наум авв соф агг зах мал прем сир
акад гос изд им англ греч лат слав евр др-рус ред сост пер""".split())

TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
                     "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))

def slug(s):
    s = "".join(TRANSLIT.get(c, c) for c in s.lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "subject"

# ---------- markdown → HTML (ровно то подмножество, которым пишутся конспекты) ----------

def _short_url(u):
    u = re.sub(r"^https?://(www\.)?", "", u)
    return u if len(u) <= 48 else u[:45] + "…"

def inline(s):
    keep = []
    def hold(x):
        keep.append(x)
        return f"\x00{len(keep) - 1}\x00"
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               lambda m: hold(f'<a href="{html.escape(m.group(2))}" target="_blank" rel="noopener">{html.escape(m.group(1), False)}</a>'), s)
    s = re.sub(r"(?<![\w/])(https?://[^\s<>«»\"]+[^\s<>«»\".,;:!?)])",
               lambda m: hold(f'<a href="{html.escape(m.group(1))}" target="_blank" rel="noopener">{html.escape(_short_url(m.group(1)), False)}</a>'), s)
    s = html.escape(s, False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\*\w])\*(?![\s\*])(.+?)(?<![\s\*])\*(?![\*\w])", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w_])_(?![\s_])(.+?)(?<![\s_])_(?![\w_])", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], s)

LIST_RE = re.compile(r"^(\s*)([-*•]|\d+[.)])\s+(.*)$")

def _list(lines):
    items = []
    for l in lines:
        m = LIST_RE.match(l)
        if m:
            items.append([len(m.group(1).expandtabs(4)), m.group(2)[0].isdigit(), m.group(3).strip(),
                          int(re.match(r"\d+", m.group(2)).group()) if m.group(2)[0].isdigit() else 1])
        elif items:
            items[-1][2] += " " + l.strip()
    def build(i, indent):
        ordered, start = items[i][1], items[i][3]
        parts = [f'<ol{f" start={start}" if ordered and start != 1 else ""}>' if ordered else "<ul>"]
        while i < len(items) and items[i][0] >= indent:
            li = "<li>" + inline(items[i][2])
            i += 1
            if i < len(items) and items[i][0] > indent:
                sub, i = build(i, items[i][0])
                li += sub
            parts.append(li + "</li>")
        parts.append("</ol>" if ordered else "</ul>")
        return "".join(parts), i
    out, i = [], 0
    while i < len(items):
        h, i = build(i, items[i][0])
        out.append(h)
    return "".join(out)

def _table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], [r for r in cells[2:]]
    return ('<div class="tw"><table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in head) +
            "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body) +
            "</tbody></table></div>")

def md(text):
    lines = text.replace("\r\n", "\n").split("\n")
    out, para, i = [], [], 0
    def flush():
        if para:
            out.append("<p>" + inline(" ".join(x.strip() for x in para)) + "</p>")
            para.clear()
    while i < len(lines):
        l = lines[i]
        if not l.strip():
            flush(); i += 1; continue
        if l.lstrip().startswith("```"):  # блок кода: ``` … ```
            flush(); buf = []; i += 1
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                buf.append(lines[i]); i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf), False) + "</code></pre>")
            i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", l)
        if m:
            flush()
            lvl = min(max(len(m.group(1)), 3), 4)
            out.append(f"<h{lvl}>{inline(m.group(2).strip())}</h{lvl}>")
            i += 1; continue
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", l):
            flush(); out.append("<hr>"); i += 1; continue
        if l.lstrip().startswith(">"):
            flush(); buf = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i])); i += 1
            out.append("<blockquote>" + md("\n".join(buf)) + "</blockquote>"); continue
        if l.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            flush(); rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i]); i += 1
            out.append(_table(rows)); continue
        if LIST_RE.match(l) and not re.match(r"^\s*\d+[.)]\s*$", l):
            flush(); block = []
            while i < len(lines) and (LIST_RE.match(lines[i]) or (lines[i].startswith(("  ", "\t")) and lines[i].strip())):
                block.append(lines[i]); i += 1
            out.append(_list(block)); continue
        para.append(l); i += 1
    flush()
    return "\n".join(out)

def strip_tags(h):
    t = re.sub(r"<[^>]+>", " ", h)
    t = t.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'").replace("&amp;", "&")
    return re.sub(r"\s+", " ", t).strip()

# ---------- особые разделы ----------

TERM_RE = re.compile(r"^\s*[-*•]\s+\*\*(.+?)\*\*\s*(?:\([^)]*\)\s*)?[—–:-]\s*(.+)$")
DATE_RE = re.compile(r"^\s*[-*•]\s+(?:\*\*)?(.+?)(?:\*\*)?\s+[—–]\s+(.+)$")
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}

def roman(s):
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN.get(ch, 0)
        total, prev = (total - v, prev) if v < prev else (total + v, v)
    return total

def date_key(d):
    """Ключ для сортировки хронологии: год, иначе середина века; «до Р. Х.» — отрицательный."""
    bc = -1 if re.search(r"до\s*Р\.?\s*Х", d) else 1
    y = re.search(r"(?<!\d)(\d{3,4})(?!\d)", d)
    if y:
        return bc * int(y.group(1))
    c = re.search(r"\b([IVXLC]+)\s*(?:[–-]\s*[IVXLC]+\s*)?в", d)
    if c:
        base = (roman(c.group(1)) - 1) * 100
        if re.search(r"(нач|перв\w* половин)", d): return bc * (base + 15)
        if re.search(r"(кон|втор\w* половин)", d): return bc * (base + 85)
        return bc * (base + 50)
    y = re.search(r"(?<!\d)(\d{1,2})\s*(?:[–-]\s*\d+)?\s*(?:г|год)", d)
    return bc * int(y.group(1)) if y else 99999

def terms_block(text, n, glossary):
    items, rest = [], []
    for l in text.split("\n"):
        m = TERM_RE.match(l)
        if m:
            items.append((m.group(1).strip(), m.group(2).strip()))
        elif items and l.startswith(("  ", "\t")) and l.strip():
            items[-1] = (items[-1][0], items[-1][1] + " " + l.strip())
        elif l.strip():
            rest.append(l)
    for t, d in items:
        glossary.append({"term": t, "def": inline(d), "n": n})
    h = "".join(f"<div><dt>{inline(t)}</dt><dd>{inline(d)}</dd></div>" for t, d in items)
    return (f'<dl class="terms">{h}</dl>' if h else "") + (md("\n".join(rest)) if rest else "")

def dates_block(text, n, chron):
    items, rest = [], []
    for l in text.split("\n"):
        m = DATE_RE.match(l)
        if m:
            items.append((m.group(1).strip(), m.group(2).strip()))
        elif l.strip():
            rest.append(l)
    for d, e in items:
        chron.append({"date": inline(d), "k": date_key(d), "event": inline(e), "n": n})
    h = "".join(f'<li><span class="dd">{inline(d)}</span> <span>{inline(e)}</span></li>' for d, e in items)
    return (f'<ul class="dates">{h}</ul>' if h else "") + (md("\n".join(rest)) if rest else "")

def qa_block(text):
    blocks = re.split(r"\n\s*\n", text.strip())
    items = []
    for b in blocks:
        b2 = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", b.strip())
        m = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", b2, re.S)
        if m:
            items.append([m.group(1).strip(), m.group(2).strip()])
        elif items:
            items[-1][1] += "\n\n" + b.strip()
        else:
            items.append(["", b.strip()])
    out = []
    for q, a in items:
        if q:
            out.append(f'<details class="qa"><summary>{inline(q)}</summary><div class="qa-a">{md(a)}</div></details>')
        else:
            out.append(md(a))
    return "".join(out)

# ---------- вопрос ----------

def split_sentences(t):
    parts = re.split(r"(?<=[.!?…])\s+(?=[«\"(—–-]?\s*[А-ЯЁA-Z0-9])", t.strip())
    out = []
    for p in parts:
        prev = out[-1] if out else ""
        last = re.search(r"([А-ЯЁа-яёA-Za-z\-]+)\.\s*$", prev)
        if out and last and (last.group(1).lower() in ABBR or len(last.group(1)) == 1):
            out[-1] = prev + " " + p
        else:
            out.append(p)
    return [p for p in out if p.strip()]

def parse_question(path, glossary, chron):
    # ­ — мягкие переносы из текста лекций: невидимы, но ломают поиск («функ­циональный» ≠ «функциональный»).
    # ́ — знак ударения («су́дите»): тоже невидимо ломает поиск.
    raw = (open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
           .replace("­", "").replace(" ", " ").replace("́", ""))
    fn = os.path.basename(path)
    m = re.match(r"(\d+)", fn)
    n = int(m.group(1)) if m else 0
    title, meta, secs, order, cur, warn = None, {}, {}, [], None, []
    for l in raw.split("\n"):
        h1 = re.match(r"^#\s+(.+)$", l)
        h2 = re.match(r"^##\s+(.+?)\s*#*\s*$", l)
        if h1 and title is None:
            title = h1.group(1).strip(); continue
        if h2:
            name = h2.group(1).strip().rstrip(":")
            key = SECTIONS.get(name.lower().replace("ё", "е"), None)
            if key is None:
                key = "x:" + name
                warn.append(f"неизвестный раздел «## {name}» — попадёт в «Подробно»")
            cur = key
            if key not in secs:
                secs[key] = []; order.append(key)
            continue
        if cur is None:
            mm = re.match(r"^\s*([А-ЯЁа-яё ]{4,20}):\s*(.+)$", l)
            if mm and mm.group(1).strip().lower() in META:
                meta[META[mm.group(1).strip().lower()]] = mm.group(2).strip()
            continue
        secs[cur].append(l)
    text = {k: "\n".join(v).strip() for k, v in secs.items()}
    title = title or re.sub(r"^\d+\.\s*", "", os.path.splitext(fn)[0])
    q = {"n": n, "title": title, "section": meta.get("section", ""), "lectures": meta.get("lectures", ""),
         "keywords": [k.strip() for k in re.split(r"[,;]", meta.get("keywords", "")) if k.strip()]}
    q["short"] = md(text.get("short", ""))
    q["plan"] = md(text.get("plan", ""))
    full = md(text.get("full", ""))
    for k in order:
        if k.startswith("x:"):
            full += f"<h3>{inline(k[2:])}</h3>" + md(text[k])
    q["full"] = full
    q["terms"] = terms_block(text.get("terms", ""), n, glossary) if text.get("terms") else ""
    q["quotes"] = md(text.get("quotes", ""))
    q["qa"] = qa_block(text["qa"]) if text.get("qa") else ""
    q["dates"] = dates_block(text.get("dates", ""), n, chron) if text.get("dates") else ""
    q["sources"] = md(text.get("sources", ""))
    short_plain = strip_tags(q["short"])
    sent = split_sentences(short_plain)
    st = {"short_chars": len(short_plain), "short_sent": len(sent), "full_chars": len(strip_tags(q["full"])),
          "qa": q["qa"].count("<details"), "terms": q["terms"].count("<dt>")}
    if not text.get("short"): warn.append("нет раздела «Кратко»")
    elif not 5 <= st["short_sent"] <= 8: warn.append(f"в «Кратко» {st['short_sent']} предложений (нужно 5–7)")
    if not text.get("full"): warn.append("нет раздела «Подробно»")
    elif st["full_chars"] < MIN_FULL: warn.append(f"«Подробно» короткий: {st['full_chars']} знаков")
    if not text.get("plan"): warn.append("нет «Плана ответа»")
    if not text.get("qa"): warn.append("нет «Уточнений»")
    if not q["section"]: warn.append("нет строки «Раздел:»")
    q["_stats"], q["_warn"] = st, warn
    return q

def parse_subject(folder):
    folder = folder.rstrip("\\/")
    name = os.path.basename(folder)
    qdir = os.path.join(folder, "Конспект", "Вопросы")
    files = sorted(glob.glob(os.path.join(qdir, "*.md")),
                   key=lambda f: int((re.match(r"(\d+)", os.path.basename(f)) or [0, "0"])[1] if re.match(r"\d", os.path.basename(f)) else 10**6))
    files = [f for f in files if not os.path.basename(f).startswith("_")]
    glossary, chron = [], []
    qs = [parse_question(f, glossary, chron) for f in files]
    note, course, title = "", "", name
    plan = os.path.join(folder, "Конспект", "_Вопросы.md")
    if os.path.exists(plan):
        for l in open(plan, encoding="utf-8-sig").read().splitlines()[:30]:
            m = re.match(r"^\s*(Охват|Курс|Название)\s*:\s*(.+)$", l)
            if m:
                if m.group(1) == "Охват": note = m.group(2).strip()
                elif m.group(1) == "Курс": course = m.group(2).strip()
                else: title = m.group(2).strip()
    tests = []
    for f in sorted(glob.glob(os.path.join(folder, "Тесты", "*.md")),
                    key=lambda f: (int(m.group(1)) if (m := re.search(r"(\d+)", os.path.basename(f))) else 10**6, f)):
        t = open(f, encoding="utf-8-sig").read()
        m = re.match(r"^#\s+(.+)$", t.strip().split("\n")[0])
        tests.append({"title": m.group(1).strip() if m else os.path.splitext(os.path.basename(f))[0],
                      "html": md(t.strip().split("\n", 1)[1] if m and "\n" in t.strip() else t)})
    glossary.sort(key=lambda g: strip_tags(g["term"]).lower().replace("ё", "е"))
    chron.sort(key=lambda c: (c["k"], c["n"]))
    return {"id": slug(name), "title": title, "note": note, "course": course, "questions": qs,
            "glossary": glossary, "dates": chron, "tests": tests}

# ---------- вывод ----------

def report(s):
    print(f"\n=== {s['title']}: вопросов {len(s['questions'])}, терминов {len(s['glossary'])}, дат {len(s['dates'])}, тестов {len(s['tests'])}")
    print(" №  | Кратко: предл./знаков | Подробно, знаков | термины | уточнения | замечания")
    bad = 0
    for q in s["questions"]:
        st = q["_stats"]
        w = "; ".join(q["_warn"])
        bad += bool(q["_warn"])
        print(f"{q['n']:>3} | {st['short_sent']:>2} / {st['short_chars']:>5}          | {st['full_chars']:>7}          | {st['terms']:>7} | {st['qa']:>9} | {w}")
    tot_full = sum(q["_stats"]["full_chars"] for q in s["questions"])
    print(f"Итого «Подробно»: {tot_full/1000:.0f} тыс. знаков; вопросов с замечаниями: {bad}")

def clean(s, kratko):
    s = dict(s)
    qs = []
    for q in s["questions"]:
        q = {k: v for k, v in q.items() if not k.startswith("_")}
        if kratko:
            q["full"] = ""; q["quotes"] = ""; q["sources"] = ""
        qs.append(q)
    s["questions"] = qs
    return s

def read_session(root):
    """Таблица `<корень>/_Сессия.md`: | Папка | Название | Форма | Что нужно | — табло сессии для общего файла.
    Первая строка `# …` — заголовок сессии (идёт в D.title, если нет --title)."""
    path = os.path.join(root, "_Сессия.md")
    if not os.path.exists(path):
        return []
    rows, head = [], ""
    for l in open(path, encoding="utf-8-sig").read().splitlines():
        if not head and l.startswith("# "):
            head = l[2:].strip()
        if not l.startswith("|"):
            continue
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] in ("Папка", "") or set(cells[0]) <= {"-", ":"}:
            continue
        rows.append({"folder": cells[0], "title": cells[1], "control": cells[2].lower(), "todo": cells[3],
                     "include": len(cells) < 5 or cells[4].lower().startswith("да"), "session_title": head})
    return rows

WEBFONTS = False

def render(subjects, title, out_path, kratko=False, artifact_path=None, session=None):
    tpl = open(TEMPLATE, encoding="utf-8").read()
    data = {"title": title, "built": datetime.date.today().strftime("%d.%m.%Y"), "kratko": kratko,
            "subjects": [clean(s, kratko) for s in subjects], "session": session or [], "webfonts": WEBFONTS}
    # Внутри <script> нельзя допустить "</script" и "<!--": экранируем через \/ и < (валидно для JSON).
    blob = (json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            .replace("</", "<\\/").replace("<!--", "\\u003c!--").replace("<script", "\\u003cscript"))
    page = tpl.replace("__TITLE__", html.escape(title)).replace("__DATA__", blob)
    head = re.search(r"<!--HEAD-->(.*?)<!--/HEAD-->", page, re.S).group(1)
    body = re.search(r"<!--BODY-->(.*?)<!--/BODY-->", page, re.S).group(1)
    full = ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
            # interactive-widget: при открытой клавиатуре страница ужимается, и выдача поиска не прячется под ней
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">\n'
            + head + "\n</head>\n<body>\n" + body + "\n</body>\n</html>\n")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    open(out_path, "w", encoding="utf-8").write(full)
    print(f"-> {out_path} ({os.path.getsize(out_path)/1024:.0f} КБ)")
    if artifact_path:
        open(artifact_path, "w", encoding="utf-8").write(head + "\n" + body)
        print(f"-> {artifact_path} (вариант для Artifact)")

def main():
    a = sys.argv[1:]
    def opt(k):
        return a[a.index(k) + 1] if k in a else None
    check, kratko = "--check" in a, "--kratko" in a
    artifact, title = opt("--artifact"), opt("--title")
    global WEBFONTS, MIN_FULL
    WEBFONTS = "--webfonts" in a
    if opt("--min-full"):
        MIN_FULL = int(opt("--min-full"))
    out_file = opt("--out")
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--artifact", "--title", "--only", "--out", "--min-full"))]
    if not pos:
        sys.exit("Использование: build_html.py <папка предмета> [--out файл.html] | --all <корневая папка> [--only \"Предмет,Предмет\"] [--check] [--kratko] [--webfonts] [--artifact файл]")
    session = []
    if "--all" in a:
        root = pos[0].rstrip("\\/")
        folders = sorted(d for d in glob.glob(os.path.join(root, "*"))
                         if glob.glob(os.path.join(d, "Конспект", "Вопросы", "*.md")))
        session = read_session(root)
        if session:  # табло сессии задаёт и состав, и порядок общего файла
            have = {os.path.basename(d): d for d in folders}
            folders = [have[r["folder"]] for r in session if r["include"] and r["folder"] in have]
        if opt("--only"):  # только названные предметы (через запятую) — например, те, по которым зачёт в эту сессию
            only = {s.strip() for s in opt("--only").split(",") if s.strip()}
            missing = only - {os.path.basename(d) for d in folders}
            if missing:
                sys.exit("--only: нет готовых вопросов у " + ", ".join(sorted(missing)))
            folders = [d for d in folders if os.path.basename(d) in only]
    else:
        folders = [pos[0].rstrip("\\/")]
        root = os.path.dirname(folders[0])
    subjects = [parse_subject(f) for f in folders]
    for s in subjects:
        r = next((r for r in session if r["folder"] == os.path.basename(folders[subjects.index(s)])), None)
        if r:  # имя файла остаётся по папке; «Название» из таблицы — только на табло
            s["control"], s["todo"], s["display"] = r["control"], r["todo"], r["title"]
        report(s)
    if check:
        return
    out_dir = os.path.join(root, "Конспекты")
    for s in subjects:
        single_out = out_file if (out_file and "--all" not in a) else os.path.join(out_dir, f"{s['title']}.html")
        render([s], s["title"], single_out,
               artifact_path=artifact if (artifact and len(subjects) == 1) else None)
        if kratko:
            render([s], f"{s['title']} (кратко)", os.path.join(out_dir, f"{s['title']} (кратко).html"), kratko=True)
    if "--all" in a and subjects:
        t = title or (session and session[0].get("session_title")) or "Конспекты к сессии"
        sids = {os.path.basename(f): s["id"] for f, s in zip(folders, subjects)}
        board = [{"title": r["title"] or r["folder"], "control": r["control"], "todo": r["todo"],
                  "sid": sids.get(r["folder"])} for r in session]
        render(subjects, t, os.path.join(out_dir, "Все предметы.html"), artifact_path=artifact, session=board)
        if kratko:
            render(subjects, t + " (кратко)", os.path.join(out_dir, "Все предметы (кратко).html"), kratko=True, session=board)

if __name__ == "__main__":
    main()
