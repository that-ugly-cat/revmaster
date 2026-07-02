import json
import re
import shutil
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:50]


def list_projects() -> list:
    DATA_DIR.mkdir(exist_ok=True)
    projects = [
        d for d in DATA_DIR.iterdir()
        if d.is_dir() and (d / "config.json").exists()
    ]
    return sorted(projects, key=lambda d: d.stat().st_mtime, reverse=True)


def get_project_dir(slug: str) -> Path:
    return DATA_DIR / slug


def load_config(project_dir: Path) -> dict:
    with open(project_dir / "config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(project_dir: Path, config: dict):
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "pdfs").mkdir(exist_ok=True)
    with open(project_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def delete_project(project_dir: Path):
    shutil.rmtree(project_dir)


def create_project(
    title: str,
    description: str,
    inclusion_criteria: str,
    assessment_criteria: list,
    extra_fields: list | None = None,
) -> tuple:
    slug = _slugify(title)
    base = slug
    i = 2
    while (DATA_DIR / slug).exists():
        slug = f"{base}-{i}"
        i += 1
    project_dir = DATA_DIR / slug
    config = {
        "project_title": title,
        "project_description": description,
        "inclusion_criteria": inclusion_criteria,
        "assessment_criteria": assessment_criteria,
        "extra_fields": extra_fields or [],
        "created": str(date.today()),
        "slug": slug,
    }
    save_config(project_dir, config)
    return project_dir, slug
