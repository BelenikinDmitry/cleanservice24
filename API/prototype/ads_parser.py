"""Разбор ads.md и проверка объявлений по лимитам Яндекс.Директа."""
import re

PUNCT = set(".,:;!?-—–…«»\"'()")
LIMITS = {"Заголовок": 56, "Доп. заголовок": 30, "Текст": 81, "Отображаемая ссылка": 20}


def _punct(s):
    return sum(c in PUNCT for c in s)


def _max_word(s):
    return max((len(w.strip(".,:;!?—-")) for w in s.split()), default=0)


def parse(path):
    text = open(path, encoding="utf-8").read()
    ads = []
    group = ""
    for block in re.split(r"^(?=##+ )", text, flags=re.M):
        m = re.match(r"^## (.+)$", block, flags=re.M)
        if m and not block.startswith("###"):
            group = m.group(1).strip()
            continue
        m = re.match(r"^### (.+)$", block, flags=re.M)
        if not m:
            continue
        fields = dict(re.findall(r"^- ([^:]+): (.*)$", block, flags=re.M))
        fields["_name"] = m.group(1).strip()
        fields["_group"] = group
        fields["Уточнения"] = [x.strip() for x in fields.get("Уточнения", "").split("|") if x.strip()]
        fields["_errors"] = validate(fields)
        ads.append(fields)
    return ads


def validate(ad):
    errs = []
    for key, limit in LIMITS.items():
        if len(ad[key]) > limit:
            errs.append(f"{key}: {len(ad[key])} > {limit}")
    if _max_word(ad["Заголовок"]) > 22:
        errs.append("Заголовок: слово длиннее 22")
    if _punct(ad["Доп. заголовок"]) > 15 or _max_word(ad["Доп. заголовок"]) > 22:
        errs.append("Доп. заголовок: знаки препинания / длина слова")
    if _punct(ad["Текст"]) > 15 or _max_word(ad["Текст"]) > 23:
        errs.append("Текст: знаки препинания / длина слова")
    if any(len(x) > 25 for x in ad["Уточнения"]):
        errs.append("Уточнение длиннее 25")
    if sum(map(len, ad["Уточнения"])) > 76:
        errs.append("Уточнения: сумма > 76")
    return errs
