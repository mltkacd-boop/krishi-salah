"""Capture the interface's real behaviour when the backend is not running.

Run only while uvicorn is stopped: the point is that the UI degrades honestly
instead of showing fabricated data.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"C:\Users\asus\Documents\CSE276_PROJECT\screenshots")
BASE = "http://127.0.0.1:5173"

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_context(viewport={"width": 1440, "height": 960}).new_page()

    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / "12-backend-unreachable-dashboard.png"), full_page=True)
    print("saved 12")

    page.goto(BASE + "/advisory", wait_until="networkidle")
    page.fill("#advisory-query", "How do I control pink bollworm in cotton?")
    page.click("button[type=submit]")
    page.wait_for_selector("text=HTTP", timeout=20000)
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / "13-backend-unreachable-ask.png"), full_page=True)
    print("saved 13")

    browser.close()
