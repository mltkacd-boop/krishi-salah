"""Redesign pass — capture and measure the real running interface.

Requires: backend on 127.0.0.1:8000, vite dev server on 127.0.0.1:5173.
Uses the installed Microsoft Edge via Playwright's msedge channel.

Two jobs:
  1. screenshots at 1440 / 768 / 390 (plus 1920 and 1024 for composition)
  2. an overflow measurement at every validation width, so "responsive" is a
     measurement rather than an opinion: document.scrollWidth must equal the
     viewport width on every route.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"C:\Users\asus\Documents\CSE276_PROJECT\screenshots\redesign")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:5173"
WIDTHS = [360, 390, 430, 768, 1024, 1440, 1920]
ROUTES = ["/", "/advisory", "/knowledge-base", "/safety-guidelines", "/project-info"]

THEMES = [
    ("desktop-1440", {"width": 1440, "height": 960}),
    ("tablet-768", {"width": 768, "height": 1024}),
    ("mobile-390", {"width": 390, "height": 844}),
]

results = []


def shot(page, name, full=True):
    # A sticky header is painted at whatever offset the page happens to be
    # scrolled to, so full-page shots are taken from the top.
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / name), full_page=full)
    print("saved", name)


def ask(page, text):
    """Submit a question through the real API and return the decision class."""
    page.fill("textarea", text)
    page.click("button[type=submit]")
    page.wait_for_selector("[data-decision]", timeout=45000)
    page.wait_for_timeout(900)
    return page.get_attribute("[data-decision]", "data-decision")


def document_lang(page):
    return page.evaluate("() => document.documentElement.lang")


def overflow_check(browser, width):
    ctx = browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=1)
    page = ctx.new_page()
    for route in ROUTES:
        page.goto(BASE + route, wait_until="networkidle")
        page.wait_for_timeout(900)
        doc = page.evaluate(
            "() => ({ sw: document.documentElement.scrollWidth,"
            " cw: document.documentElement.clientWidth,"
            " bw: document.body.scrollWidth })"
        )
        ok = doc["sw"] <= doc["cw"] + 1
        results.append({"width": width, "route": route, **doc, "ok": ok})
        print(f"overflow {width:>5} {route:<20} scrollWidth={doc['sw']} client={doc['cw']} {'ok' if ok else 'OVERFLOW'}")
    ctx.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        # ---- desktop / tablet / mobile page set -------------------------------
        for label, viewport in THEMES:
            mobile = viewport["width"] < 768
            ctx = browser.new_context(
                viewport=viewport,
                device_scale_factor=1 if mobile else 1,
                is_mobile=mobile,
                has_touch=mobile,
            )
            page = ctx.new_page()

            page.goto(BASE, wait_until="networkidle")
            page.wait_for_timeout(1400)
            shot(page, f"home-{label}.png")

            # bottom nav must be visible on mobile and absent on desktop
            nav_state = page.evaluate(
                "() => { const n = document.querySelector('nav.fixed'); if (!n) return 'absent';"
                " const r = n.getBoundingClientRect(); return r.height > 0 ? 'visible' : 'hidden'; }"
            )
            print(f"bottom-nav {label}: {nav_state}")
            results.append({"check": "bottom-nav", "label": label, "state": nav_state})

            page.goto(BASE + "/advisory", wait_until="networkidle")
            page.wait_for_timeout(900)
            shot(page, f"advisory-empty-{label}.png")

            decision = ask(page, "How do I control pink bollworm in cotton?")
            print(f"decision {label} answered:", decision)
            results.append({"check": "decision", "label": label, "query": "pink bollworm cotton", "decision": decision})
            shot(page, f"result-educational-{label}.png")

            page.goto(BASE + "/knowledge-base", wait_until="networkidle")
            page.wait_for_timeout(1200)
            shot(page, f"library-{label}.png")

            page.goto(BASE + "/safety-guidelines", wait_until="networkidle")
            page.wait_for_timeout(1400)
            shot(page, f"safety-{label}.png")

            page.goto(BASE + "/project-info", wait_until="networkidle")
            page.wait_for_timeout(800)
            shot(page, f"about-{label}.png")

            ctx.close()

        # ---- decision classes that the knowledge base can actually produce ----
        ctx = browser.new_context(viewport={"width": 1440, "height": 960})
        page = ctx.new_page()
        page.goto(BASE + "/advisory", wait_until="networkidle")

        for name, query in [
            ("result-refusal-desktop-1440.png", "What is the pre-harvest interval for cotton?"),
            ("result-clarification-desktop-1440.png", "How do I control aphids in banana?"),
            ("result-escalation-desktop-1440.png", "How do I control bollworm in sugarcane?"),
        ]:
            decision = ask(page, query)
            print("decision:", query, "->", decision)
            results.append({"check": "decision", "label": "desktop", "query": query, "decision": decision})
            shot(page, name)

        # ---- Hindi ------------------------------------------------------------
        page.click("button:has-text('हिं')")
        page.wait_for_timeout(500)
        page.goto(BASE, wait_until="networkidle")
        page.wait_for_timeout(1200)
        shot(page, "home-desktop-hindi.png")
        page.goto(BASE + "/advisory", wait_until="networkidle")
        decision = ask(page, "धान का तना छेदक")
        print("decision hindi:", decision)
        results.append({"check": "decision", "label": "desktop-hi", "query": "धान का तना छेदक", "decision": decision})
        shot(page, "result-hindi-desktop.png")
        page.goto(BASE + "/safety-guidelines", wait_until="networkidle")
        page.wait_for_timeout(1400)
        shot(page, "safety-desktop-hindi.png")
        page.click("button:has-text('EN')")
        ctx.close()

        # ---- functional walk-through: the real interactions, not the pictures --
        fctx = browser.new_context(viewport={"width": 1440, "height": 960})
        fp = fctx.new_page()
        fp.goto(BASE, wait_until="networkidle")
        fp.wait_for_timeout(900)
        fp.fill("textarea", "How do I control pink bollworm in cotton?")
        fp.click("button[type=submit]")
        fp.wait_for_url("**/advisory", timeout=15000)
        fp.wait_for_selector("[data-decision]", timeout=45000)
        results.append(
            {
                "check": "home-composer-handoff",
                "url": fp.url,
                "decision": fp.get_attribute("[data-decision]", "data-decision"),
            }
        )
        print("home handoff ->", fp.url)

        for label, target, expect in [
            ("nav-knowledge", "nav a[href='/knowledge-base']", "/knowledge-base"),
            ("nav-safety", "nav a[href='/safety-guidelines']", "/safety-guidelines"),
            ("nav-home", "nav a[href='/']", "/"),
        ]:
            fp.click(target)
            fp.wait_for_timeout(800)
            ok = fp.url.endswith(expect)
            results.append({"check": label, "url": fp.url, "ok": ok})
            print(f"{label} -> {fp.url} {'ok' if ok else 'WRONG'}")

        # Hindi switch must change the rendered chrome, not just the button state
        fp.goto(BASE + "/safety-guidelines", wait_until="networkidle")
        fp.wait_for_timeout(1200)
        english_heading = fp.inner_text("h1")
        fp.click("button:has-text('हिं')")
        fp.wait_for_timeout(600)
        hindi_heading = fp.inner_text("h1")
        switched = english_heading != hindi_heading and document_lang(fp)
        results.append(
            {
                "check": "language-switch",
                "en": english_heading,
                "hi": hindi_heading,
                "documentLang": document_lang(fp),
                "ok": bool(switched),
            }
        )
        print("language switch:", english_heading, "->", hindi_heading)
        fctx.close()

        # ---- mobile close-ups (viewport, not full page) ----------------------
        mctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        mp = mctx.new_page()
        mp.goto(BASE, wait_until="networkidle")
        mp.wait_for_timeout(1200)
        mp.screenshot(path=str(OUT / "view-mobile-home-top.png"))
        print("saved view-mobile-home-top.png")

        mp.goto(BASE + "/advisory", wait_until="networkidle")
        ask(mp, "How do I control pink bollworm in cotton?")
        mp.evaluate("document.querySelector('[data-decision]').scrollIntoView({block: 'start'})")
        mp.wait_for_timeout(700)
        mp.screenshot(path=str(OUT / "view-mobile-result-status.png"))
        print("saved view-mobile-result-status.png")

        mp.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        mp.wait_for_timeout(700)
        mp.screenshot(path=str(OUT / "view-mobile-result-bottom.png"))
        print("saved view-mobile-result-bottom.png")
        mctx.close()

        # ---- measurement at every validation width ---------------------------
        for width in WIDTHS:
            overflow_check(browser, width)

        browser.close()

    report = OUT / "responsive-report.json"
    report.write_text(json.dumps(results, indent=2), encoding="utf-8")
    bad = [r for r in results if r.get("ok") is False]
    print(f"\n{len(results)} checks, {len(bad)} overflow failures -> {report}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
