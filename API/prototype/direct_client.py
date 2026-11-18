"""Клиент API Яндекс.Директ v5 (JSON) и демо-бэкенд с тестовыми данными.

RealClient ходит в боевой API или в песочницу (api-sandbox.direct.yandex.com).
DemoClient не делает сетевых запросов и возвращает детерминированные тестовые данные,
чтобы интерфейс можно было запустить и показать без токена.
"""
import json
import random
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

API_URL = "https://api.direct.yandex.com/json/v5"
SANDBOX_URL = "https://api-sandbox.direct.yandex.com/json/v5"

REPORT_FIELDS = ["Date", "CampaignName", "Impressions", "Clicks", "Cost"]


class DirectError(Exception):
    pass


class RealClient:
    """Минимальный клиент: Campaigns.get, Reports (TSV), Ads.add."""

    def __init__(self, token, client_login=None, sandbox=True):
        self.token = token
        self.client_login = client_login
        self.base = SANDBOX_URL if sandbox else API_URL

    def _request(self, path, payload, extra_headers=None):
        headers = {
            "Authorization": "Bearer " + self.token,
            "Accept-Language": "ru",
            "Content-Type": "application/json; charset=utf-8",
        }
        if self.client_login:
            headers["Client-Login"] = self.client_login
        headers.update(extra_headers or {})
        req = urllib.request.Request(
            f"{self.base}/{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, dict(resp.headers), resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read().decode("utf-8")

    def _call(self, service, method, params):
        status, _, body = self._request(service, {"method": method, "params": params})
        data = json.loads(body)
        if status != 200 or "error" in data:
            raise DirectError(data.get("error", {"http_status": status}))
        return data["result"]

    def campaigns(self):
        result = self._call(
            "campaigns",
            "get",
            {
                "SelectionCriteria": {},
                "FieldNames": ["Id", "Name", "State", "Status", "Type"],
            },
        )
        return result.get("Campaigns", [])

    def report(self, date_from, date_to):
        """Статистика через сервис Reports (офлайн-режим: 201/202 — отчёт ставится в очередь)."""
        payload = {
            "params": {
                "SelectionCriteria": {
                    "DateFrom": date_from.isoformat(),
                    "DateTo": date_to.isoformat(),
                },
                "FieldNames": REPORT_FIELDS,
                "ReportName": f"cs24-{date_from}-{date_to}",
                "ReportType": "CAMPAIGN_PERFORMANCE_REPORT",
                "DateRangeType": "CUSTOM_DATE",
                "Format": "TSV",
                "IncludeVAT": "NO",
                "IncludeDiscount": "NO",
            }
        }
        headers = {
            "processingMode": "auto",
            "returnMoneyInMicros": "true",
            "skipReportHeader": "true",
            "skipReportSummary": "true",
        }
        for _ in range(8):
            status, resp_headers, body = self._request("reports", payload, headers)
            if status == 200:
                return _parse_tsv(body)
            if status in (201, 202):
                time.sleep(min(int(resp_headers.get("retryIn", 5)), 60))
                continue
            raise DirectError({"http_status": status, "body": body[:500]})
        raise DirectError("Отчёт не сформирован за отведённое число попыток")

    def ads_add(self, ad_group_id, ad):
        return self._call("ads", "add", {"Ads": [build_ad_payload(ad_group_id, ad)]})


def _parse_tsv(text):
    rows = []
    lines = [line for line in text.splitlines() if line.strip()]
    for line in lines[1:] if lines and lines[0].startswith("Date\t") else lines:
        d, name, imp, clicks, cost = line.split("\t")
        rows.append(
            {
                "date": d,
                "campaign": name,
                "impressions": int(imp),
                "clicks": int(clicks),
                "cost": int(cost) / 1_000_000,
            }
        )
    return rows


def build_ad_payload(ad_group_id, ad):
    """Тело объекта для Ads.add (текстовое объявление)."""
    return {
        "AdGroupId": int(ad_group_id),
        "TextAd": {
            "Title": ad["Заголовок"],
            "Title2": ad["Доп. заголовок"],
            "Text": ad["Текст"],
            "Href": "https://cleanservice24.ru/uborka-posle-remonta/",
            "DisplayUrlPath": ad["Отображаемая ссылка"],
            "Mobile": "NO",
        },
    }


class DemoClient:
    """Тестовые данные. Это НЕ реальная статистика — интерфейс подписывает их как демо."""

    CAMPAIGNS = [
        {"Id": 10000001, "Name": "Мытьё окон", "State": "ON", "Status": "ACCEPTED", "Type": "TEXT_CAMPAIGN"},
        {"Id": 10000002, "Name": "Уборка после ремонта", "State": "ON", "Status": "ACCEPTED", "Type": "TEXT_CAMPAIGN"},
    ]

    def campaigns(self):
        return list(self.CAMPAIGNS)

    def report(self, date_from, date_to):
        rows = []
        day = date_from
        while day <= date_to:
            for camp in self.CAMPAIGNS:
                rnd = random.Random(f"{camp['Id']}-{day}")
                impressions = rnd.randint(700, 1600)
                clicks = int(impressions * rnd.uniform(0.03, 0.065))
                cost = round(clicks * rnd.uniform(35, 62), 2)
                rows.append(
                    {
                        "date": day.isoformat(),
                        "campaign": camp["Name"],
                        "impressions": impressions,
                        "clicks": clicks,
                        "cost": cost,
                    }
                )
            day += timedelta(days=1)
        return rows

    def ads_add(self, ad_group_id, ad):
        return {"demo": True, "message": "В демо-режиме объявления в Директ не отправляются"}


def default_period(days=14):
    end = date.today() - timedelta(days=1)
    return end - timedelta(days=days - 1), end
