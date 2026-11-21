#!/usr/bin/env python3
"""Сбор частот для ключей из <группа>/keywords.md через XMLRiver Wordstat.

Ключ API берётся из переменных окружения XMLRIVER_USER и XMLRIVER_KEY
(в файлы и git не пишется). Сырые ответы кэшируются в /tmp/wordstat_raw,
повторный запуск не тратит деньги на уже полученные запросы.

Результат: keywords_freq_update.md рядом со скриптом (исходный отчёт keywords_freq.md не перезаписывается).
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = Path("/tmp/wordstat_raw")
URL = "https://xmlriver.com/wordstat/new/json"


GROUP_DIRS = ["general", "cottages", "apartments", "offices"]


def load_keywords():
    """Ключи из <группа>/keywords.md: строки таблицы `| ключ | частота |`."""
    out, n = [], 0
    for g in GROUP_DIRS:
        f = HERE / g / "keywords.md"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\| (.+?) \| \d+ \|$", line)
            if m and m.group(1) != "Ключ":
                n += 1
                out.append((n, g, m.group(1).strip()))
    return out


def load_common_minus():
    text = (HERE / "minus_words.md").read_text(encoding="utf-8")
    text = text.split("\n## 2.")[0]
    words = set()
    for block in re.findall(r"```\n(.*?)```", text, flags=re.S):
        words |= {w.strip().lower() for w in block.splitlines() if w.strip()}
    return words


def fetch(query, user, key):
    CACHE.mkdir(exist_ok=True)
    f = CACHE / (re.sub(r"\W+", "_", query) + ".json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    params = urllib.parse.urlencode({"user": user, "key": key, "query": query})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(f"{URL}?{params}", timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except Exception as e:  # noqa: BLE001
            print(f"  ошибка ({e}), попытка {attempt + 1}", file=sys.stderr)
            time.sleep(3)
    return None


def main():
    user, key = os.environ.get("XMLRIVER_USER"), os.environ.get("XMLRIVER_KEY")
    if not user or not key:
        sys.exit("Задайте XMLRIVER_USER и XMLRIVER_KEY")
    kws = load_keywords()
    minus = load_common_minus()
    known = {k.lower() for _, _, k in kws}
    freq, failed, found = {}, [], {}
    for i, (n, g, k) in enumerate(kws, 1):
        data = fetch(k, user, key)
        if data is None:
            failed.append(k)
            continue
        freq[k] = 0
        for item in data.get("popular", []):
            t, v = item["text"].strip().lower(), int(item["value"])
            if t == k.lower():
                freq[k] = v
            elif t not in known and not (set(t.split()) & minus):
                if "после" in t.split() or "послестроительная" in t:
                    found[t] = max(found.get(t, 0), v)
        print(f"{i}/{len(kws)} {k}: {freq[k]}", flush=True)
        time.sleep(0.3)

    lines = ["# Частотность ключей: «Уборка после ремонта»", "",
             "Источник: XMLRiver Wordstat (вся Россия, все устройства). "
             "Частота берётся по точному совпадению фразы в выдаче `popular`; "
             "0 — фразы нет в выдаче (очень редкая или нулевая).", ""]
    for g in sorted({g for _, g, _ in kws}):
        lines += [f"## {g}", "", "| № | Ключ | Частота |", "|---|---|---|"]
        rows = [(n, k) for n, gg, k in kws if gg == g and k in freq]
        for n, k in sorted(rows, key=lambda r: -freq[r[1]]):
            lines.append(f"| {n} | {k} | {freq[k]} |")
        lines.append("")
    zero = [k for _, _, k in kws if k in freq and freq[k] == 0]
    lines += [f"## Нулевая частота ({len(zero)})", ""] + [f"- {k}" for k in zero] + [""]
    if failed:
        lines += ["## Не получены (ошибка API)", ""] + [f"- {k}" for k in failed] + [""]
    new = sorted(found.items(), key=lambda x: -x[1])
    lines += [f"## Новые фразы из выдачи (не в <группа>/keywords.md, без общих минус-слов) — {len(new)}", "",
              "| Фраза | Частота |", "|---|---|"]
    lines += [f"| {t} | {v} |" for t, v in new[:150]]
    (HERE / "keywords_freq_update.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Готово: {len(freq)} получено, {len(zero)} нулевых, {len(failed)} ошибок")


if __name__ == "__main__":
    main()
