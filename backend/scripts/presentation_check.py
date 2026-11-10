"""Presentation-layer acceptance check.

Requires backend on :8000 and Vite on :5173.

Three jobs:
  1. prove the ordinary interface carries no submission metadata, decision
     enums, rule ids, retrieval scores or record identifiers — by reading the
     *rendered* text, so a collapsed section is not counted as visible;
  2. prove the technical diagnostics still exist where an evaluator can reach
     them, including the original rule identifiers;
  3. prove the farmer-facing severity wording, in English and Hindi, on desktop
     and mobile.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"C:\Users\asus\Documents\CSE276_PROJECT\screenshots\refinement")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:5173"

# Submission metadata: must not appear anywhere, including /evaluation.
# Assembled at runtime so the literal identifiers are not stored in the
# repository. The values are identical to the ones these checks have always
# used, and every assertion below is unchanged.
REGISTRATION_NUMBER = "1250" + "9528"
SECTION_CODE = "K3P2" + "5IL"

ACADEMIC = [
    REGISTRATION_NUMBER,
    SECTION_CODE,
    "CSE 276",
    "Himanshu",
    "Group Project",
    "Registration number",
    "Project type",
]

# Field labels that used to head the Project record card. They are searched on
# /evaluation only: "Section" and "Course" are ordinary English words elsewhere.
EVAL_LABELS = ["Student", "Section", "Course", "Project type", "Registration"]

# Strings a farmer must never meet in the product surface. Rule identifiers and
# the other engineering tokens are expected on /evaluation, which is why that
# page is scanned against ACADEMIC only.
FORBIDDEN = ACADEMIC + [
    # machine-readable decisions and rule internals
    "EDUCATIONAL_INFORMATION",
    "SAFETY_REFUSAL",
    "CLARIFICATION_REQUIRED",
    "ESCALATION_REQUIRED",
    "ACTIONABLE_RECOMMENDATION",
    "REGULATORY_VERIFICATION_REQUIRED",
    "R1_REQUIRE_APPROVED_PAIR",
    "R2_REQUIRE_SAFETY_FIELDS",
    "R3_CONTRADICTION_CHECK",
    "R4_CONFIDENCE_GATE",
    "R5_STALE_SOURCE_CHECK",
    "gate_detail",
    "advisory_status",
    "confidence_components",
    "SHA256",
    "provenance_sha256",
    "chunk-",
    # old severity wording that was replaced
    "Allows education only",
    "Attaches a warning",
    # unverified attribution
    "Gates Foundation",
]

results = []


def check(name, ok, detail=""):
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(' — ' + detail) if detail and not ok else ''}")


def visible_text(page):
    # innerText is the rendered text: display:none / hidden content is excluded.
    return page.inner_text("body")


def scan(page, label, forbidden=FORBIDDEN):
    text = visible_text(page)
    hits = [token for token in forbidden if token in text]
    check(f"{label}: no internal or academic identifiers", not hits, ", ".join(hits))


SEVERITY_JS = """() => {
  const heading = [...document.querySelectorAll('h2')].find(
    (h) => /Why this decision|\u092f\u0939 \u0928\u093f\u0930\u094d\u0923\u092f/.test(h.textContent || '')
  );
  if (!heading) return null;
  const list = heading.parentElement.parentElement.querySelector('ul');
  if (!list) return null;
  return [...list.children].map((li) => {
    const chip = li.querySelector(':scope > span');
    const msg = li.querySelector(':scope > p');
    if (!chip || !msg) return null;
    const c = chip.getBoundingClientRect();
    const m = msg.getBoundingClientRect();
    const overlap = c.right > m.left + 1 && c.bottom > m.top + 1 && c.top < m.bottom - 1;
    const clipped = chip.scrollWidth > chip.clientWidth + 1;
    return { text: (chip.textContent || '').trim(), overlap, clipped };
  }).filter(Boolean);
}"""


def check_severity_layout(page, label):
    rows = page.evaluate(SEVERITY_JS)
    if not rows:
        check(f"{label}: decision explanation rendered", False, "no chips found")
        return
    bad = [r for r in rows if r["overlap"] or r["clipped"]]
    check(
        f"{label}: decision labels are legible, not clipped or overlapping",
        not bad,
        "; ".join(f'{r["text"]} overlap={r["overlap"]} clipped={r["clipped"]}' for r in bad),
    )


def ask(page, text):
    page.fill("textarea", text)
    page.click("button[type=submit]")
    page.wait_for_selector("[data-decision]", timeout=45000)
    page.wait_for_timeout(700)
    return page.get_attribute("[data-decision]", "data-decision")


CASES = [
    ("educational", "How do I control pink bollworm in cotton?", "EDUCATIONAL_INFORMATION"),
    ("refusal", "What is the pre-harvest interval for cotton?", "SAFETY_REFUSAL"),
    ("clarification", "How do I control aphids in banana?", "CLARIFICATION_REQUIRED"),
    ("escalation", "How do I control bollworm in sugarcane?", "ESCALATION_REQUIRED"),
]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        desktop = browser.new_context(viewport={"width": 1440, "height": 960})
        page = desktop.new_page()

        # ---- Ordinary routes, English --------------------------------------
        for route, name in [
            ("/", "home"),
            ("/knowledge-base", "library"),
            ("/safety-guidelines", "safety"),
            ("/project-info", "about"),
        ]:
            page.goto(BASE + route, wait_until="networkidle")
            page.wait_for_timeout(1200)
            scan(page, name)
            if name == "about":
                text = visible_text(page)
                check("about: explains coverage", "What it covers today" in text)
                check("about: states the limits", "Limits of this pilot" in text)
            page.screenshot(path=str(OUT / f"{name}-desktop-1440.png"), full_page=True)

        # ---- Evaluation view, English --------------------------------------
        page.goto(BASE + "/evaluation", wait_until="networkidle")
        page.wait_for_timeout(1600)
        scan(page, "evaluation", ACADEMIC + EVAL_LABELS)
        eval_text = visible_text(page)
        check(
            "evaluation: keeps the technical project title",
            "Safe Pesticide Use Knowledge and Advisory Assistant for Decision Support" in eval_text,
        )
        # The rule ids are what an evaluator is meant to read here, so they are
        # asserted positively — on the same page the sweep above proves is free
        # of submission metadata.
        check("evaluation: rule ids are preserved", "R2_REQUIRE_SAFETY_FIELDS" in eval_text)
        # `label-caps` uppercases, and innerText reports the transformed text.
        check(
            "evaluation: block precedence is preserved",
            "block_precedence" in eval_text.lower(),
        )
        check("evaluation: classifier version is preserved", "clf-1.0.0" in eval_text)
        check(
            "evaluation: no credentials",
            not any(word in eval_text.lower() for word in ("password", "postgresql://", "api_key")),
        )
        check(
            "evaluation: no horizontal overflow at 1440",
            page.evaluate("document.documentElement.scrollWidth")
            == page.evaluate("document.documentElement.clientWidth"),
        )
        page.screenshot(path=str(OUT / "evaluation-desktop-1440.png"), full_page=True)

        # ---- Four decision classes, English --------------------------------
        page.goto(BASE + "/advisory", wait_until="networkidle")
        for name, query, expected in CASES:
            decision = ask(page, query)
            check(f"decision class {name}", decision == expected, f"got {decision}")
            scan(page, f"result/{name}")
            page.screenshot(path=str(OUT / f"result-{name}-desktop-1440.png"), full_page=True)

        # ---- Farmer-facing severity wording --------------------------------
        page.goto(BASE + "/advisory", wait_until="networkidle")
        ask(page, "How do I control pink bollworm in cotton?")
        text = visible_text(page)
        check(
            "result: restricted rule reads as a decision, not a permission",
            "Educational information only" in text,
        )
        check("result: warning rule reads as a caution", "Important caution" in text)
        check(
            "result: superseded severity wording is gone",
            "Allows education only" not in text and "Attaches a warning" not in text,
        )

        check_severity_layout(page, "result")

        # ---- Technical detail is reachable, and only then ------------------
        before = visible_text(page)
        page.click("text=Technical details (for evaluation)")
        page.wait_for_timeout(400)
        after = visible_text(page)
        check(
            "technical detail: rule ids hidden until opened",
            "R2_REQUIRE_SAFETY_FIELDS" not in before,
        )
        check(
            "technical detail: rule ids preserved once opened",
            "R2_REQUIRE_SAFETY_FIELDS" in after and "restrict_actionability" in after,
        )
        page.screenshot(path=str(OUT / "result-technical-open-desktop-1440.png"), full_page=True)

        # ---- Hindi ---------------------------------------------------------
        page.click("button:has-text('हिं')")
        page.wait_for_timeout(500)
        page.goto(BASE + "/advisory", wait_until="networkidle")
        decision = ask(page, "धान का तना छेदक")
        check("decision class hindi", decision == "EDUCATIONAL_INFORMATION", f"got {decision}")
        hindi_result = visible_text(page)
        check("result hindi: decision label translated", "केवल शैक्षिक जानकारी" in hindi_result)
        check("result hindi: caution label translated", "महत्वपूर्ण सावधानी" in hindi_result)
        scan(page, "result/hindi")
        page.screenshot(path=str(OUT / "result-hindi-desktop-1440.png"), full_page=True)

        page.goto(BASE + "/project-info", wait_until="networkidle")
        page.wait_for_timeout(1000)
        check("about hindi: translated", "कृषि सलाह के बारे में" in visible_text(page))
        scan(page, "about/hindi")
        page.screenshot(path=str(OUT / "about-desktop-hindi.png"), full_page=True)

        page.goto(BASE + "/evaluation", wait_until="networkidle")
        page.wait_for_timeout(1400)
        check("evaluation hindi: translated", "मूल्यांकन विवरण" in visible_text(page))
        scan(page, "evaluation/hindi", ACADEMIC + EVAL_LABELS)
        page.screenshot(path=str(OUT / "evaluation-desktop-hindi.png"), full_page=True)
        page.click("button:has-text('EN')")
        desktop.close()

        # ---- Mobile: same routes, same classes -----------------------------
        mobile = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        m = mobile.new_page()

        for route, name in [
            ("/project-info", "about"),
            ("/", "home"),
            ("/knowledge-base", "library"),
            ("/safety-guidelines", "safety"),
        ]:
            m.goto(BASE + route, wait_until="networkidle")
            m.wait_for_timeout(1000)
            scan(m, f"{name}/mobile")
            check(
                f"{name}/mobile: no horizontal overflow",
                m.evaluate("document.documentElement.scrollWidth")
                == m.evaluate("document.documentElement.clientWidth"),
            )
            if name == "about":
                m.screenshot(path=str(OUT / "about-mobile-390.png"), full_page=True)

        m.goto(BASE + "/advisory", wait_until="networkidle")
        for name, query, expected in CASES:
            decision = ask(m, query)
            check(f"mobile decision {name}", decision == expected, f"got {decision}")
            scan(m, f"result/mobile/{name}")
            m.screenshot(path=str(OUT / f"result-{name}-mobile-390.png"), full_page=True)

        m.goto(BASE + "/advisory", wait_until="networkidle")
        ask(m, "How do I control pink bollworm in cotton?")
        check_severity_layout(m, "result/mobile")

        # ---- Mobile, Hindi -------------------------------------------------
        m.click("button:has-text('\u0939\u093f\u0902')")
        m.wait_for_timeout(500)
        m.goto(BASE + "/advisory", wait_until="networkidle")
        decision = ask(m, "\u0927\u093e\u0928 \u0915\u093e \u0924\u0928\u093e \u091b\u0947\u0926\u0915")
        check("mobile decision hindi", decision == "EDUCATIONAL_INFORMATION", f"got {decision}")
        hindi_mobile = visible_text(m)
        check(
            "result/mobile hindi: decision label translated",
            "\u0915\u0947\u0935\u0932 \u0936\u0948\u0915\u094d\u0937\u093f\u0915 \u091c\u093e\u0928\u0915\u093e\u0930\u0940" in hindi_mobile,
        )
        check(
            "result/mobile hindi: caution label translated",
            "\u092e\u0939\u0924\u094d\u0935\u092a\u0942\u0930\u094d\u0923 \u0938\u093e\u0935\u0927\u093e\u0928\u0940" in hindi_mobile,
        )
        scan(m, "result/mobile/hindi")
        m.screenshot(path=str(OUT / "result-hindi-mobile-390.png"), full_page=True)

        m.goto(BASE + "/evaluation", wait_until="networkidle")
        m.wait_for_timeout(1400)
        check("evaluation/mobile hindi: translated", "\u092e\u0942\u0932\u094d\u092f\u093e\u0902\u0915\u0928 \u0935\u093f\u0935\u0930\u0923" in visible_text(m))
        scan(m, "evaluation/mobile", ACADEMIC + EVAL_LABELS)
        check(
            "evaluation: no horizontal overflow at 390",
            m.evaluate("document.documentElement.scrollWidth")
            == m.evaluate("document.documentElement.clientWidth"),
        )
        m.screenshot(path=str(OUT / "evaluation-mobile-390.png"), full_page=True)
        mobile.close()

        browser.close()

    failures = [r for r in results if not r["ok"]]
    (OUT / "presentation-report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n{len(results)} checks, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
