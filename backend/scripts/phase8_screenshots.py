"""Phase 8 — capture the real running interface (no mocked data).

Requires: backend on 127.0.0.1:8000, vite dev server on 127.0.0.1:5173.
Uses the installed Microsoft Edge via Playwright's msedge channel.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"C:\Users\asus\Documents\CSE276_PROJECT\screenshots")
OUT.mkdir(exist_ok=True)
BASE = "http://127.0.0.1:5173"


def shot(page, name, full=True):
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / name), full_page=full)
    print("saved", name)


def ask(page, text, wait_for=None):
    page.fill("#advisory-query", text)
    page.click("button[type=submit]")
    page.wait_for_selector("[data-decision]", timeout=30000)
    page.wait_for_timeout(900)
    return page.get_attribute("[data-decision]", "data-decision")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        desktop = browser.new_context(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        page = desktop.new_page()

        # 1. landing / dashboard
        page.goto(BASE, wait_until="networkidle")
        page.wait_for_timeout(1200)
        shot(page, "01-dashboard-desktop.png")

        # 2. advisory empty state
        page.click("text=Ask the advisory")
        page.wait_for_selector("#advisory-query")
        page.wait_for_timeout(800)
        shot(page, "02-advisory-empty.png")

        # 3. answered / educational decision
        d = ask(page, "How do I control pink bollworm in cotton?")
        print("decision answered case:", d)
        shot(page, "03-result-educational.png")

        # 4. safety refusal (PHI not published)
        d = ask(page, "What is the pre-harvest interval for cotton?")
        print("decision refusal case:", d)
        shot(page, "04-result-safety-refusal.png")

        # 4b. clarification required
        d = ask(page, "How do I control aphids in banana?")
        print("decision clarification case:", d)
        shot(page, "04b-result-clarification.png")

        # 5. escalation (crop outside scope)
        d = ask(page, "How do I control bollworm in sugarcane?")
        print("decision escalation case:", d)
        shot(page, "05-result-escalation.png")

        # 6. Hindi interface
        page.click("button:has-text('हिं')")
        page.wait_for_timeout(400)
        d = ask(page, "धान का तना छेदक")
        print("decision hindi case:", d)
        shot(page, "06-result-hindi.png")

        # 7. supporting pages
        page.click("text=सुरक्षा")
        page.wait_for_timeout(1200)
        shot(page, "07-safety-guidelines-hindi.png")

        page.goto(BASE + "/knowledge-base", wait_until="networkidle")
        page.wait_for_timeout(1200)
        shot(page, "08-knowledge-base.png")

        # 8. mobile
        mobile = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        m = mobile.new_page()
        m.goto(BASE, wait_until="networkidle")
        m.wait_for_timeout(1200)
        shot(m, "09-dashboard-mobile.png")
        m.click("header button[aria-controls='mobile-nav']")
        m.wait_for_timeout(600)
        shot(m, "10-mobile-nav.png", full=False)
        m.go_back()
        m.goto(BASE + "/advisory", wait_until="networkidle")
        d = ask(m, "How do I control pink bollworm in cotton?")
        print("mobile decision:", d)
        shot(m, "11-result-mobile.png")

        browser.close()


if __name__ == "__main__":
    sys.exit(main())
