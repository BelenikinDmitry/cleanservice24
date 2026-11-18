"""Снимает скриншоты запущенного приложения (нужен playwright + chromium).

Использование: python3 make_screenshots.py [BASE_URL] [OUT_DIR]
Приложение должно быть уже запущено (по умолчанию http://localhost:8000).
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
out = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / "screenshots")
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 860}, locale="ru-RU")

    page.goto(base + "/")
    page.screenshot(path=str(out / "1-login.png"))

    page.click("text=Войти в демо-режиме")
    page.wait_for_url("**/campaigns")
    page.screenshot(path=str(out / "2-campaigns.png"))

    page.goto(base + "/ads")
    page.screenshot(path=str(out / "3-ads.png"), full_page=True)

    page.goto(base + "/reports")
    page.screenshot(path=str(out / "4-reports-by-day.png"), full_page=True)

    page.goto(base + "/reports?group=campaign")
    page.screenshot(path=str(out / "5-reports-by-campaign.png"), full_page=True)

    browser.close()
print("Скриншоты сохранены в", out)
