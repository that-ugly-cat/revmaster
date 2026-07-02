import sqlite3
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
GLOBAL_DB = DATA_DIR / "global.db"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# Global db — users
# ──────────────────────────────────────────────────────────────────────────────

def init_global_db():
    DATA_DIR.mkdir(exist_ok=True)
    with _conn(GLOBAL_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username      TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'user',
                email         TEXT NOT NULL DEFAULT ''
            )
        """)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "email" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")


def global_has_users() -> bool:
    if not GLOBAL_DB.exists():
        return False
    init_global_db()
    with _conn(GLOBAL_DB) as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0


def create_global_user(username: str, password_hash: str, role: str = "user", email: str = ""):
    init_global_db()
    with _conn(GLOBAL_DB) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, email),
        )


def get_global_user(username: str) -> dict | None:
    if not GLOBAL_DB.exists():
        return None
    init_global_db()
    with _conn(GLOBAL_DB) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    return dict(row) if row else None


def list_global_users() -> list:
    if not GLOBAL_DB.exists():
        return []
    init_global_db()
    with _conn(GLOBAL_DB) as conn:
        rows = conn.execute(
            "SELECT username, role, email FROM users ORDER BY username"
        ).fetchall()
    return [dict(r) for r in rows]


def update_global_user_email(username: str, email: str):
    init_global_db()
    with _conn(GLOBAL_DB) as conn:
        conn.execute(
            "UPDATE users SET email = ? WHERE username = ?",
            (email, username),
        )


def delete_global_user(username: str):
    init_global_db()
    with _conn(GLOBAL_DB) as conn:
        conn.execute("DELETE FROM users WHERE username = ?", (username,))


def update_global_user_password(username: str, password_hash: str):
    init_global_db()
    with _conn(GLOBAL_DB) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (password_hash, username),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Per-project db — init
# ──────────────────────────────────────────────────────────────────────────────

def init_db(project_dir: Path):
    with _conn(project_dir / "revmaster.db") as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS papers (
                key              TEXT PRIMARY KEY,
                author           TEXT,
                publication_year INTEGER,
                title            TEXT,
                abstract         TEXT,
                item_type        TEXT,
                doi              TEXT,
                url              TEXT,
                manual_tags      TEXT,
                pdf_url          TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS assessments (
                key              TEXT NOT NULL,
                reviewer         TEXT NOT NULL,
                include_decision TEXT,
                country          TEXT DEFAULT '[]',
                study_year       INTEGER,
                study_type       TEXT,
                methodology      TEXT DEFAULT 'null',
                criteria_data    TEXT DEFAULT '{}',
                PRIMARY KEY (key, reviewer),
                FOREIGN KEY (key) REFERENCES papers(key)
            );
            CREATE TABLE IF NOT EXISTS project_members (
                username TEXT NOT NULL,
                role     TEXT NOT NULL DEFAULT 'reviewer',
                PRIMARY KEY (username)
            );
        """)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(papers)").fetchall()]
        if "pdf_url" not in cols:
            conn.execute("ALTER TABLE papers ADD COLUMN pdf_url TEXT DEFAULT ''")


# ──────────────────────────────────────────────────────────────────────────────
# Per-project db — papers
# ──────────────────────────────────────────────────────────────────────────────

