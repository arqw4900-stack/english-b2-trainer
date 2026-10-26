"""Puts the data from data/*.txt into index.html (between /*@EXTRA@*/ and /*@EXTRA-END@*/) and checks it.

python data/build.py
  words/*.txt   extra word themes: "# Тема | Theme", then "english | русский | example" ([word] = what the card asks to type);
                a theme with the name of an existing one (e.g. «Фразовые глаголы») adds its words to that theme
  grammar.txt   B2 grammar topics with typed exercises
  practice.txt  free-answer practice
  writing.txt   writing tasks with model answers
Exits 1 on errors (duplicate words, identical translations, broken records).
"""
import collections, json, pathlib, re, sys

SRC = pathlib.Path(__file__).parent
OUT = SRC.parent / "index.html"
errors, notes = [], []
err = errors.append


def lines(name):
    for n, raw in enumerate((SRC / name).read_text(encoding="utf-8").splitlines(), 1):
        s = raw.strip()
        if s and not s.startswith("//"):
            yield n, s


def split(s, n=None):
    return [p.strip() for p in (s.split("|", n) if n else s.split("|"))]


def fields(s):   # "||" separates answers inside one field
    return [p.strip() for p in re.split(r"(?<!\|)\|(?!\|)", s)]


def words():
    themes = []
    for f in sorted((SRC / "words").glob("*.txt")):
        th = None
        for n, s in lines(f"words/{f.name}"):
            if s.startswith("#"):
                ru, en = split(s[1:])
                th = {"name": ru, "en": en, "words": []}
                themes.append(th)
                continue
            parts = split(s)
            if len(parts) != 3 or not all(parts):
                sys.exit(f"{f.name}:{n}: expected 'english | русский | example': {s}")
            if s.count("[") != s.count("]") or s.count("[") > 1:
                sys.exit(f"{f.name}:{n}: one [word] at most: {s}")
            th["words"].append([parts[0], "", parts[1], parts[2]])
    return themes


def grammar():
    out, g = [], None
    for n, s in lines("grammar.txt"):
        k, _, v = s.partition(":")
        v = v.strip()
        if s.startswith("@"):
            gid, grp, abbr, name, ru = split(s[1:])
            g = {"id": gid, "grp": grp, "abbr": abbr, "name": name, "ru": ru, "rule": [], "examples": [], "tip": "", "ex": []}
            out.append(g)
        elif k == "rule": g["rule"].append(v)
        elif k == "table": g["table"] = [split(v)]
        elif k == "row": g["table"].append(split(v))
        elif k == "e": g["examples"].append([p.strip() for p in v.split(";;")])
        elif k == "tip": g["tip"] = v
        elif k == "q":
            q, ans, note = fields(v)
            g["ex"].append({"q": q, "task": "", "ans": [a.strip() for a in ans.split("||")], "note": note})
        else: sys.exit(f"grammar.txt:{n}: unknown line: {s}")
    return out


PTYPES = {"tr": 3, "fix": 3, "para": 4, "reg": 4, "gap": 3, "wf": 4, "cont": 4, "use": 4, "op": 3}   # fields per line


def practice():
    out = {t: [] for t in PTYPES}
    for n, s in lines("practice.txt"):
        k, _, v = s.partition(":")
        parts = fields(v)
        if k not in PTYPES or len(parts) != PTYPES[k] or not all(parts):
            sys.exit(f"practice.txt:{n}: bad line: {s}")
        if len(parts) == 4:
            q, task, ans, note = parts
        else:
            (q, ans, note), task = parts, ""
        out[k].append({"q": q, "task": task, "ans": [a.strip() for a in ans.split("||")], "note": note})
    return out


def writing():
    out, w = [], None
    for n, s in lines("writing.txt"):
        k, _, v = s.partition(":")
        v = v.strip()
        if s.startswith("@"):
            wid, kind, grp, reg, rng, title, ru = split(s[1:])
            lo, hi = map(int, rng.split("-"))
            w = {"id": wid, "kind": kind, "grp": grp, "reg": reg, "min": lo, "max": hi, "title": title, "ru": ru, "task": "", "tru": "", "pts": [], "phr": [], "model": []}
            out.append(w)
        elif k == "task": w["task"] = v
        elif k == "ru": w["tru"] = v
        elif k == "pt": w["pts"].append(v)
        elif k == "ph": w["phr"].append(split(v, 1))
        elif k == "m": w["model"].append(v)
        else: sys.exit(f"writing.txt:{n}: unknown line: {s}")
    return out


html = OUT.read_text(encoding="utf-8")
base = json.loads(re.search(r"^const THEMES = (.*);$", html, re.M).group(1))
extra, gram, prac, wri = words(), grammar(), practice(), writing()

