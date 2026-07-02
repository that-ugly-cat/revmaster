<p align="center">
  <b>Self-hosted literature review assessment tool.</b><br>
  Multi-project workflows, per-reviewer independent screening, PDF management, IRR support.
</p>

---

RevMaster helps research teams screen and assess papers for a literature review. Import a
Zotero CSV export, invite reviewers to assess independently (title/abstract screening,
inclusion criteria, structured extra fields), fetch open-access PDFs automatically via
Unpaywall, and export the results for further analysis.

## Features

- **Multi-project dashboard**: each project has its own paper set, criteria, and members.
- **Zotero import**: CSV export → paper database, safe to re-import (dedup by `Key`).
- **Automatic PDF retrieval**: Unpaywall lookup by DOI, with filename-based matching for
  manually uploaded PDFs.
- **Independent per-reviewer assessment**: blind screening — reviewers never see each
  other's status until an admin reconciles.
- **Configurable criteria**: assessment criteria and extra metadata fields, addable/
  renamable after project creation (existing data migrates automatically on rename).
- **Analysis tab**: per-reviewer progress, bibliometric charts (year/authors/keywords),
  assessment charts (study year/country/type/methodology).
- **Roles**: admin (all projects, user management) vs reviewer (assigned projects only).

## Quick start

```bash
git clone https://github.com/that-ugly-cat/revmaster.git
cd revmaster
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 — the first visit shows a setup screen to create the admin
account (no separate `.env`/secret config needed).

## Stack

Streamlit · SQLite · bcrypt. No build step, no external services beyond Unpaywall (optional,
for automatic PDF retrieval).

```
app.py       — Streamlit UI (dashboard, project view, assessment, admin)
auth.py      — password hashing (bcrypt)
db.py        — SQLite schema and queries
project.py   — project/paper/assessment logic
pdf_fetch.py — Unpaywall lookup + PDF matching
configs/     — dropdown option lists (countries, study types, methodology)
```

## Deployment

See **[docs.md](docs.md)** for the full user guide (setup, Zotero import, PDF management,
multi-reviewer/IRR, analysis).

Docker: `docker-compose.yml` maps the app to `127.0.0.1:8501` and mounts `./data` for the
SQLite database and uploaded PDFs.

```bash
docker compose up -d --build
```

Put it behind a reverse proxy (Caddy/nginx) that terminates TLS for production use.

## Tech notes

- All app state (users, projects, papers, assessments, uploaded PDFs) lives under `data/` —
  back up by copying the folder.
- No cloud dependencies — everything runs locally except optional Unpaywall PDF lookups.
