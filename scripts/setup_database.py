"""
Phase 5 (DEC-012) — secure database provisioning for the pilot application.

WHY THIS SCRIPT EXISTS
----------------------
The project's existing PostgreSQL 18 installation uses `scram-sha-256` for every
`pg_hba.conf` entry and no administrator password was ever recorded, so the
application cannot connect to it without credentials that this project does not
have and must not guess (Phase 5 Requirement #2: "Do not assume the PostgreSQL
administrator password").

This script offers two secure ways forward and never weakens authentication:

  A) --init-local-cluster   Create a SEPARATE, project-local PostgreSQL cluster
                            inside the repository (`.pgdata/`, git-ignored) on a
                            non-default port, bound to 127.0.0.1 only, with
                            scram-sha-256 auth and a randomly generated
                            administrator password. It does not read, modify or
                            require the password of the existing installation.
                            No Windows service is registered; start/stop are
                            explicit (`--start` / `--stop`).

  B) --existing             Use the already-running server. The administrator
                            password is typed at an interactive prompt
                            (`getpass` — never echoed, never written to disk,
                            never passed on a command line where it would land in
                            shell history).

Both paths end by creating:
  * role  `pesticide_app`      LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE
  * db    `pesticide_advisory` owner = pesticide_app
and by writing `DATABASE_URL` into `backend/.env` (git-ignored).

WHAT NEVER HAPPENS HERE
-----------------------
* `pg_hba.conf` is never set to `trust`, `peer` or any password-less method.
* The server is never bound to 0.0.0.0 / ::  .
* No password is ever hardcoded, committed, logged or echoed.
* The app role is never granted SUPERUSER, CREATEDB or CREATEROLE.

USAGE (from the repository root, backend venv active)
-----------------------------------------------------
    python scripts/setup_database.py --status
    python scripts/setup_database.py --init-local-cluster
    python scripts/setup_database.py --start
    python scripts/setup_database.py --stop
    python scripts/setup_database.py --existing          # prompts for admin password
    python scripts/setup_database.py --print-env         # re-emit URL from .env (masked)
"""
from __future__ import annotations

import argparse
import getpass
import os
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
ENV_FILE = BACKEND_DIR / ".env"
PGDATA_DIR = REPO_ROOT / ".pgdata"
LOCAL_PORT = 55432
LOCAL_ADMIN = "pesticide_admin"
APP_ROLE = "pesticide_app"
APP_DB = "pesticide_advisory"
MIN_PG_MAJOR = 14


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def find_pg_bin(explicit: str | None = None) -> pathlib.Path:
    """Locate a PostgreSQL bin/ directory without requiring PATH configuration."""
    if explicit:
        p = pathlib.Path(explicit)
        if (p / "initdb.exe").exists() or (p / "initdb").exists():
            return p
        raise SystemExit(f"--pg-bin {explicit} does not contain initdb.")

    candidates: list[pathlib.Path] = []
    if os.name == "nt":
        for base in (r"C:\Program Files\PostgreSQL", r"C:\Program Files (x86)\PostgreSQL"):
            root = pathlib.Path(base)
            if root.is_dir():
                candidates.extend(sorted(root.glob("*/bin"), reverse=True))
    else:
        for base in ("/usr/lib/postgresql", "/usr/local/pgsql", "/opt/homebrew/opt"):
            root = pathlib.Path(base)
            if root.is_dir():
                candidates.extend(sorted(root.glob("*/bin"), reverse=True))
        if not candidates:
            candidates.append(pathlib.Path("/usr/bin"))

    for cand in candidates:
        if (cand / "initdb").exists() or (cand / "initdb.exe").exists():
            return cand

    found = shutil.which("initdb")
    if found:
        return pathlib.Path(found).parent
    raise SystemExit("Could not find PostgreSQL binaries. Pass --pg-bin <path to bin>.")


def pg_version(bin_dir: pathlib.Path) -> str:
    exe = bin_dir / ("pg_ctl.exe" if os.name == "nt" else "pg_ctl")
    out = subprocess.run([str(exe), "--version"], capture_output=True, text=True)
    return (out.stdout or out.stderr).strip()