# ---------- checks ----------
key = lambda en: re.sub(r"\s+", " ", re.sub(r"\(.*?\)|[\[\]]", "", en).lower()).strip()
senses = lambda ru: frozenset(p.strip() for p in re.split(r"[,;]", re.sub(r"\(.*?\)", "", ru)) if p.strip())
# the old vocabulary has deliberate synonyms (they are never offered as options for each other),
# so only the new words are checked against everything
seen_en = {key(w[0]): th["name"] for th in base for w in th["words"]}
seen_ru = {senses(w[2]): w[0] for th in base for w in th["words"]}
for th in extra:
    for en, _, ru, ex in th["words"]:
        k, r = key(en), senses(ru)
        if k in seen_en:
            err(f"duplicate word: {en} ({seen_en[k]} / {th['name']})")
        seen_en[k] = th["name"]
        if r in seen_ru:
            err(f"same translation «{ru}»: {en} / {seen_ru[r]}")
        seen_ru[r] = en
        if not re.search(r"[.!?…][\"”]?$", ex):
            notes.append(f"example without final punctuation: {en}")
counts = collections.Counter()
for th in extra:
    counts[th["name"]] += len(th["words"])
print("Новые слова: " + ", ".join(f"{k} +{v}" for k, v in counts.items()))

ids = set()
for g in gram:
    if g["id"] in ids:
        err(f"grammar: repeated id {g['id']}")
    ids.add(g["id"])
    if len(g["ex"]) < 10 or not g["rule"] or len(g["examples"]) < 3 or not g["tip"]:
        err(f"grammar {g['id']}: needs rule, ≥3 examples, tip, ≥10 exercises")
    if any(len(e) != 2 for e in g["examples"]):
        err(f"grammar {g['id']}: example without translation")
    if "table" in g and len({len(r) for r in g["table"]}) != 1:
        err(f"grammar {g['id']}: table rows of different length")
    for e in g["ex"]:
        if e["q"].count("___") != 1 or not all(e["ans"]) or len(e["note"]) < 12:
            err(f"grammar {g['id']}: bad exercise: {e['q'][:60]}")
print(f"Грамматика: {len(gram)} тем, {sum(len(g['ex']) for g in gram)} упражнений")

for k, items in prac.items():
    if len(items) < 10:
        err(f"practice {k}: only {len(items)} items")
    for it in items:
        if len(it["note"]) < 10:
            err(f"practice {k}: short note: {it['q'][:50]}")
        if k in ("gap", "wf") and it["q"].count("___") != 1:
            err(f"practice {k}: needs one ___: {it['q']}")
        if len(set(it["ans"])) != len(it["ans"]):
            err(f"practice {k}: repeated answer: {it['q'][:50]}")
    if len({it["q"] for it in items}) != len(items):
        err(f"practice {k}: repeated prompt")
print("Практика: " + ", ".join(f"{k} {len(v)}" for k, v in prac.items()))

for w in wri:
    n = len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", " ".join(w["model"]).replace(chr(92) + "n", " ")))
    if w["grp"] not in ("formal", "informal", "essay", "article", "report") or w["reg"] not in ("off", "semi", "neu", "inf"):
        err(f"writing {w['id']}: bad group or register")
    if not w["task"] or not w["tru"] or len(w["pts"]) < 3 or len(w["phr"]) < 4 or len(w["model"]) < 3:
        err(f"writing {w['id']}: needs task, ru, ≥3 points, ≥4 phrases, model")
    if any(len(p) != 2 for p in w["phr"]):
        err(f"writing {w['id']}: phrase without translation")
    if not w["min"] * 0.9 <= n <= w["max"] * 1.1:
        err(f"writing {w['id']}: model has {n} words, task {w['min']}-{w['max']}")
print(f"Письмо: {len(wri)} заданий")
if len({w['id'] for w in wri}) != len(wri):
    err("writing: repeated id")

if notes:
    print("\nЗамечания:\n  " + "\n  ".join(notes[:20]))
if errors:
    print(f"\nОШИБКИ ({len(errors)}):\n  " + "\n  ".join(errors[:60]))
    sys.exit(1)

js = lambda name, data: f"const {name} = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
block = "/*@EXTRA@*/\n" + js("EXTRA_THEMES", extra) + js("GRAMMAR", gram) + js("PRACTICE", prac) + js("WRITING", wri) + "/*@EXTRA-END@*/"
if "/*@EXTRA@*/" not in html:
    sys.exit("marker /*@EXTRA@*/ not found in index.html")
html = re.sub(r"/\*@EXTRA@\*/.*?/\*@EXTRA-END@\*/", lambda m: block, html, flags=re.S)
OUT.write_text(html, encoding="utf-8", newline="\n")
print(f"\nindex.html: {len(html.encode()) // 1024} KB · ошибок нет")
