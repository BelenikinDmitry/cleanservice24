"""CleanService24 Ads Manager — внутренний инструмент одного рекламодателя.

Запуск:  python3 app.py            (демо-режим, без токена, http://localhost:8000)
Режимы (переменная DIRECT_MODE): demo | sandbox | prod
Для sandbox/prod нужны YANDEX_CLIENT_ID, YANDEX_CLIENT_SECRET (приложение в Яндекс ID).
Токен хранится только в памяти процесса.
"""
import json
import os
import secrets
import urllib.parse
import urllib.request
from datetime import date, datetime
from html import escape
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ads_parser import parse as parse_ads
from direct_client import DemoClient, DirectError, RealClient, build_ad_payload, default_period

MODE = os.environ.get("DIRECT_MODE", "demo")
PORT = int(os.environ.get("PORT", "8000"))
CLIENT_ID = os.environ.get("YANDEX_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("YANDEX_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("YANDEX_REDIRECT_URI", f"http://localhost:{PORT}/callback")
ADS_FILE = Path(__file__).resolve().parents[2] / "yadirect" / "after_renovation" / "ads.md"
APP_NAME = "CleanService24 Ads Manager"

SESSIONS = {}  # sid -> {"token": str | None}
OAUTH_STATES = set()

CSS = """
:root{--bg:#f5f6f8;--card:#fff;--text:#1b1f24;--muted:#667085;--line:#e4e7ec;--accent:#fc3f1d;--ok:#12805c;--bad:#c0262d;--warn:#fff4d6}
@media(prefers-color-scheme:dark){:root{--bg:#14161a;--card:#1d2026;--text:#e8eaed;--muted:#9aa3af;--line:#2d3139;--ok:#4cc38a;--bad:#ff6b6b;--warn:#3a3118}}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 -apple-system,Segoe UI,Roboto,Arial,sans-serif;background:var(--bg);color:var(--text)}
header{background:var(--card);border-bottom:1px solid var(--line);padding:0 24px;display:flex;align-items:center;gap:28px;height:56px}
header .brand{font-weight:700}header .brand b{color:var(--accent)}
nav a{color:var(--muted);text-decoration:none;margin-right:18px;padding:18px 0;display:inline-block;border-bottom:2px solid transparent}
nav a.on{color:var(--text);border-color:var(--accent)}header .right{margin-left:auto;color:var(--muted);font-size:13px}
.banner{background:var(--warn);padding:8px 24px;font-size:13px}
main{max-width:1080px;margin:24px auto;padding:0 24px}h1{font-size:22px;margin:0 0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-bottom:18px}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:13px}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tfoot td{font-weight:700;border-bottom:0}
.btn{display:inline-block;background:var(--accent);color:#fff;border:0;border-radius:8px;padding:10px 18px;font-size:15px;text-decoration:none;cursor:pointer}
.btn.sec{background:transparent;color:var(--text);border:1px solid var(--line)}
.tag{display:inline-block;padding:2px 9px;border-radius:99px;font-size:12px;background:var(--line)}
.ok{color:var(--ok)}.bad{color:var(--bad)}.muted{color:var(--muted)}
form.row{display:flex;gap:10px;align-items:end;flex-wrap:wrap;margin-bottom:14px}
label{display:flex;flex-direction:column;font-size:12px;color:var(--muted);gap:4px}
input,select{padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--text);font-size:14px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:800px){.grid{grid-template-columns:1fr}}
pre{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;font-size:12.5px;margin:8px 0 0}
.ad h3{margin:0 0 2px;font-size:16px;color:#1a0dab}.ad .u{color:var(--ok);font-size:13px}.ad p{margin:2px 0}
.login{max-width:440px;margin:80px auto;text-align:center}.login p{color:var(--muted)}
"""


def page(title, body, active="", authed=True):
    nav = ""
    if authed:
        items = [("/campaigns", "Кампании"), ("/ads", "Объявления"), ("/reports", "Отчёты")]
        nav = "<nav>" + "".join(
            f'<a href="{h}" class="{"on" if h == active else ""}">{t}</a>' for h, t in items
        ) + "</nav>"
    right = f'<span class="right">{MODE} · <a href="/logout">Выйти</a></span>' if authed else ""
    banner = (
        '<div class="banner">Демо-режим: данные тестовые, запросы в API Яндекс Директа не отправляются.</div>'
        if MODE == "demo"
        else ""
    )
    return (
        f'<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)} — {APP_NAME}</title><style>{CSS}</style></head><body>"
        f'<header><div class="brand">CleanService24 <b>Ads</b> Manager</div>{nav}{right}</header>'
        f"{banner}<main>{body}</main></body></html>"
    )


def fmt_int(n):
    return f"{int(n):,}".replace(",", " ")


def fmt_money(x):
    return f"{x:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def bar_chart(title, labels, values, unit=""):
    w, h, pad = 480, 170, 24
    mx = max(values) or 1
    bw = (w - 2 * pad) / len(values)
    bars = ""
    for i, v in enumerate(values):
        bh = (h - 2 * pad) * v / mx
        x = pad + i * bw
        bars += (
            f'<rect x="{x + 2:.1f}" y="{h - pad - bh:.1f}" width="{bw - 4:.1f}" height="{bh:.1f}" '
            f'rx="2" fill="#fc3f1d" opacity=".85"><title>{labels[i]}: {v:g}{unit}</title></rect>'
        )
    first, last = labels[0][5:], labels[-1][5:]
    return (
        f'<div class="card"><b>{escape(title)}</b>'
        f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{escape(title)}">{bars}'
        f'<text x="{pad}" y="{h - 6}" font-size="11" fill="#667085">{first}</text>'
        f'<text x="{w - pad}" y="{h - 6}" font-size="11" fill="#667085" text-anchor="end">{last}</text>'
        f"</svg></div>"
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "AdsManager/0.1"

    def log_message(self, fmt, *args):
        pass

    # ---------- helpers ----------
    def _sid(self):
        c = SimpleCookie(self.headers.get("Cookie", ""))
        return c["sid"].value if "sid" in c else None

    def _session(self):
        return SESSIONS.get(self._sid())

    def _send(self, html, status=200, headers=None):
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, url, cookie=None):
        self.send_response(302)
        self.send_header("Location", url)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _start_session(self, token):
        sid = secrets.token_urlsafe(24)
        SESSIONS[sid] = {"token": token}
        return f"sid={sid}; Path=/; HttpOnly; SameSite=Lax"

    def _client(self, sess):
        if MODE == "demo":
            return DemoClient()
        return RealClient(sess["token"], sandbox=(MODE == "sandbox"))

    # ---------- routing ----------
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(url.query)
        path = url.path
        if path == "/login/yandex":
            return self.login_yandex()
        if path == "/login/demo" and MODE == "demo":
            return self._redirect("/campaigns", self._start_session(None))
        if path == "/callback":
            return self.callback(q)
        if path == "/logout":
            SESSIONS.pop(self._sid(), None)
            return self._redirect("/", "sid=; Path=/; Max-Age=0")
        sess = self._session()
        if path in ("/", "/login"):
            return self._redirect("/campaigns") if sess else self.login_page()
        if not sess:
            return self._redirect("/")
        try:
            if path == "/campaigns":
                return self.campaigns_page(sess)
            if path == "/ads":
                return self.ads_page()
            if path == "/reports":
                return self.reports_page(sess, q)
        except DirectError as e:
            return self._send(page("Ошибка API", f'<div class="card bad">Ошибка API Директа: {escape(str(e))}</div>'), 502)
        self._send(page("404", "<h1>Не найдено</h1>"), 404)

    def do_POST(self):
        sess = self._session()
        if not sess or self.path != "/ads/send":
            return self._redirect("/")
        length = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        idx, group_id = int(form["idx"][0]), form["ad_group_id"][0].strip()
        ads = parse_ads(ADS_FILE)
        if not group_id.isdigit() or ads[idx]["_errors"]:
            return self._send(page("Ошибка", '<div class="card bad">Нужен числовой AdGroupId и валидное объявление.</div>', "/ads"), 400)
        try:
            result = self._client(sess).ads_add(group_id, ads[idx])
        except DirectError as e:
            return self._send(page("Ошибка API", f'<div class="card bad">{escape(str(e))}</div>', "/ads"), 502)
        body = f'<h1>Результат Ads.add</h1><div class="card"><pre>{escape(json.dumps(result, ensure_ascii=False, indent=2))}</pre></div><a class="btn sec" href="/ads">Назад</a>'
        self._send(page("Ads.add", body, "/ads"))

    # ---------- auth ----------
    def login_page(self):
        if MODE == "demo":
            btn = '<a class="btn" href="/login/demo">Войти в демо-режиме</a><p class="muted">OAuth-ключи не заданы — запущен демо-режим с тестовыми данными.</p>'
        else:
            btn = '<a class="btn" href="/login/yandex">Подключить аккаунт Директа</a>'
        body = (
            f'<div class="card login"><h1>{APP_NAME}</h1>'
            "<p>Внутренний инструмент рекламодателя: загрузка объявлений и отчёты по кампаниям Яндекс Директа.</p>"
            f"{btn}</div>"
        )
        self._send(page("Вход", body, authed=False))

    def login_yandex(self):
        if MODE == "demo" or not CLIENT_ID:
            return self._send(page("Вход", '<div class="card bad">YANDEX_CLIENT_ID не задан.</div>', authed=False), 500)
        state = secrets.token_urlsafe(16)
        OAUTH_STATES.add(state)
        params = urllib.parse.urlencode(
            {"response_type": "code", "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI, "state": state}
        )
        self._redirect("https://oauth.yandex.ru/authorize?" + params)

    def callback(self, q):
        state = q.get("state", [""])[0]
        if state not in OAUTH_STATES or "code" not in q:
            return self._send(page("Вход", '<div class="card bad">Неверный ответ OAuth.</div>', authed=False), 400)
        OAUTH_STATES.discard(state)
        data = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "code": q["code"][0],
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            }
        ).encode()
        with urllib.request.urlopen(urllib.request.Request("https://oauth.yandex.ru/token", data=data), timeout=30) as r:
            token = json.loads(r.read())["access_token"]
        self._redirect("/campaigns", self._start_session(token))

    # ---------- pages ----------
    def campaigns_page(self, sess):
        camps = self._client(sess).campaigns()
        rows = "".join(
            f'<tr><td>{c["Id"]}</td><td>{escape(c["Name"])}</td><td>{c["Type"]}</td>'
            f'<td><span class="tag">{c["State"]}</span></td><td>{c["Status"]}</td></tr>'
            for c in camps
        )
        body = (
            "<h1>Кампании</h1><div class=\"card\"><table><thead><tr><th>ID</th><th>Название</th><th>Тип</th>"
            f"<th>Состояние</th><th>Статус модерации</th></tr></thead><tbody>{rows}</tbody></table>"
            '<p class="muted">Источник: сервис Campaigns, метод get.</p></div>'
        )
        self._send(page("Кампании", body, "/campaigns"))

    def ads_page(self):
        ads = parse_ads(ADS_FILE)
        blocks, last_group = "", None
        for i, ad in enumerate(ads):
            if ad["_group"] != last_group:
                last_group = ad["_group"]
                blocks += f"<h2>{escape(last_group)}</h2>"
            status = (
                '<span class="ok">✓ лимиты соблюдены</span>'
                if not ad["_errors"]
                else '<span class="bad">✗ ' + escape("; ".join(ad["_errors"])) + "</span>"
            )
            counts = (
                f'заголовок {len(ad["Заголовок"])}/56 · доп. {len(ad["Доп. заголовок"])}/30 · '
                f'текст {len(ad["Текст"])}/81 · ссылка {len(ad["Отображаемая ссылка"])}/20'
            )
            payload = json.dumps(build_ad_payload(0, ad), ensure_ascii=False, indent=2).replace(
                '"AdGroupId": 0', '"AdGroupId": "<ID группы>"'
            )
            blocks += (
                f'<div class="card ad"><div class="muted">{escape(ad["_name"])}</div>'
                f'<h3>{escape(ad["Заголовок"])} — {escape(ad["Доп. заголовок"])}</h3>'
                f'<div class="u">cleanservice24.ru › {escape(ad["Отображаемая ссылка"])}</div>'
                f'<p>{escape(ad["Текст"])}</p><p class="muted">{" · ".join(map(escape, ad["Уточнения"]))}</p>'
                f'<p class="muted">{counts}</p><p>{status}</p>'
                f"<details><summary>Тело запроса Ads.add</summary><pre>{escape(payload)}</pre></details>"
                f'<form class="row" method="post" action="/ads/send" style="margin-top:10px">'
                f'<input type="hidden" name="idx" value="{i}">'
                f'<label>ID группы объявлений (AdGroupId)<input name="ad_group_id" inputmode="numeric" placeholder="например, 5000000001"></label>'
                f'<button class="btn sec" {"disabled" if ad["_errors"] else ""}>Отправить в Директ</button></form></div>'
            )
        head = f'<h1>Объявления</h1><p class="muted">Источник: {escape(ADS_FILE.name)} · объявлений: {len(ads)}. Проверка лимитов — до отправки.</p>'
        self._send(page("Объявления", head + blocks, "/ads"))

    def reports_page(self, sess, q):
        d_from, d_to = default_period()
        try:
            d_from = datetime.strptime(q["from"][0], "%Y-%m-%d").date() if "from" in q else d_from
            d_to = datetime.strptime(q["to"][0], "%Y-%m-%d").date() if "to" in q else d_to
        except ValueError:
            pass
        group = q.get("group", ["day"])[0]
        rows = self._client(sess).report(d_from, d_to)
        agg = {}
        for r in rows:
            key = r["date"] if group == "day" else r["campaign"]
            a = agg.setdefault(key, {"impressions": 0, "clicks": 0, "cost": 0.0})
            a["impressions"] += r["impressions"]
            a["clicks"] += r["clicks"]
            a["cost"] += r["cost"]
        keys = sorted(agg)
        tot = {k: sum(agg[x][k] for x in keys) for k in ("impressions", "clicks", "cost")}

        def line(label, a):
            ctr = a["clicks"] / a["impressions"] * 100 if a["impressions"] else 0
            cpc = a["cost"] / a["clicks"] if a["clicks"] else 0
            return (
                f'<td>{escape(label)}</td><td class="n">{fmt_int(a["impressions"])}</td><td class="n">{fmt_int(a["clicks"])}</td>'
                f'<td class="n">{ctr:.2f}%</td><td class="n">{fmt_money(a["cost"])}</td><td class="n">{fmt_money(cpc)}</td>'
            )

        body_rows = "".join(f"<tr>{line(k, agg[k])}</tr>" for k in keys)
        sel = lambda v: "selected" if group == v else ""
        form = (
            '<form class="row" method="get">'
            f'<label>С<input type="date" name="from" value="{d_from}"></label>'
            f'<label>По<input type="date" name="to" value="{d_to}"></label>'
            f'<label>Разбивка<select name="group"><option value="day" {sel("day")}>По дням</option>'
            f'<option value="campaign" {sel("campaign")}>По кампаниям</option></select></label>'
            '<button class="btn">Показать</button></form>'
        )
        charts = ""
        if group == "day" and keys:
            charts = '<div class="grid">' + bar_chart("Клики по дням", keys, [agg[k]["clicks"] for k in keys]) + bar_chart(
                "Расход по дням, ₽", keys, [round(agg[k]["cost"], 2) for k in keys]
            ) + "</div>"
        body = (
            "<h1>Отчёты</h1>" + form + charts
            + '<div class="card"><table><thead><tr>'
            + f'<th>{"Дата" if group == "day" else "Кампания"}</th><th class="n">Показы</th><th class="n">Клики</th>'
            '<th class="n">CTR</th><th class="n">Расход</th><th class="n">CPC</th></tr></thead>'
            f"<tbody>{body_rows}</tbody><tfoot><tr>{line('Итого', tot)}</tr></tfoot></table>"
            '<p class="muted">Источник: сервис Reports (CAMPAIGN_PERFORMANCE_REPORT, TSV).</p></div>'
        )
        self._send(page("Отчёты", body, "/reports"))


if __name__ == "__main__":
    print(f"{APP_NAME}: режим {MODE}, http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
