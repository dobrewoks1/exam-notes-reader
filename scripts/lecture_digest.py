# Сводка по выгруженным лекциям предмета — чтобы спланировать билеты и найти литературу,
# не читая сначала 300 КБ текста.
#
#   python scripts/lecture_digest.py "<корень>/<Предмет>" [--from 1] [--to 28] [--out папка]
#
# Читает <Предмет>/Лекции/NN. *.md (первая строка — "# Занятие N. …", страницы разделены "---")
# и пишет <Предмет>/Конспект/_Материалы из лекций.md:
#   - по каждой лекции: объём, разделы (строки вида "16.1. …"), вопросы для самоконтроля,
#     списки литературы;
#   - в конце — сводный список литературы без повторов, с номерами лекций, где она названа.
# --from/--to — диапазон занятий (номер из имени файла), например первая половина курса.
import os, re, sys, glob

args = sys.argv[1:]
if not args:
    sys.exit(__doc__ or "usage: lecture_digest.py <папка предмета> [--from N] [--to M]")
subj = args[0].rstrip("\\/")
def opt(name, default):
    return int(args[args.index(name) + 1]) if name in args else default
lo, hi = opt("--from", 0), opt("--to", 10**6)

lec_dir = os.path.join(subj, "Лекции")
out_dir = args[args.index("--out") + 1] if "--out" in args else os.path.join(subj, "Конспект")
os.makedirs(out_dir, exist_ok=True)

# Заголовки блоков, которые стоит вытащить целиком. Порядок важен: более длинные — раньше.
BLOCKS = [
    ("lit", r"(основная|дополнительная|рекомендуемая|рекомендованная)?\s*(литература|источники)(\s+и\s+литература)?(\s+к\s+(занятию|лекции|теме))?"),
    ("q", r"(вопросы\s+(для\s+самоконтроля|и\s+задания|к\s+(занятию|лекции|теме)|для\s+самопроверки|для\s+повторения)|контрольные\s+вопросы|задания\s+для\s+самоконтроля)"),
]
HEAD_RE = re.compile(r"^\s*(?:#+\s*)?(?P<h>" + "|".join(f"(?P<{k}>{r})" for k, r in BLOCKS) + r")\s*:?\s*$", re.I)
SUB_RE = re.compile(r"^\s*(\d{1,2}\.\d{1,2}\.?)\s+(\S.{2,150})$")
STOP_RE = re.compile(r"^\s*(---|#\s|Тест\s*\()")

def clean(s):
    return re.sub(r"\s+", " ", s.replace("\u00a0", " ")).strip()

def num(f):
    m = re.match(r"(\d+)", os.path.basename(f))
    return int(m.group(1)) if m else -1

files = sorted((f for f in glob.glob(os.path.join(lec_dir, "*.md")) if lo <= num(f) <= hi), key=num)
if not files:
    sys.exit(f"Нет лекций в {lec_dir} (диапазон {lo}–{hi})")

subject = os.path.basename(subj)
out = [f"# {subject}: материалы из лекций", "",
       f"Лекций: {len(files)} (занятия {num(files[0])}–{num(files[-1])}). Сгенерировано lecture_digest.py — не править руками.", ""]
all_lit = {}   # нормализованная строка -> [исходный текст, {номера лекций}]
total = 0
with_lit = 0

for f in files:
    lines = open(f, encoding="utf-8").read().splitlines()
    n = num(f)
    title = clean(lines[0].lstrip("# ")) if lines else os.path.basename(f)
    body_chars = sum(len(re.sub(r"\s", "", l)) for l in lines)
    total += body_chars
    subs, seen = [], set()
    blocks = {"lit": [], "q": []}
    cur = None
    for raw in lines[1:]:
        l = clean(raw)
        if not l:
            continue
        m = HEAD_RE.match(l)
        if m:
            cur = "lit" if m.group("lit") else "q"
            if cur == "lit" and m.group("h"):
                blocks["lit"].append(f"*{m.group('h').strip().rstrip(':')}:*")
            continue
        if STOP_RE.match(raw) or SUB_RE.match(l):
            cur = None
        sm = SUB_RE.match(l)
        if sm and len(l) < 160:
            key = sm.group(1).rstrip(".")
            if key not in seen:
                seen.add(key)
                subs.append(f"{key}. {sm.group(2).strip()}")
            continue
        if cur:
            blocks[cur].append(l)
    out += [f"## {n}. {title}", "", f"Объём: {body_chars/1000:.1f} тыс. знаков без пробелов. Файл: `Лекции/{os.path.basename(f)}`", ""]
    if subs:
        out += ["**Разделы:**", ""] + [f"- {s}" for s in subs] + [""]
    if blocks["q"]:
        out += ["**Вопросы из лекции:**", ""] + [f"- {q}" for q in blocks["q"][:25]] + [""]
    lit_items = [x for x in blocks["lit"] if not x.startswith("*")]
    if lit_items:
        with_lit += 1
        out += ["**Литература из лекции:**", ""] + [f"- {x}" if not x.startswith("*") else x for x in blocks["lit"][:40]] + [""]
        for x in lit_items:
            item = re.sub(r"^[\s\.]*\d+[\.\)]\s*|^[\s\.]+", "", x)
            if re.match(r"(медиа-объект|видео|презентация)\b", item, re.I):
                continue
            # "Цыпин В. Каноническое право / прот. Владислав Цыпин. – 2-е изд." и
            # "Цыпин В. Каноническое право. 2-е изд." — одна книга: убираем "/ ответственность".
            core = re.sub(r"\s/\s[^–\-]*?(?=\s[–\-]\s|$)", "", item)
            key = re.sub(r"[^а-яёa-z0-9]", "", core.lower())[:50]
            if len(key) < 8:
                continue
            all_lit.setdefault(key, [item, set()])[1].add(n)

if all_lit:
    out += ["---", "", "## Сводный список литературы (по частоте упоминания)", ""]
    for item, ns in sorted(all_lit.values(), key=lambda v: (-len(v[1]), v[0])):
        out.append(f"- {item} — лекции {', '.join(map(str, sorted(ns)))}")
    out.append("")

path = os.path.join(out_dir, "_Материалы из лекций.md")
open(path, "w", encoding="utf-8").write("\n".join(out))
print(f"{subject}: лекций {len(files)}, {total/1000:.0f} тыс. знаков; со списком литературы {with_lit}; "
      f"уникальных позиций литературы {len(all_lit)}\n-> {path}")
