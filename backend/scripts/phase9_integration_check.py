"""Phase 9 — automated integration check for the running interface.

The Phase 8 script (phase8_screenshots.py) produced screenshots by hand and
printed the decision it happened to see; nothing failed if the decision was
wrong. This script keeps the same coverage but *asserts* it, and exits non-zero
on any failure, so it can be run before a deployment instead of being read.

What it checks, against the real backend and the real frontend:

1. every route renders with no console error and no failed request
2. desktop navigation reaches every route
3. the five verified decisions still come back from POST /rag/answer
4. the language switch changes the chrome and survives a reload
5. the backend-unreachable state is shown, and is not confused with a refusal
6. no horizontal overflow at 390 px and 1440 px

Requires: backend on 127.0.0.1:8000, Vite on 127.0.0.1:5173.
Uses the installed Microsoft Edge through Playwright's msedge channel, which is
why no browser download is needed on this laptop.
"""
from __future__ import annotations

import sys

from playwright.sync_api import Error, sync_playwright

BASE = "http://127.0.0.1:5173"
ROUTES = ["/", "/advisory", "/knowledge-base", "/safety-guidelines", "/project-info"]

DECISION_CASES = [
    ("How do I control pink bollworm in cotton?", "EDUCATIONAL_INFORMATION"),
    ("What is the pre-harvest interval for cotton?", "SAFETY_REFUSAL"),
    ("How do I control aphids in banana?", "CLARIFICATION_REQUIRED"),
    ("How do I control bollworm in sugarcane?", "ESCALATION_REQUIRED"),
]

results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    results.append((ok, name, detail))
    if ok:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}" + (f"  [{detail}]" if detail else ""))
    return ok


def ask(page, text: str) -> str:
    page.fill("textarea", text)
    page.click("button[type=submit]")
    page.wait_for_selector("[data-decision]", timeout=30000)
    page.wait_for_timeout(400)
    return page.get_attribute("[data-decision]", "data-decision") or ""


def main() -> int:
    console_errors: list[str] = []
    failed_requests: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        page = context.new_page()
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("requestfailed", lambda r: failed_requests.append(f"{r.method} {r.url}"))
        page.on(
            "response",
            lambda r: failed_requests.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None,
        )

        # 1. routes render
        for route in ROUTES:
            console_errors.clear()
            failed_requests.clear()
            page.goto(BASE + route, wait_until="networkidle")
            page.wait_for_timeout(600)
            body = page.inner_text("body")
            check(
                len(body.strip()) > 200 and not console_errors and not failed_requests,
                f"route {route} renders",
                "; ".join(console_errors + failed_requests)[:200],
            )

        # 2. navigation reaches every route (header bar; About sits in the footer)
        page.goto(BASE, wait_until="networkidle")
        for href, label, scope in (
            ("/advisory", "advisory", "header nav"),
            ("/knowledge-base", "knowledge-base", "header nav"),
            ("/safety-guidelines", "safety-guidelines", "header nav"),
            ("/project-info", "project-info", "footer nav"),
            ("/", "home", "header nav"),
        ):
            page.click(f"{scope} a[href='{href}']")
            page.wait_for_timeout(500)
            check(page.url.rstrip("/").endswith(href.rstrip("/")), f"nav → {label}", page.url)

        # 3. decisions still come from the backend
        page.goto(BASE + "/advisory", wait_until="networkidle")
        for query, expected in DECISION_CASES:
            actual = ask(page, query)
            check(actual == expected, f"decision: {query[:40]}", f"got {actual}")

        # Hindi question with the interface switched to Hindi
        page.click("button:has-text('हिं')")
        page.wait_for_timeout(400)
        page.goto(BASE + "/advisory", wait_until="networkidle")
        hi_lang = page.get_attribute("html", "lang")
        hi_nav = page.inner_text("header nav")
        check("सलाह" in hi_nav, "language switch renders Hindi chrome", hi_nav[:40].replace("\n", " "))
        check(hi_lang == "hi", "html lang follows the interface language", str(hi_lang))
        actual = ask(page, "धान का तना छेदक")
        check(actual == "EDUCATIONAL_INFORMATION", "decision: Hindi rice stem borer", f"got {actual}")

        # 4. the choice survives a reload (localStorage)
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(500)
        check("सलाह" in page.inner_text("header nav"), "language choice persists across reload")

        # back to English for the remaining checks
        page.click("button:has-text('EN')")
        page.wait_for_timeout(300)

        # 5. backend unreachable: abort the API calls, not the static assets
        err_context = browser.new_context(viewport={"width": 1440, "height": 960})
        err_page = err_context.new_page()
        err_page.route("http://localhost:8000/**", lambda route: route.abort())
        err_page.route("http://127.0.0.1:8000/**", lambda route: route.abort())

        err_page.goto(BASE, wait_until="load")
        err_page.wait_for_timeout(1500)
        check("unreachable" in err_page.inner_text("body").lower(), "dashboard shows unreachable state")

        err_page.goto(BASE + "/advisory", wait_until="load")
        err_page.wait_for_timeout(800)
        ask_ok = True
        try:
            ask(err_page, "How do I control pink bollworm in cotton?")
        except (Error, TimeoutError):
            ask_ok = False
        body = err_page.inner_text("body")
        check(not ask_ok, "advisory request fails when the backend is down")
        check(
            "did not respond" in body.lower() or "could not reach" in body.lower(),
            "advisory shows an error, not an answer",
            body[:80].replace("\n", " "),
        )
        err_context.close()

        # 6. no horizontal overflow
        for width, height in ((390, 844), (1440, 960)):
            ctx = browser.new_context(
                viewport={"width": width, "height": height},
                is_mobile=width < 500,
                has_touch=width < 500,
            )
            pg = ctx.new_page()
            for route in ROUTES:
                pg.goto(BASE + route, wait_until="networkidle")
                pg.wait_for_timeout(400)
                scroll = pg.evaluate("document.documentElement.scrollWidth")
                client = pg.evaluate("document.documentElement.clientWidth")
                check(scroll <= client + 1, f"no overflow {width}px {route}", f"{scroll}>{client}")
            ctx.close()

        browser.close()

    failed = [name for ok, name, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