def run(cmd: list[str], *, env: dict | None = None, quiet: bool = False) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0 and not quiet:
        print(f"  ! command failed ({proc.returncode}): {' '.join(cmd[:3])} ...")
        err = (proc.stderr or proc.stdout or "").strip()
        if err:
            print("    " + err.replace("\n", "\n    "))
    return proc


def run_detached(cmd: list[str], *, timeout: float = 90.0) -> tuple[int, str]:
    """
    Run a command that spawns a long-lived server process (pg_ctl start/stop).

    `subprocess.run(capture_output=True)` must NOT be used here: pg_ctl launches
    the postmaster, the postmaster inherits the stdout/stderr pipe, and
    `subprocess.run` reads that pipe until EOF — which never arrives while the
    server is alive. That is a real hang, not a slow start, and it cost two
    debugging cycles to find.

    So output goes to the (already configured) server log file, and readiness is
    confirmed by probing the TCP port instead of by reading a pipe.
    """
    proc = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=timeout,
    )
    return proc.returncode, ""


def wait_for_port(host: str, port: int, *, timeout: float = 60.0) -> bool:
    """Bounded wait for a TCP listener. Returns False instead of raising."""
    import socket

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.25)
    return False


def mask_url(url: str) -> str:
    """Never print a password, even in diagnostics."""
    return re.sub(r"(://[^:/@]+:)[^@]+(@)", r"\1********\2", url)


def read_env() -> dict[str, str]:
    data: dict[str, str] = {}
    if not ENV_FILE.exists():
        return data
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k, _, v = stripped.partition("=")
        data[k.strip()] = v.strip()
    return data


def write_env(updates: dict[str, str]) -> None:
    """
    Upsert keys in backend/.env without disturbing unrelated values or comments.
    backend/.env is git-ignored; the repository only ever contains .env.example.
    """
    existing = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    seen: set[str] = set()
    out: list[str] = []
    for line in existing:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if m and m.group(1) in updates:
            key = m.group(1)
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    if not out:
        out = ["# Local environment (git-ignored). Generated by scripts/setup_database.py."]
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    try:  # best effort on POSIX; no-op on Windows NTFS without ACL tooling
        os.chmod(ENV_FILE, 0o600)
    except OSError:
        pass


def connect(host: str, port: int, user: str, password: str, dbname: str):
    import psycopg2

    return psycopg2.connect(
        host=host, port=port, user=user, password=password, dbname=dbname,
        connect_timeout=10, application_name="pesticide_advisory_setup",
    )


# ---------------------------------------------------------------------------
# schema provisioning (shared by both paths)
# ---------------------------------------------------------------------------
def provision_app_role(
    conn,
    app_password: str,
    *,
    host: str,
    port: int,
    admin_user: str,
    admin_password: str,
) -> None:
    """
    Idempotently create the least-privilege application role and database.

    The generated app password is embedded in a psycopg2 parameterised statement
    (server-side quoting) rather than string-formatted SQL, so it cannot break
    out of the literal even though PostgreSQL DDL cannot take a bound parameter
    for a password.
    """
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
        if cur.fetchone() is None:
            cur.execute(
                f'CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                f'NOINHERIT NOREPLICATION PASSWORD %s',
                (app_password,),
            )
            print(f"  + created role {APP_ROLE} (NOSUPERUSER, NOCREATEDB, NOCREATEROLE)")
        else:
            cur.execute(f"ALTER ROLE {APP_ROLE} PASSWORD %s", (app_password,))
            print(f"  ~ role {APP_ROLE} exists; password rotated")

        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (APP_DB,))
        if cur.fetchone() is None:
            cur.execute(f'CREATE DATABASE "{APP_DB}" OWNER {APP_ROLE} ENCODING \'UTF8\'')
            print(f"  + created database {APP_DB} (owner {APP_ROLE})")
        else:
            print(f"  ~ database {APP_DB} exists")

    # Database-level privileges: no PUBLIC access, app role owns its schema.
    #
    # The credentials are passed explicitly rather than read back from the
    # existing connection: psycopg2 does not always retain the password, and a
    # missing password makes libpq fall back to an interactive prompt — which
    # hangs an unattended script. Always supply it.
    admin_db = connect(host, port, admin_user, admin_password, APP_DB)
    admin_db.autocommit = True
    with admin_db.cursor() as cur:
        cur.execute(f'REVOKE ALL ON DATABASE "{APP_DB}" FROM PUBLIC')
        cur.execute(f'GRANT CONNECT, TEMPORARY ON DATABASE "{APP_DB}" TO {APP_ROLE}')
        cur.execute(f'GRANT ALL ON SCHEMA public TO {APP_ROLE}')
    admin_db.close()
    print("  + privileges: PUBLIC revoked, pesticide_app granted CONNECT/TEMP + schema ownership")





