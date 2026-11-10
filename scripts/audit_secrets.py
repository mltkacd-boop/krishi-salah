"""
One-off audit: scan project source files for accidentally committed secrets.

Not part of the app. Skips directories excluded by .gitignore (node_modules,
.venv, dist, caches) and binary files. Reports only file + line + rule name +
a masked fragment, so running it never prints a secret to the console.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    "node_modules", ".venv", "venv", "dist", "build", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov", ".git",
    ".pgdata",  # project-local PostgreSQL cluster (contains generated credentials)
}

# Files that match .gitignore's secret rules. They are *expected* to hold real
# credentials locally; the audit's subject is what could be COMMITTED. They are
# listed in the output so their exclusion is visible, never silent.
SKIP_FILES = {
    ".env", "backend/.env", "frontend/.env",
}

TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".sql", ".yml", ".yaml",
    ".toml", ".cfg", ".ini", ".txt", ".html", ".css", ".env", ".example", ".sh", ".ps1",
}

# Each rule is (name, compiled regex). Regexes target *value* shapes, so a
# mention of the word "password" in prose is not a finding.
RULES = [
    ("postgres-url-with-password", re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^\s:/@]+:(?!CHANGE_ME|PLACEHOLDER|\$|%|\{)[^\s@'\"]{4,}@")),
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("openai-style-key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{36}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    # KEY=value assignment where the value looks like a real secret.
    ("assigned-secret", re.compile(
        r"(?i)(?<![A-Za-z])(?:api[_-]?key|secret|token|passwd|password|pwd)\b\s*[:=]\s*"
        r"[\"']?(?P<value>(?!CHANGE_ME|PLACEHOLDER|YOUR_|EXAMPLE|<|$|\s*$)"
        r"[A-Za-z0-9!@#$%^&*_\-+.]{8,})[\"']?"
    )),
]

# A matched "value" that is really a code reference, not a literal secret:
#   password=app_password          (parameter passing)
#   password=secrets.token_urlsafe(24)
#   api_key=settings.cloud_llm_api_key
#   password=os.getenv("X")
# These are the legitimate ways this codebase handles secrets, so flagging them
# would train the reader to ignore the scanner.
CODE_REFERENCE = re.compile(
    r"^(?:password|passwd|pwd|"
    r"[A-Za-z0-9_]*_password|"
    r"[A-Za-z0-9_]*_key|"
    r"(?:secrets|os|settings|conn|self|request|payload|body)\..*)$"
)

# Narrow, deliberate allow-list. An audit tool that skips any line containing
# "#", "example" or "test_" is worthless — a real secret in a comment or a test
# fixture would sail through. Earlier draft had exactly that flaw; it is removed.
# Only these are tolerated, because they are *code that obtains* a secret from
# the environment at runtime, never a secret literal:
ALLOW_CONTEXT = re.compile(
    r"(?i)os\.getenv|os\.environ|getenv\(|settings\.|Field\(|getpass|"
    r"secrets\.token|token_urlsafe"
)


def main() -> int:
    findings: list[tuple[str, int, str, str]] = []
    skipped: list[str] = []
    scanned = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".env", ".gitignore"}:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in SKIP_FILES:
            skipped.append(rel)
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        for lineno, line in enumerate(text.splitlines(), 1):
            if len(line) > 4000:
                continue
            for name, rx in RULES:
                m = rx.search(line)
                if not m:
                    continue
                frag = m.group(0)
                value = m.groupdict().get("value")
                if value and CODE_REFERENCE.match(value):
                    continue
                # A value that immediately continues into a call expression is a
                # function invocation (e.g. `admin_password = init_local_cluster(...)`),
                # so the matched identifier is not a secret literal.
                if value and line[m.end():m.end() + 1] == "(":
                    continue
                if ALLOW_CONTEXT.search(frag) or ALLOW_CONTEXT.search(line[max(0, m.start() - 40):m.start()]):
                    continue
                masked = frag[:12] + "***" if len(frag) > 12 else "***"
                findings.append((rel, lineno, name, masked))

    print(f"Scanned {scanned} text files under {ROOT.name}/ ({len(RULES)} rules).")
    print("Excluded: .venv, node_modules, dist, __pycache__, caches, .pgdata")
    if skipped:
        print(
            "Skipped (git-ignored secret files, expected to hold local credentials — "
            "cannot be committed):"
        )
        for rel in skipped:
            print(f"  - {rel}")
    else:
        print("Skipped local secret files: none present")

    if not findings:
        print("RESULT: no secrets in committable files.")
        return 0
    print(f"RESULT: {len(findings)} potential finding(s):")
    for rel, lineno, name, masked in findings:
        print(f"  {rel}:{lineno}  [{name}]  {masked}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