def insert_papers(project_dir: Path, df):
    col_map = {c.lower(): c for c in df.columns}

    def get(row, *names):
        for n in names:
            if n in col_map:
                v = row.get(col_map[n], "")
                return "" if str(v) in ("nan", "None") else str(v)
        return ""

    with _conn(project_dir / "revmaster.db") as conn:
        for _, row in df.iterrows():
            key = get(row, "key")
            if not key:
                continue
            year_raw = get(row, "publication year")
            try:
                year = int(float(year_raw)) if year_raw else None
            except (ValueError, TypeError):
                year = None
            conn.execute(
                """
                INSERT OR IGNORE INTO papers
                    (key, author, publication_year, title, abstract,
                     item_type, doi, url, manual_tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    get(row, "author"),
                    year,
                    get(row, "title"),
                    get(row, "abstract note", "abstract"),
                    get(row, "item type"),
                    get(row, "doi"),
                    get(row, "url"),
                    get(row, "manual tags"),
                ),
            )


def get_papers(project_dir: Path) -> list:
    with _conn(project_dir / "revmaster.db") as conn:
        rows = conn.execute(
            "SELECT * FROM papers ORDER BY author, publication_year"
        ).fetchall()
    return [dict(r) for r in rows]


def save_paper_pdf_url(project_dir: Path, key: str, pdf_url: str):
    with _conn(project_dir / "revmaster.db") as conn:
        conn.execute(
            "UPDATE papers SET pdf_url = ? WHERE key = ?",
            (pdf_url, key),
        )


def clear_paper_pdf_url(project_dir: Path, key: str):
    with _conn(project_dir / "revmaster.db") as conn:
        conn.execute(
            "UPDATE papers SET pdf_url = '' WHERE key = ?",
            (key,),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Per-project db — assessments
# ──────────────────────────────────────────────────────────────────────────────

def get_assessment(project_dir: Path, key: str, reviewer: str) -> dict | None:
    with _conn(project_dir / "revmaster.db") as conn:
        row = conn.execute(
            "SELECT * FROM assessments WHERE key = ? AND reviewer = ?",
            (key, reviewer),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["country"] = json.loads(d.get("country") or "[]")
    d["methodology"] = json.loads(d.get("methodology") or "null")
    d["criteria_data"] = json.loads(d.get("criteria_data") or "{}")
    return d


def save_assessment(project_dir: Path, key: str, reviewer: str, data: dict):
    country = json.dumps(data.get("country") or [])
    methodology = json.dumps(data.get("methodology"))
    criteria_data = json.dumps(data.get("criteria_data") or {})
    with _conn(project_dir / "revmaster.db") as conn:
        conn.execute(
            """
            INSERT INTO assessments
                (key, reviewer, include_decision, country, study_year,
                 study_type, methodology, criteria_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key, reviewer) DO UPDATE SET
                include_decision = excluded.include_decision,
                country          = excluded.country,
                study_year       = excluded.study_year,
                study_type       = excluded.study_type,
                methodology      = excluded.methodology,
                criteria_data    = excluded.criteria_data
            """,
            (
                key, reviewer,
                data.get("include_decision", ""),
                country,
                data.get("study_year"),
                data.get("study_type", ""),
                methodology,
                criteria_data,
            ),
        )


def get_stats(project_dir: Path, reviewer: str | None = None) -> dict:
    """Stats for one reviewer, or aggregate across all reviewers if reviewer=None."""
    with _conn(project_dir / "revmaster.db") as conn:
        total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        if reviewer:
            q_base = "FROM assessments WHERE reviewer = ? AND"
            args = (reviewer,)
        else:
            q_base = "FROM assessments WHERE"
            args = ()
        assessed = conn.execute(
            f"SELECT COUNT(*) {q_base} include_decision IS NOT NULL AND include_decision != ''",
            args,
        ).fetchone()[0]
        included = conn.execute(
            f"SELECT COUNT(*) {q_base} include_decision = 'Yes'", args
        ).fetchone()[0]
        excluded = conn.execute(
            f"SELECT COUNT(*) {q_base} include_decision = 'No'", args
        ).fetchone()[0]
        maybe = conn.execute(
            f"SELECT COUNT(*) {q_base} include_decision = 'Maybe'", args
        ).fetchone()[0]
    return {
        "total": total,
        "assessed": assessed,
        "included": included,
        "excluded": excluded,
        "maybe": maybe,
    }


def get_all_assessments(project_dir: Path, reviewer: str | None = None) -> list:
    """All papers joined with assessments. If reviewer given, only their rows."""
    if reviewer:
        filter_clause = "AND a.reviewer = ?"
        args = (reviewer,)
    else:
        filter_clause = ""
        args = ()
    with _conn(project_dir / "revmaster.db") as conn:
        rows = conn.execute(
            f"""
            SELECT p.*,
                   a.reviewer,
                   a.include_decision,
                   a.country,
                   a.study_year       AS study_year_assessed,
                   a.study_type,
                   a.methodology,
                   a.criteria_data
            FROM papers p
            LEFT JOIN assessments a ON p.key = a.key {filter_clause}
            ORDER BY p.author, p.publication_year
            """,
            args,
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["country"] = json.loads(d.get("country") or "[]")
        d["methodology"] = json.loads(d.get("methodology") or "null")
        d["criteria_data"] = json.loads(d.get("criteria_data") or "{}")
        result.append(d)
    return result


def rename_criterion(project_dir: Path, old_name: str, new_name: str):
    """Rename a key in every assessment's criteria_data JSON blob."""
    with _conn(project_dir / "revmaster.db") as conn:
        rows = conn.execute(
            "SELECT key, reviewer, criteria_data FROM assessments"
        ).fetchall()
        for row in rows:
            data = json.loads(row["criteria_data"] or "{}")
            if old_name in data:
                data[new_name] = data.pop(old_name)
                conn.execute(
                    "UPDATE assessments SET criteria_data = ? WHERE key = ? AND reviewer = ?",
                    (json.dumps(data), row["key"], row["reviewer"]),
                )


def get_reviewer_summary(project_dir: Path) -> list:
    """Per-reviewer stats: list of {reviewer, assessed, included, excluded, maybe}."""
    with _conn(project_dir / "revmaster.db") as conn:
        rows = conn.execute(
            """
            SELECT
                reviewer,
                COUNT(*) AS assessed,
                SUM(CASE WHEN include_decision = 'Yes'   THEN 1 ELSE 0 END) AS included,
                SUM(CASE WHEN include_decision = 'No'    THEN 1 ELSE 0 END) AS excluded,
                SUM(CASE WHEN include_decision = 'Maybe' THEN 1 ELSE 0 END) AS maybe
            FROM assessments
            WHERE include_decision IS NOT NULL AND include_decision != ''
            GROUP BY reviewer
            ORDER BY reviewer
            """
        ).fetchall()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# Per-project db — members
# ──────────────────────────────────────────────────────────────────────────────

def add_project_member(project_dir: Path, username: str, role: str = "reviewer"):
    with _conn(project_dir / "revmaster.db") as conn:
        conn.execute(
            "INSERT OR REPLACE INTO project_members (username, role) VALUES (?, ?)",
            (username, role),
        )


def remove_project_member(project_dir: Path, username: str):
    with _conn(project_dir / "revmaster.db") as conn:
        conn.execute(
            "DELETE FROM project_members WHERE username = ?", (username,)
        )


def get_project_members(project_dir: Path) -> list:
    with _conn(project_dir / "revmaster.db") as conn:
        rows = conn.execute(
            "SELECT * FROM project_members ORDER BY role, username"
        ).fetchall()
    return [dict(r) for r in rows]


def get_member_role(project_dir: Path, username: str) -> str | None:
    with _conn(project_dir / "revmaster.db") as conn:
        row = conn.execute(
            "SELECT role FROM project_members WHERE username = ?", (username,)
        ).fetchone()
    return row[0] if row else None


def is_project_member(project_dir: Path, username: str) -> bool:
    return get_member_role(project_dir, username) is not None