def verify_app_login(host: str, port: int, app_password: str) -> tuple[bool, str]:
    try:
        c = connect(host, port, APP_ROLE, app_password, APP_DB)
        with c.cursor() as cur:
            cur.execute("SELECT current_user, current_database(), version()")
            user, db, version = cur.fetchone()
            cur.execute("SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = current_user")
            rolsuper, rolcreatedb, rolcreaterole = cur.fetchone()
        c.close()
        if rolsuper or rolcreatedb or rolcreaterole:
            return False, f"role has elevated attributes (super={rolsuper}, createdb={rolcreatedb}, createrole={rolcreaterole})"
        return True, f"logged in as {user} to {db} without elevated privileges"
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        return False, str(exc).strip()


# ---------------------------------------------------------------------------
# path A: project-local cluster
# ---------------------------------------------------------------------------
def init_local_cluster(bin_dir: pathlib.Path, port: int) -> str:
    if PGDATA_DIR.exists() and any(PGDATA_DIR.iterdir()):
        raise SystemExit(
            f"{PGDATA_DIR} already exists and is not empty. Use --start, or remove it deliberately."
        )
    PGDATA_DIR.mkdir(parents=True, exist_ok=True)
    admin_password = secrets.token_urlsafe(24)

    # mkstemp returns an open descriptor; on Windows that lock prevents unlink,
    # so it is closed immediately. The file itself is deleted in `finally`.
    fd, pwfile_name = tempfile.mkstemp(suffix=".pw")
    os.close(fd)
    pwfile = pathlib.Path(pwfile_name)
    try:
        pwfile.write_text(admin_password, encoding="utf-8")
        initdb = bin_dir / ("initdb.exe" if os.name == "nt" else "initdb")
        print(f"  initialising cluster at {PGDATA_DIR} (port {port}, loopback only)")
        proc = run([
            str(initdb),
            "-D", str(PGDATA_DIR),
            "-U", LOCAL_ADMIN,
            f"--pwfile={pwfile}",
            "--auth-host=scram-sha-256",
            "--auth-local=scram-sha-256",
            "--encoding=UTF8",
            "--locale=C",
        ])
        if proc.returncode != 0:
            raise SystemExit("initdb failed — see the message above.")
    finally:
        pwfile.unlink(missing_ok=True)

    # Tighten the defaults for an 8 GB development laptop, and make the
    # authentication/binding posture explicit and auditable.
    overrides = f"""
# --- Pesticide Advisory pilot overrides (Phase 5, DEC-012) ---
port = {port}
listen_addresses = '127.0.0.1'
shared_buffers = 128MB
work_mem = 8MB
maintenance_work_mem = 64MB
effective_cache_size = 512MB
max_connections = 20
logging_collector = off
log_min_duration_statement = 500
"""
    with (PGDATA_DIR / "postgresql.conf").open("a", encoding="utf-8") as fh:
        fh.write(overrides)

    start_local_cluster(bin_dir, port)

    # The superuser password is needed for exactly one optional operation later
    # (CREATE EXTENSION vector, which requires superuser). Losing it would mean
    # re-initialising the whole cluster, so it is written to a 0600 file *inside
    # the git-ignored data directory* — never to source, never to .env, never to
    # a log. It is a local development credential for a loopback-only cluster.
    creds = PGDATA_DIR / "admin-credentials.json"
    import json

    creds.write_text(
        json.dumps(
            {
                "note": "Local development superuser for the project-local PostgreSQL cluster. "
                        "Git-ignored. Delete this file and re-initialise if it is ever exposed.",
                "role": LOCAL_ADMIN,
                "password": admin_password,
                "host": "127.0.0.1",
                "port": port,
                "database": "postgres",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    try:
        os.chmod(creds, 0o600)
    except OSError:
        pass

    return admin_password


def start_local_cluster(bin_dir: pathlib.Path, port: int = LOCAL_PORT) -> None:
    pg_ctl = bin_dir / ("pg_ctl.exe" if os.name == "nt" else "pg_ctl")
    logfile = PGDATA_DIR / "server.log"
    code, _ = run_detached([str(pg_ctl), "-D", str(PGDATA_DIR), "-l", str(logfile), "start"])
    if not wait_for_port("127.0.0.1", port, timeout=60):
        tail = ""
        if logfile.exists():
            tail = "\n".join(logfile.read_text(encoding="utf-8", errors="replace").splitlines()[-15:])
        raise SystemExit(f"server did not become reachable on 127.0.0.1:{port}.\n{tail}")
    print(f"  + server reachable on 127.0.0.1:{port} (exit={code}, log: {logfile})")


def stop_local_cluster(bin_dir: pathlib.Path, port: int = LOCAL_PORT) -> None:
    pg_ctl = bin_dir / ("pg_ctl.exe" if os.name == "nt" else "pg_ctl")
    pidfile = PGDATA_DIR / "postmaster.pid"
    if not pidfile.exists():
        print("  ! no postmaster.pid — the cluster does not appear to be running")
        return
    code, _ = run_detached([str(pg_ctl), "-D", str(PGDATA_DIR), "-m", "fast", "stop"], timeout=60)
    # Confirm by probing the port rather than trusting the exit code alone.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                print(f"  + server stopped (port {port} closed)")
                return
        time.sleep(0.5)
    print(f"  ! stop requested (exit={code}) but port {port} is still accepting connections")


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def status() -> int:
    print("PostgreSQL installation")
    print("-----------------------")
    try:
        bin_dir = find_pg_bin()
        print(f"  binaries : {bin_dir}")
        print(f"  version  : {pg_version(bin_dir)}")
    except SystemExit as exc:
        print(f"  ! {exc}")
        return 1

    ext = list(bin_dir.parent.glob("share/extension/vector*")) if (bin_dir.parent / "share").is_dir() else []
    print(f"  pgvector : {'installed (' + str(len(ext)) + ' files)' if ext else 'NOT INSTALLED (no share/extension/vector*)'}")

    print()
    print("Project-local cluster (.pgdata)")
    print("-------------------------------")
    print(f"  exists   : {PGDATA_DIR.exists()}")
    pg_ctl = bin_dir / ("pg_ctl.exe" if os.name == "nt" else "pg_ctl")
    running = run([str(pg_ctl), "-D", str(PGDATA_DIR), "status"], quiet=True).returncode == 0 if PGDATA_DIR.exists() else False
    print(f"  running  : {running}")

    print()
    print("Configuration")
    print("-------------")
    env = read_env()
    url = env.get("DATABASE_URL", "")
    print(f"  backend/.env DATABASE_URL : {mask_url(url) if url else '(not set)'}")
    m = re.match(r"postgresql(?:\+\w+)?://([^:/@]+):[^@]*@([^:/]+):(\d+)/(\w+)", url)
    if m:
        user, host, port, db = m.group(1), m.group(2), int(m.group(3)), m.group(4)
        print(f"  parsed    : user={user} host={host} port={port} db={db}")
    print(f"  KB_REPOSITORY            : {env.get('KB_REPOSITORY', '(unset → json)')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provision the pilot PostgreSQL database securely.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--init-local-cluster", action="store_true",
                       help="create a separate project-local cluster (no admin password needed)")
    group.add_argument("--existing", action="store_true",
                       help="provision against an already-running server (prompts for admin password)")
    group.add_argument("--start", action="store_true", help="start the project-local cluster")
    group.add_argument("--stop", action="store_true", help="stop the project-local cluster")
    group.add_argument("--status", action="store_true", help="report installation and configuration state")
    group.add_argument("--verify", action="store_true", help="verify the app role can log in as configured")
    parser.add_argument("--pg-bin", default=None, help="path to the PostgreSQL bin directory")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=LOCAL_PORT)
    parser.add_argument("--admin-user", default="postgres")
    args = parser.parse_args(argv)

    bin_dir = find_pg_bin(args.pg_bin)

    if args.status:
        return status()

    if args.start:
        start_local_cluster(bin_dir)
        return 0

    if args.stop:
        stop_local_cluster(bin_dir)
        return 0

    if args.verify:
        url = read_env().get("DATABASE_URL", "")
        m = re.match(r"postgresql(?:\+\w+)?://([^:/@]+):([^@]*)@([^:/]+):(\d+)/(\w+)", url)
        if not m:
            print("No usable DATABASE_URL in backend/.env")
            return 1
        user, password, host, port, db = m.group(1), m.group(2), m.group(3), int(m.group(4)), m.group(5)
        ok, msg = verify_app_login(host, port, password)
        print(("OK   " if ok else "FAIL ") + msg)
        return 0 if ok else 1

    if args.init_local_cluster:
        print(f"Provisioning a project-local PostgreSQL cluster (separate from any existing install).")
        print(f"  version: {pg_version(bin_dir)}")
        admin_password = init_local_cluster(bin_dir, args.port)
        app_password = secrets.token_urlsafe(24)
        conn = connect("127.0.0.1", args.port, LOCAL_ADMIN, admin_password, "postgres")
        try:
            provision_app_role(
                conn, app_password,
                host="127.0.0.1", port=args.port,
                admin_user=LOCAL_ADMIN, admin_password=admin_password,
            )
        finally:
            conn.close()
        url = f"postgresql://{APP_ROLE}:{app_password}@127.0.0.1:{args.port}/{APP_DB}"
        write_env({"DATABASE_URL": url})
        print(f"  + wrote DATABASE_URL to {ENV_FILE.relative_to(REPO_ROOT)} (git-ignored)")
        ok, msg = verify_app_login("127.0.0.1", args.port, app_password)
        print(("  OK   " if ok else "  FAIL ") + msg)
        print(f"  superuser '{LOCAL_ADMIN}' credential: .pgdata/admin-credentials.json (git-ignored, 0600). "
              f"Not needed for normal application use — only to enable optional extensions.")
        return 0 if ok else 1

    if args.existing:
        print(f"Provisioning against the existing server at {args.host}:{args.port}.")
        print("The administrator password is read from an interactive prompt and is never stored or logged.")
        try:
            admin_password = getpass.getpass(f"  password for PostgreSQL role '{args.admin_user}': ")
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return 130
        if not admin_password:
            print("No password supplied — nothing changed.")
            return 1
        app_password = secrets.token_urlsafe(24)
        conn = connect(args.host, args.port, args.admin_user, admin_password, "postgres")
        try:
            provision_app_role(
                conn, app_password,
                host=args.host, port=args.port,
                admin_user=args.admin_user, admin_password=admin_password,
            )
        finally:
            conn.close()
        url = f"postgresql://{APP_ROLE}:{app_password}@{args.host}:{args.port}/{APP_DB}"
        write_env({"DATABASE_URL": url})
        print(f"  + wrote DATABASE_URL to {ENV_FILE.relative_to(REPO_ROOT)} (git-ignored)")
        ok, msg = verify_app_login(args.host, args.port, app_password)
        print(("  OK   " if ok else "  FAIL ") + msg)
        return 0 if ok else 1

    parser.print_help()
    print("\nNo action selected. Run --status first.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
