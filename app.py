import base64
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

import auth
import db
import pdf_fetch
import project as proj

# ──────────────────────────────────────────────────────────────────────────────
# Page config (must be first Streamlit call)
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="RevMaster",
    page_icon=":books:",
    layout="wide",
    menu_items={"About": "RevMaster v2 — literature review assessment tool"},
)

# ──────────────────────────────────────────────────────────────────────────────
# Config helpers
# ──────────────────────────────────────────────────────────────────────────────

CONFIGS_DIR = Path(__file__).parent / "configs"

METH_CATEGORIES = {
    "Observational vs Experimental": ["Observational", "Experimental"],
    "Descriptive vs Analytical": ["Descriptive", "Analytical"],
    "Qualitative vs Quantitative": ["Qualitative", "Quantitative", "Mixed methods"],
    "Longitudinal vs Cross-sectional": ["Longitudinal", "Cross-sectional"],
}
LITREV_TYPES = [
    "Traditional (narrative) review", "Rapid review",
    "Scoping review", "Systematic review", "Meta analysis",
]


def _load_lines(name: str) -> list:
    p = CONFIGS_DIR / name
    return [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def _load_text(name: str) -> str:
    p = CONFIGS_DIR / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


@st.cache_data
def get_include_options():
    return _load_lines("include_options.txt") or ["Yes", "Maybe", "No"]

@st.cache_data
def get_country_options():
    return _load_lines("country_options.txt")

@st.cache_data
def get_study_type_options():
    return _load_lines("study_type_options.txt")

@st.cache_data
def get_methodology_empirical():
    return _load_lines("methodology_options_empirical.txt")

@st.cache_data
def get_methodology_litrev():
    return _load_lines("methodology_options_litrev.txt")

@st.cache_data
def get_methodology_empirical_explanation():
    return _load_text("methodology_options_empirical_explanation.txt")

@st.cache_data
def get_methodology_litrev_explanation():
    return _load_text("methodology_options_litrev_explanation.txt")


# ──────────────────────────────────────────────────────────────────────────────
# PDF helpers
# ──────────────────────────────────────────────────────────────────────────────

def _show_pdf(file_path: str):
    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{encoded}" '
        f'width="100%" height="1200" type="application/pdf"></iframe>',
        unsafe_allow_html=True,
    )


def _find_pdf(project_dir: Path, author: str, title: str, year: int | None = None) -> str | None:
    pdfs_dir = project_dir / "pdfs"
    if not pdfs_dir.exists():
        return None
    surnames = [b.split(",")[0].strip() for b in author.split(";") if b.strip()]
    if not surnames:
        return None
    import re as _re
    first_surname = surnames[0].lower()
    first_surname_norm = _re.sub(r"[^a-z0-9]", "", first_surname)
    candidates = [
        f for f in pdfs_dir.iterdir()
        if f.is_file() and f.suffix.lower() == ".pdf"
        and (first_surname in f.name.lower() or first_surname_norm in f.name.lower())
    ]
    if len(candidates) == 1:
        return str(candidates[0])
    if len(candidates) > 1:
        first_words = " ".join(title.split()[:2]).lower()
        filtered = [f for f in candidates if first_words in f.name.lower()]
        if len(filtered) == 1:
            return str(filtered[0])
        if year:
            filtered2 = [f for f in candidates if str(year) in f.name]
            if len(filtered2) == 1:
                return str(filtered2[0])
        return str(candidates[0])
    return None


# ──────────────────────────────────────────────────────────────────────────────
# PDF mapping helper
# ──────────────────────────────────────────────────────────────────────────────

def _build_pdf_mapping(project_dir: Path, papers: list) -> tuple:
    """
    Returns:
      paper_to_pdf : {paper_key: pdf_filename | None}
      pdf_to_paper : {pdf_filename: paper_dict | None}
    """
    pdfs_dir = project_dir / "pdfs"
    pdf_to_paper: dict = {}
    if pdfs_dir.exists():
        for f in sorted(pdfs_dir.iterdir()):
            if f.is_file() and f.suffix.lower() == ".pdf":
                pdf_to_paper[f.name] = None

    paper_to_pdf: dict = {}
    for paper in papers:
        found = _find_pdf(project_dir, paper.get("author", ""), paper.get("title", ""), paper.get("publication_year"))
        if found:
            fname = Path(found).name
            paper_to_pdf[paper["key"]] = fname
            pdf_to_paper[fname] = paper
        else:
            paper_to_pdf[paper["key"]] = None

    return paper_to_pdf, pdf_to_paper


# ──────────────────────────────────────────────────────────────────────────────
# Export helper
# ──────────────────────────────────────────────────────────────────────────────

def _export_excel(project_dir: Path) -> bytes:
    config = proj.load_config(project_dir)
    rows = db.get_all_assessments(project_dir)
    df = pd.DataFrame(rows)

    if "country" in df.columns:
        df["country"] = df["country"].apply(
            lambda v: "; ".join(v) if isinstance(v, list) else (str(v) if v else "")
        )

    if "criteria_data" in df.columns:
        ordered_keys = config.get("extra_fields", []) + config.get("assessment_criteria", [])
        criteria_df = pd.json_normalize(
            df["criteria_data"].apply(lambda v: v if isinstance(v, dict) else {})
        )
        known = [k for k in ordered_keys if k in criteria_df.columns]
        extra = [k for k in criteria_df.columns if k not in ordered_keys]
        criteria_df = criteria_df[known + extra]
        df = pd.concat([df.drop(columns=["criteria_data"]), criteria_df], axis=1)

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# Auth helpers
# ──────────────────────────────────────────────────────────────────────────────

def current_user() -> dict | None:
    return st.session_state.get("user")


def is_admin() -> bool:
    u = current_user()
    return u is not None and u.get("role") == "admin"


def can_manage_project(project_dir: Path) -> bool:
    u = current_user()
    if not u:
        return False
    if u["role"] == "admin":
        return True
    return db.get_member_role(project_dir, u["username"]) == "owner"


# ──────────────────────────────────────────────────────────────────────────────
# View: first-run setup
# ──────────────────────────────────────────────────────────────────────────────

def view_setup():
    st.title("RevMaster — first setup")
    st.info("No users found. Create the admin account to get started.")

    with st.form("setup_form"):
        username = st.text_input("Admin username *")
        email = st.text_input("Email", placeholder="used for PDF retrieval via Unpaywall")
        pw = st.text_input("Password *", type="password")
        pw2 = st.text_input("Confirm password *", type="password")
        submitted = st.form_submit_button("Create admin account", type="primary")

    if submitted:
        errors = []
        if not username.strip():
            errors.append("Username is required.")
        if not pw:
            errors.append("Password is required.")
        if pw != pw2:
            errors.append("Passwords do not match.")
        if errors:
            for e in errors:
                st.error(e)
        else:
            db.create_global_user(username.strip(), auth.hash_password(pw), role="admin", email=email.strip())
            st.success("Admin account created. Please log in.")
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# View: login
# ──────────────────────────────────────────────────────────────────────────────

@st.dialog("Documentation", width="large")
def _dialog_docs():
    docs_path = Path(__file__).parent / "docs.md"
    if docs_path.exists():
        st.markdown(docs_path.read_text(encoding="utf-8"), unsafe_allow_html=False)
    else:
        st.error("Documentation file not found.")


def view_login():
    col_land, col_gap, col_login = st.columns([3, 1, 2])

    with col_land:
        st.title(":books: RevMaster")
        st.subheader("A structured tool for literature review assessment")
        st.write(
            "RevMaster replaces the spreadsheet-based workflow typical of systematic and "
            "scoping reviews. Instead of annotating rows in Excel, you open a paper and fill "
            "in structured assessment fields side by side with the PDF — then move to the next."
        )
        st.divider()

        st.markdown("**What you can do with RevMaster**")
        st.markdown(
            "- **Multi-project dashboard** — manage multiple review projects from a single interface\n"
            "- **Per-reviewer assessments** — each team member saves their own independent evaluation, "
            "enabling double-blind screening and inter-rater comparisons\n"
            "- **Structured fields** — inclusion decision, country, study type, methodology, "
            "and fully customisable free-text assessment criteria defined at project creation\n"
            "- **PDF viewer** — read the paper and fill in the assessment on the same screen\n"
            "- **Progress tracking** — see how many papers each reviewer has assessed, "
            "and which ones still need attention\n"
            "- **Excel export** — export the full assessment dataset at any time for further analysis"
        )
        st.divider()

        st.markdown("**Typical workflow**")
        st.markdown(
            "1. Run your literature search and export results from Zotero (CSV)\n"
            "2. Admin creates a project, uploads the CSV, defines assessment criteria\n"
            "3. Reviewers are assigned to the project and start assessing papers\n"
            "4. Export the final dataset and proceed to evidence synthesis"
        )
        st.divider()
        col_doc, col_contact = st.columns([1, 3])
        with col_doc:
            if st.button("Documentation", use_container_width=True):
                _dialog_docs()
        with col_contact:
            st.caption(
                "Need an account, need to complain, or want to offer someone a coffee? "
                "[Get in touch with Giovanni](https://www.giovannispitale.net/)"
            )

    with col_login:
        st.write("")
        st.write("")
        with st.container(border=True):
            st.subheader("Sign in")
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
            if submitted:
                user = db.get_global_user(username)
                if user and auth.check_password(password, user["password_hash"]):
                    st.session_state["user"] = {"username": user["username"], "role": user["role"]}
                    st.session_state["view"] = "dashboard"
                    st.rerun()
                else:
                    st.error("Wrong username or password.")


# ──────────────────────────────────────────────────────────────────────────────
# View: dashboard
# ──────────────────────────────────────────────────────────────────────────────

def view_dashboard():
    user = current_user()

    with st.sidebar:
        st.write(f"**{user['username']}**")
        if is_admin():
            st.caption("admin")
            if st.button("Admin panel", use_container_width=True):
                st.session_state["view"] = "admin"
                st.rerun()
        st.divider()
        u_full = db.get_global_user(user["username"]) or {}
        current_email = u_full.get("email") or ""
        with st.expander("My profile"):
            new_email = st.text_input("Email", value=current_email, key="sidebar_email",
                                      placeholder="used for PDF retrieval")
            if st.button("Save email", use_container_width=True, key="save_email_btn"):
                db.update_global_user_email(user["username"], new_email.strip())
                st.success("Saved.")
        st.divider()
        if st.button("Documentation", use_container_width=True):
            st.session_state["view"] = "docs"
            st.rerun()
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    col_h, col_btn = st.columns([5, 1])
    with col_h:
        st.title("RevMaster")
    with col_btn:
        st.write("")
        if is_admin() and st.button("+ New project", type="primary", use_container_width=True):
            st.session_state["view"] = "new_project"
            st.rerun()

    # Admin sees all projects; regular users see only their projects
    all_projects = proj.list_projects()
    if is_admin():
        projects = all_projects
    else:
        projects = [
            p for p in all_projects
            if db.is_project_member(p, user["username"])
        ]

    if not projects:
        if is_admin():
            st.info("No projects yet. Create the first one.")
        else:
            st.info("You have not been assigned to any project yet.")
        return

    for p_dir in projects:
        db.init_db(p_dir)
        config = proj.load_config(p_dir)
        stats = db.get_stats(p_dir)
        my_stats = db.get_stats(p_dir, reviewer=user["username"])
        pct = int(my_stats["assessed"] / stats["total"] * 100) if stats["total"] else 0

        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 1, 1])
            with c1:
                st.subheader(config["project_title"])
                if config.get("project_description"):
                    st.caption(config["project_description"])
                st.progress(
                    pct / 100,
                    text=(
                        f"Your progress: {my_stats['assessed']} / {stats['total']} papers  ·  "
                        f"✅ {my_stats['included']}  ·  ❌ {my_stats['excluded']}  ·  ❔ {my_stats['maybe']}"
                    ),
                )
            with c2:
                members = db.get_project_members(p_dir)
                st.metric("Papers", stats["total"])
                st.metric("Reviewers", len(members))
            with c3:
                st.write("")
                st.write("")
                if st.button("Open", key=f"open_{p_dir.name}", use_container_width=True, type="primary"):
                    st.session_state["view"] = f"project:{p_dir.name}"
                    st.rerun()
                if st.button("Files", key=f"files_{p_dir.name}", use_container_width=True):
                    st.session_state["view"] = f"files:{p_dir.name}"
                    st.rerun()
                user_role = db.get_member_role(p_dir, user["username"])
                if is_admin() or user_role == "owner":
                    if st.button("Delete", key=f"del_{p_dir.name}", use_container_width=True):
                        _dialog_delete_project(p_dir.name, config["project_title"])

    st.divider()
    docs_path = Path(__file__).parent / "docs.md"
    if docs_path.exists():
        with st.expander("Documentation"):
            st.markdown(docs_path.read_text(encoding="utf-8"), unsafe_allow_html=False)


# ──────────────────────────────────────────────────────────────────────────────
# View: new project (admin only)
# ──────────────────────────────────────────────────────────────────────────────

def view_new_project():
    if st.button("← Back"):
        st.session_state["view"] = "dashboard"
        st.rerun()

    st.title("New project")

    with st.form("new_project_form"):
        st.subheader("Project details")
        title = st.text_input("Project title *", placeholder="e.g. Ethics of AI in clinical decision-making")
        description = st.text_area("Description", placeholder="Brief description shown on the dashboard.")
        inclusion_criteria = st.text_area("Inclusion criteria", height=120)

        st.divider()
        st.subheader("Assessment criteria")
        criteria_raw = st.text_area(
            "One criterion per line *",
            placeholder="e.g.\nMain ethical issues identified\nRecommendations proposed",
            height=140,
        )

        st.divider()
        st.subheader("Extra fields")
        st.caption(
            "Optional single-line fields shown in the structured section of the assessment panel. "
            "One per line."
        )
        extra_fields_raw = st.text_area(
            "Extra fields",
            placeholder="e.g.\nHealth emergency / issue\nContext\nDomain\nFunding source\nTarget population\nJurisdiction",
            height=130,
            label_visibility="collapsed",
        )

        st.divider()
        st.subheader("Papers (CSV)")
        st.caption("Zotero export format. Required columns: Key, Author, Title, Publication Year.")
        uploaded_csv = st.file_uploader("CSV file", type=["csv"])

        submitted = st.form_submit_button("Create project", type="primary")

    if uploaded_csv is not None:
        try:
            preview = pd.read_csv(uploaded_csv)
            show_cols = [c for c in ["Key", "Author", "Title", "Publication Year"] if c in preview.columns]
            st.dataframe(preview[show_cols].head(5), use_container_width=True, hide_index=True)
            uploaded_csv.seek(0)
        except Exception as e:
            st.error(f"Error reading CSV: {e}")

    if submitted:
        errors = []
        if not title.strip():
            errors.append("Project title is required.")
        if not criteria_raw.strip():
            errors.append("Assessment criteria are required.")
        if uploaded_csv is None:
            errors.append("A CSV file is required.")
        if errors:
            for e in errors:
                st.error(e)
        else:
            criteria = [c.strip() for c in criteria_raw.splitlines() if c.strip()]
            extra_fields = [f.strip() for f in extra_fields_raw.splitlines() if f.strip()]
            project_dir, slug = proj.create_project(
                title.strip(), description.strip(), inclusion_criteria.strip(),
                criteria, extra_fields,
            )
            db.init_db(project_dir)
            df = pd.read_csv(uploaded_csv)
            db.insert_papers(project_dir, df)
            # creator becomes owner
            db.add_project_member(project_dir, current_user()["username"], role="owner")
            st.success(f"Project created — {len(df)} papers imported.")
            st.session_state["view"] = f"project:{slug}"
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# View: project
# ──────────────────────────────────────────────────────────────────────────────

def view_project(slug: str):
    user = current_user()
    project_dir = proj.get_project_dir(slug)

    if not project_dir.exists():
        st.error("Project not found.")
        st.session_state["view"] = "dashboard"
        st.rerun()
        return

    # Access check
    if not is_admin() and not db.is_project_member(project_dir, user["username"]):
        st.error("You are not authorized to access this project.")
        if st.button("← Back to dashboard"):
            st.session_state["view"] = "dashboard"
            st.rerun()
        return

    config = proj.load_config(project_dir)
    reviewer = user["username"]
    can_manage = can_manage_project(project_dir)

    # ── sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.write(f"**{user['username']}**")
        if is_admin():
            st.caption("admin")
        else:
            role = db.get_member_role(project_dir, user["username"]) or ""
            st.caption(role)
        st.divider()

        if st.button("← All projects"):
            st.session_state["view"] = "dashboard"
            st.rerun()

        if st.button("Files"):
            st.session_state["view"] = f"files:{slug}"
            st.rerun()

        st.divider()
        st.subheader("Export")
        if st.button("Prepare Excel export"):
            excel_bytes = _export_excel(project_dir)
            st.download_button(
                "⬇ Download Excel",
                data=excel_bytes,
                file_name=f"{slug}_assessment.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.divider()
        st.subheader("Upload PDFs")
        active_paper = st.session_state.get(f"selected_paper_{slug}")
        if active_paper:
            st.caption(f"Selected: **{active_paper.get('title', '')[:40]}…** — file will be renamed automatically.")
        upload_counter = st.session_state.get(f"upload_count_{slug}", 0)
        pdf_files = st.file_uploader(
            "Select PDF files", type=["pdf"], accept_multiple_files=True,
            key=f"pdf_uploader_{slug}_{upload_counter}",
        )
        if pdf_files:
            pdfs_dir = project_dir / "pdfs"
            pdfs_dir.mkdir(exist_ok=True)
            for f in pdf_files:
                if active_paper and len(pdf_files) == 1:
                    fname = pdf_fetch.pdf_filename(active_paper)
                else:
                    fname = f.name
                (pdfs_dir / fname).write_bytes(f.read())
            st.session_state[f"upload_count_{slug}"] = upload_counter + 1
            st.rerun()

        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # ── header ────────────────────────────────────────────────────────────────
    st.header(config["project_title"])
    if config.get("project_description"):
        st.caption(config["project_description"])

    tabs = ["Assessment", "Analysis"]
    if can_manage:
        tabs.append("Members")
        tabs.append("Settings")

    tab_objects = st.tabs(tabs)
    tab_assess = tab_objects[0]
    tab_analysis = tab_objects[1]
    tab_members = tab_objects[2] if can_manage else None
    tab_settings = tab_objects[3] if can_manage else None

    # ── tab: assessment ───────────────────────────────────────────────────────
    with tab_assess:
        papers = db.get_papers(project_dir)
        if not papers:
            st.warning("No papers loaded for this project.")
            return

        assessments_map = {
            a["key"]: a["include_decision"]
            for a in db.get_all_assessments(project_dir, reviewer=reviewer)
            if a.get("include_decision")
        }
        _status_label = {"Yes": "✅ Include", "No": "❌ Exclude", "Maybe": "🔶 Maybe"}
        _pdf_map_assess, _ = _build_pdf_mapping(project_dir, papers)
        papers_df = pd.DataFrame(papers)[["key", "author", "publication_year", "title", "pdf_url"]]
        papers_df.columns = ["Key", "Author", "Year", "Title", "pdf_url"]

        def _pdf_label(row):
            if _pdf_map_assess.get(row["Key"]):
                return "📄"
            if row["pdf_url"]:
                return "🔗"
            return "—"

        papers_df["PDF"] = papers_df.apply(_pdf_label, axis=1)
        papers_df["Status"] = papers_df["Key"].map(
            lambda k: _status_label.get(assessments_map.get(k, ""), "— pending")
        )

        event = st.dataframe(
            papers_df[["Key", "Author", "Year", "Title", "PDF", "Status"]],
            selection_mode="single-row",
            on_select="rerun",
            use_container_width=True,
            height=300,
            hide_index=True,
            key=f"paper_table_{slug}",
        )

        selected = event.selection.rows
        if not selected:
            st.session_state.pop(f"selected_paper_{slug}", None)
            st.info("Select a paper above to start the assessment.")
        else:
            st.session_state[f"selected_paper_{slug}"] = papers[selected[0]]
            paper = papers[selected[0]]
            paper_key = paper["key"]
            assessment = db.get_assessment(project_dir, paper_key, reviewer)

            st.divider()
            st.subheader(paper["title"])
            st.caption(f"{paper['author']}  ·  {paper.get('publication_year', '')}")

            col_pdf, col_form = st.columns([3, 2])

            with col_pdf:
                if paper.get("abstract"):
                    with st.expander("Abstract"):
                        st.write(paper["abstract"])
                pdf_url_db = paper.get("pdf_url") or ""
                pdf_path = _find_pdf(project_dir, paper.get("author", ""), paper.get("title", ""), paper.get("publication_year"))
                if pdf_path:
                    _show_pdf(pdf_path)
                elif pdf_url_db:
                    st.caption(
                        f"Source: Unpaywall (open access) — "
                        f"[Open in new tab]({pdf_url_db})"
                    )
                    st.markdown(
                        f'<iframe src="{pdf_url_db}" width="100%" height="1200" type="application/pdf"></iframe>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.info("PDF not found. Upload it via the Files panel or use Fetch PDFs.")
                    if paper.get("doi"):
                        st.markdown(f"DOI: [{paper['doi']}](https://doi.org/{paper['doi']})")
                    if paper.get("url"):
                        st.markdown(f"[Open URL]({paper['url']})")

            with col_form:
                st.subheader("Assessment")
                st.caption(f"Reviewer: **{reviewer}**")

                inc = (assessment or {}).get("include_decision", "")
                if inc == "Yes":
                    st.success("Assessed: **Include**")
                elif inc == "No":
                    st.error("Assessed: **Exclude**")
                elif inc == "Maybe":
                    st.info("Assessed: **Maybe**")
                else:
                    st.warning("Not assessed yet.")

                with st.expander("Inclusion criteria"):
                    st.write(config.get("inclusion_criteria") or "—")

                include_opts = get_include_options()
                inc_idx = include_opts.index(inc) if inc in include_opts else 0
                include_w = st.radio(
                    "Include?", include_opts, index=inc_idx, horizontal=True,
                    key=f"include_{paper_key}_{reviewer}",
                )

                c1, c2 = st.columns(2)
                with c1:
                    curr_country = (assessment or {}).get("country") or []
                    country_w = st.multiselect(
                        "Country", get_country_options(), default=curr_country,
                        key=f"country_{paper_key}_{reviewer}",
                    )
                with c2:
                    raw_year = (assessment or {}).get("study_year") or paper.get("publication_year") or 0
                    try:
                        default_year = int(raw_year)
                    except (TypeError, ValueError):
                        default_year = 0
                    year_w = st.number_input(
                        "Study year", value=default_year, step=1, format="%d",
                        key=f"year_{paper_key}_{reviewer}",
                    )

                study_type_opts = get_study_type_options()
                curr_type = (assessment or {}).get("study_type") or (study_type_opts[0] if study_type_opts else "")
                type_idx = study_type_opts.index(curr_type) if curr_type in study_type_opts else 0
                study_type_w = st.radio(
                    "Study type", study_type_opts, index=type_idx,
                    key=f"studytype_{paper_key}_{reviewer}",
                )

                curr_meth = (assessment or {}).get("methodology")
                if study_type_w == "Empirical":
                    opts = get_methodology_empirical()
                    if get_methodology_empirical_explanation():
                        with st.expander("Methodology options — explanation"):
                            st.write(get_methodology_empirical_explanation())
                    default_m = curr_meth if isinstance(curr_meth, list) else []
                    meth_w = st.multiselect(
                        "Methodology", opts, default=[m for m in default_m if m in opts],
                        key=f"meth_{paper_key}_{reviewer}",
                    )
                elif study_type_w == "Literature review":
                    opts = get_methodology_litrev()
                    if get_methodology_litrev_explanation():
                        with st.expander("Methodology options — explanation"):
                            st.write(get_methodology_litrev_explanation())
                    default_m = curr_meth if isinstance(curr_meth, list) else []
                    meth_w = st.multiselect(
                        "Methodology", opts, default=[m for m in default_m if m in opts],
                        key=f"meth_{paper_key}_{reviewer}",
                    )
                else:
                    meth_w = st.text_input(
                        "Methodological notes",
                        value=curr_meth if isinstance(curr_meth, str) else "",
                        key=f"meth_{paper_key}_{reviewer}",
                    )

                criteria_data = (assessment or {}).get("criteria_data") or {}

                extra_fields_data = {}
                for field in config.get("extra_fields", []):
                    extra_fields_data[field] = st.text_input(
                        field,
                        value=criteria_data.get(field, ""),
                        key=f"extra_{paper_key}_{reviewer}_{field}",
                    )

                st.divider()
                criteria_widgets = {}
                for criterion in config.get("assessment_criteria", []):
                    criteria_widgets[criterion] = st.text_area(
                        criterion,
                        value=criteria_data.get(criterion, ""),
                        key=f"crit_{paper_key}_{reviewer}_{criterion}",
                    )

                if st.button("Save", type="primary", use_container_width=True):
                    db.save_assessment(
                        project_dir, paper_key, reviewer,
                        {
                            "include_decision": include_w,
                            "country": country_w,
                            "study_year": int(year_w),
                            "study_type": study_type_w,
                            "methodology": meth_w,
                            "criteria_data": {
                                **extra_fields_data,
                                **{c: criteria_widgets[c] for c in config.get("assessment_criteria", [])},
                            },
                        },
                    )
                    st.success("Saved!")
                    st.rerun()

    # ── tab: analysis ─────────────────────────────────────────────────────────
    with tab_analysis:
        from collections import Counter

        all_papers = db.get_papers(project_dir)
        my_assessments = db.get_all_assessments(project_dir, reviewer=reviewer)
        assessed_rows = [r for r in my_assessments if r.get("include_decision")]

        stats_total = db.get_stats(project_dir)
        my_stats = db.get_stats(project_dir, reviewer=reviewer)
        total = stats_total["total"]

        # ── progress ──────────────────────────────────────────────────────────
        st.subheader("Your progress")
        pct = int(my_stats["assessed"] / total * 100) if total else 0
        st.progress(pct / 100)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total papers", total)
        c2.metric("Your assessed", my_stats["assessed"])
        c3.metric("Include", my_stats["included"])
        c4.metric("Exclude", my_stats["excluded"])
        c5.metric("Maybe", my_stats["maybe"])

        not_assessed = total - my_stats["assessed"]
        if not_assessed > 0:
            with st.expander(f"Not assessed by you yet ({not_assessed})"):
                df_all = pd.DataFrame(my_assessments)
                cols = {"key": "Key", "author": "Author", "publication_year": "Year", "title": "Title"}
                mask = df_all["include_decision"].isna() | (df_all["include_decision"] == "")
                st.dataframe(
                    df_all[mask][list(cols)].rename(columns=cols),
                    use_container_width=True, hide_index=True,
                )

        if can_manage:
            st.divider()
            st.subheader("All reviewers")
            summary = db.get_reviewer_summary(project_dir)
            if summary:
                st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
            else:
                st.info("No assessments recorded yet.")

        if not all_papers:
            st.info("No papers loaded yet.")
        else:
            # ── papers per year ───────────────────────────────────────────────
            st.divider()
            st.subheader("Papers per year")
            years = [p["publication_year"] for p in all_papers if p.get("publication_year")]
            if years:
                year_counts = pd.Series(Counter(years)).sort_index().rename("Papers")
                st.bar_chart(year_counts, sort=False)
            else:
                st.caption("No publication year data.")

            # ── authors ───────────────────────────────────────────────────────
            st.divider()
            st.subheader("Authors")
            author_tokens = []
            for p in all_papers:
                raw = p.get("author") or ""
                for entry in raw.split(";"):
                    surname = entry.strip().split(",")[0].strip()
                    if surname:
                        author_tokens.append(surname)
            if author_tokens:
                top_authors = (pd.Series(Counter(author_tokens))
                               .sort_values(ascending=False).head(20)
                               .rename("Papers"))
                st.bar_chart(top_authors, use_container_width=True, sort=False)
            else:
                st.caption("No author data.")

            # ── keywords ──────────────────────────────────────────────────────
            st.divider()
            st.subheader("Keywords")
            kw_tokens = []
            for p in all_papers:
                raw = p.get("manual_tags") or ""
                for kw in raw.split(";"):
                    kw = kw.strip().lstrip("*").lower()
                    if kw and kw != "article":
                        kw_tokens.append(kw)
            if kw_tokens:
                top_kw = (pd.Series(Counter(kw_tokens))
                          .sort_values(ascending=False).head(30)
                          .rename("Papers"))
                st.bar_chart(top_kw, use_container_width=True, sort=False)
            else:
                st.caption("No keyword data.")

            # ── assessment-based charts (reviewer's own data) ─────────────────
            if assessed_rows:
                st.divider()
                st.subheader("Study year")
                st.caption("Based on your assessments.")
                study_years = [r["study_year_assessed"] for r in assessed_rows if r.get("study_year_assessed")]
                if study_years:
                    sy_counts = pd.Series(Counter(study_years)).sort_index().rename("Papers")
                    st.bar_chart(sy_counts, sort=False)
                else:
                    st.caption("No study year data.")

                st.divider()
                st.subheader("Country")
                st.caption("Based on your assessments. Multi-country papers count once per country.")
                country_tokens = []
                for r in assessed_rows:
                    c = r.get("country") or []
                    if isinstance(c, list):
                        country_tokens.extend(c)
                    elif isinstance(c, str) and c:
                        country_tokens.append(c)
                if country_tokens:
                    top_countries = (pd.Series(Counter(country_tokens))
                                     .sort_values(ascending=False)
                                     .rename("Papers"))
                    st.bar_chart(top_countries, use_container_width=True, sort=False)
                else:
                    st.caption("No country data.")

                st.divider()
                st.subheader("Study type")
                st.caption("Based on your assessments.")
                study_types = [r["study_type"] for r in assessed_rows if r.get("study_type")]
                if study_types:
                    st_df = (pd.Series(Counter(study_types))
                             .sort_values(ascending=False)
                             .rename("Papers"))
                    st.bar_chart(st_df, use_container_width=True, sort=False)
                else:
                    st.caption("No study type data.")

                st.divider()
                st.subheader("Methodology")
                st.caption("Based on your assessments. Each paper may appear in multiple categories.")

                all_meth_values = []
                litrev_values = []
                for r in assessed_rows:
                    m = r.get("methodology")
                    if isinstance(m, list):
                        for v in m:
                            if v in LITREV_TYPES:
                                litrev_values.append(v)
                            else:
                                all_meth_values.append(v)
                    elif isinstance(m, str) and m:
                        all_meth_values.append(m)

                col_meth_l, col_meth_r = st.columns(2)
                col_idx = 0
                for cat_name, cat_options in METH_CATEGORIES.items():
                    counts = {opt: all_meth_values.count(opt) for opt in cat_options if all_meth_values.count(opt) > 0}
                    if counts:
                        target_col = col_meth_l if col_idx % 2 == 0 else col_meth_r
                        with target_col:
                            st.markdown(f"**{cat_name}**")
                            mdf = (pd.Series(counts).sort_values(ascending=False).rename("Papers"))
                            st.bar_chart(mdf, use_container_width=True, sort=False)
                        col_idx += 1

                if litrev_values:
                    st.markdown("**Literature review type**")
                    litrev_counts = {t: litrev_values.count(t) for t in LITREV_TYPES if litrev_values.count(t) > 0}
                    ldf = pd.Series(litrev_counts).sort_values(ascending=False).rename("Papers")
                    st.bar_chart(ldf, use_container_width=True, sort=False)

                if not any([all_meth_values, litrev_values]):
                    st.caption("No methodology data.")
            else:
                st.divider()
                st.info("Assessment charts will appear once you have assessed some papers.")

    # ── tab: members ──────────────────────────────────────────────────────────
    if tab_members is not None:
        with tab_members:
            st.subheader("Project members")
            members = db.get_project_members(project_dir)
            if members:
                df_members = pd.DataFrame(members)
                st.dataframe(df_members, use_container_width=True, hide_index=True)
            else:
                st.info("No members assigned yet.")

            st.divider()
            st.subheader("Add member")
            all_users = db.list_global_users()
            member_usernames = {m["username"] for m in members}
            available = [u["username"] for u in all_users if u["username"] not in member_usernames]

            if available:
                with st.form("add_member_form"):
                    new_member = st.selectbox("User", available)
                    new_role = st.radio("Role", ["reviewer", "owner"], horizontal=True)
                    if st.form_submit_button("Add", type="primary"):
                        db.add_project_member(project_dir, new_member, role=new_role)
                        st.success(f"{new_member} added as {new_role}.")
                        st.rerun()
            else:
                st.info("All users are already members of this project.")

            st.divider()
            st.subheader("Remove member")
            removable = [m["username"] for m in members]
            if removable:
                with st.form("remove_member_form"):
                    to_remove = st.selectbox("User to remove", removable)
                    if st.form_submit_button("Remove", type="secondary"):
                        db.remove_project_member(project_dir, to_remove)
                        st.success(f"{to_remove} removed from project.")
                        st.rerun()

    if tab_settings is not None:
        with tab_settings:
            def _render_field_section(field_type: str, label: str, add_placeholder: str):
                st.subheader(label)
                fields = config.get(field_type, [])
                if fields:
                    for field in fields:
                        c_name, c_btn = st.columns([5, 1])
                        c_name.write(field)
                        if c_btn.button("Rename", key=f"set_ren_{field_type}_{field}"):
                            _dialog_rename_criterion(field_type, field, slug)
                else:
                    st.caption("None defined.")

                st.write("")
                with st.form(f"add_{field_type}_form"):
                    new_field = st.text_input(
                        "New field name",
                        placeholder=add_placeholder,
                        label_visibility="collapsed",
                    )
                    if st.form_submit_button("+ Add", type="primary"):
                        new_field = new_field.strip()
                        if new_field and new_field not in config.get(field_type, []):
                            config.setdefault(field_type, []).append(new_field)
                            proj.save_config(project_dir, config)
                            st.success(f"Added: {new_field}")
                            st.rerun()
                        elif new_field in config.get(field_type, []):
                            st.error("A field with this name already exists.")

            _render_field_section(
                "assessment_criteria",
                "Assessment criteria",
                "e.g. Main ethical issues identified",
            )
            st.divider()
            _render_field_section(
                "extra_fields",
                "Extra fields",
                "e.g. Health emergency / issue",
            )


# ──────────────────────────────────────────────────────────────────────────────
# View: admin panel
# ──────────────────────────────────────────────────────────────────────────────

def view_admin():
    with st.sidebar:
        if st.button("← Dashboard"):
            st.session_state["view"] = "dashboard"
            st.rerun()
        st.divider()
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

    st.title("Admin panel")
    tab_users, tab_projects = st.tabs(["Users", "Projects"])

    with tab_users:
        st.subheader("All users")
        users = db.list_global_users()
        if users:
            st.dataframe(pd.DataFrame(users), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Create user")
        with st.form("create_user_form"):
            new_username = st.text_input("Username *")
            new_email = st.text_input("Email", placeholder="used for PDF retrieval via Unpaywall")
            new_pw = st.text_input("Password *", type="password")
            new_pw2 = st.text_input("Confirm password *", type="password")
            new_role = st.radio("Role", ["user", "admin"], horizontal=True)
            if st.form_submit_button("Create", type="primary"):
                errors = []
                if not new_username.strip():
                    errors.append("Username is required.")
                if not new_pw:
                    errors.append("Password is required.")
                if new_pw != new_pw2:
                    errors.append("Passwords do not match.")
                if db.get_global_user(new_username.strip()):
                    errors.append("Username already exists.")
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    db.create_global_user(new_username.strip(), auth.hash_password(new_pw),
                                          role=new_role, email=new_email.strip())
                    st.success(f"User '{new_username.strip()}' created.")
                    st.rerun()

        st.divider()
        st.subheader("Delete user")
        current_username = current_user()["username"]
        deletable = [u["username"] for u in users if u["username"] != current_username]
        if deletable:
            with st.form("delete_user_form"):
                to_delete = st.selectbox("User to delete", deletable)
                if st.form_submit_button("Delete", type="secondary"):
                    db.delete_global_user(to_delete)
                    st.success(f"User '{to_delete}' deleted.")
                    st.rerun()
        else:
            st.info("No other users to delete.")

    with tab_projects:
        st.subheader("All projects")
        projects = proj.list_projects()
        if not projects:
            st.info("No projects yet.")
        else:
            for p_dir in projects:
                config = proj.load_config(p_dir)
                stats = db.get_stats(p_dir)
                members = db.get_project_members(p_dir)
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.write(f"**{config['project_title']}**  ·  `{p_dir.name}`")
                        st.caption(
                            f"{stats['total']} papers  ·  {len(members)} members: "
                            + ", ".join(m["username"] for m in members)
                        )
                    with c2:
                        if st.button("Open", key=f"admin_open_{p_dir.name}", use_container_width=True):
                            st.session_state["view"] = f"project:{p_dir.name}"
                            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# View: file manager
# ──────────────────────────────────────────────────────────────────────────────

@st.dialog("Delete project")
def _dialog_delete_project(slug: str, title: str):
    st.warning(
        f"This will permanently delete **{title}** including all papers, "
        f"assessments and PDF files. This cannot be undone."
    )
    st.write("Type the project title to confirm:")
    confirm = st.text_input("Project title", label_visibility="collapsed")
    c1, c2 = st.columns(2)
    if c1.button(
        "Delete", type="primary", use_container_width=True,
        disabled=(confirm.strip() != title),
    ):
        proj.delete_project(proj.get_project_dir(slug))
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


@st.dialog("Rename field")
def _dialog_rename_criterion(field_type: str, old_name: str, slug: str):
    project_dir = proj.get_project_dir(slug)
    config = proj.load_config(project_dir)
    st.caption(f"Type: **{'Assessment criterion' if field_type == 'assessment_criteria' else 'Extra field'}**")
    new_name = st.text_input("New name", value=old_name)
    c1, c2 = st.columns(2)
    if c1.button("Rename", type="primary", use_container_width=True):
        new_name = new_name.strip()
        if new_name and new_name != old_name:
            lst = config[field_type]
            lst[lst.index(old_name)] = new_name
            proj.save_config(project_dir, config)
            db.rename_criterion(project_dir, old_name, new_name)
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


@st.dialog("Rename file")
def _dialog_rename(filename: str, pdfs_dir: Path):
    new_name = st.text_input("New filename", value=filename)
    if not new_name.lower().endswith(".pdf"):
        new_name += ".pdf"
    c1, c2 = st.columns(2)
    if c1.button("Rename", type="primary", use_container_width=True):
        if new_name.strip() and new_name != filename:
            (pdfs_dir / filename).rename(pdfs_dir / new_name.strip())
        st.session_state.pop("rename_file", None)
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.session_state.pop("rename_file", None)
        st.rerun()


def view_files(slug: str):
    user = current_user()
    project_dir = proj.get_project_dir(slug)

    if not project_dir.exists():
        st.error("Project not found.")
        st.session_state["view"] = "dashboard"
        st.rerun()
        return

    if not is_admin() and not db.is_project_member(project_dir, user["username"]):
        st.error("Not authorized.")
        st.session_state["view"] = "dashboard"
        st.rerun()
        return

    config = proj.load_config(project_dir)
    pdfs_dir = project_dir / "pdfs"
    pdfs_dir.mkdir(exist_ok=True)
    papers = db.get_papers(project_dir)

    with st.sidebar:
        if st.button("← All projects"):
            st.session_state["view"] = "dashboard"
            st.rerun()
        if st.button("Open assessment", use_container_width=True):
            st.session_state["view"] = f"project:{slug}"
            st.rerun()
        st.divider()
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    st.header(f"Files — {config['project_title']}")

    # Upload
    uploaded = st.file_uploader(
        "Upload PDF files", type=["pdf"], accept_multiple_files=True
    )
    if uploaded:
        for f in uploaded:
            (pdfs_dir / f.name).write_bytes(f.read())
        st.success(f"{len(uploaded)} file(s) uploaded.")
        st.rerun()

    st.divider()

    paper_to_pdf, pdf_to_paper = _build_pdf_mapping(project_dir, papers)

    total_pdfs = len(pdf_to_paper)
    matched = sum(1 for v in pdf_to_paper.values() if v is not None)
    unmatched = total_pdfs - matched
    via_unpaywall = sum(1 for p in papers if p.get("pdf_url"))
    no_pdf = sum(1 for p in papers if paper_to_pdf.get(p["key"]) is None and not p.get("pdf_url"))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("PDF files", total_pdfs)
    c2.metric("Matched", matched)
    c3.metric("Unmatched files", unmatched, delta=f"-{unmatched}" if unmatched else None, delta_color="inverse")
    c4.metric("Via Unpaywall", via_unpaywall)
    c5.metric("No PDF", no_pdf, delta=f"-{no_pdf}" if no_pdf else None, delta_color="inverse")

    st.divider()

    # ── file table ────────────────────────────────────────────────────────────
    if not pdf_to_paper:
        st.info("No PDF files yet.")
    else:
        # header row
        h1, h2, h3 = st.columns([3, 4, 1])
        h1.caption("**Filename**")
        h2.caption("**Matched paper**")
        h3.caption("**Actions**")

        for filename, matched_paper in pdf_to_paper.items():
            c_name, c_match, c_act = st.columns([3, 4, 1])

            with c_name:
                st.write(filename)

            with c_match:
                if matched_paper:
                    surnames = [
                        b.split(",")[0].strip()
                        for b in matched_paper.get("author", "").split(";")
                        if b.strip()
                    ]
                    display = surnames[0] if surnames else "?"
                    if len(surnames) > 1:
                        display += " et al."
                    st.success(
                        f"{display} ({matched_paper.get('publication_year', '?')})  "
                        f"— {matched_paper['title'][:60]}{'…' if len(matched_paper['title']) > 60 else ''}"
                    )
                else:
                    st.error("No match found")

            with c_act:
                col_r, col_d = st.columns(2)
                if col_r.button("✏", key=f"ren_{filename}", help="Rename"):
                    st.session_state["rename_file"] = filename
                if col_d.button("✕", key=f"del_{filename}", help="Delete"):
                    st.session_state["confirm_delete"] = filename

            # rename dialog
            if st.session_state.get("rename_file") == filename:
                _dialog_rename(filename, pdfs_dir)

            # delete confirmation inline
            if st.session_state.get("confirm_delete") == filename:
                with st.container(border=True):
                    st.warning(f"Delete **{filename}**? This cannot be undone.")
                    cy, cn = st.columns(2)
                    if cy.button("Delete", key=f"yes_del_{filename}", type="primary", use_container_width=True):
                        (pdfs_dir / filename).unlink(missing_ok=True)
                        st.session_state.pop("confirm_delete", None)
                        st.rerun()
                    if cn.button("Cancel", key=f"no_del_{filename}", use_container_width=True):
                        st.session_state.pop("confirm_delete", None)
                        st.rerun()

    # ── papers without PDF ────────────────────────────────────────────────────
    unpaywall_papers = [p for p in papers if p.get("pdf_url")]
    missing_papers = [p for p in papers if paper_to_pdf.get(p["key"]) is None and not p.get("pdf_url")]

    if unpaywall_papers:
        user_data_up = db.get_global_user(current_user()["username"]) or {}
        user_email_up = user_data_up.get("email") or ""
        refetch_key = f"refetch_results_{slug}"

        col_up_exp, col_up_btn = st.columns([3, 1])
        with col_up_exp:
            with st.expander(f"Papers with Unpaywall URL — embed may be blocked ({len(unpaywall_papers)})"):
                for paper in unpaywall_papers:
                    surnames = [b.split(",")[0].strip() for b in paper.get("author", "").split(";") if b.strip()]
                    a = surnames[0] if surnames else "Unknown"
                    if len(surnames) > 1:
                        a += " et al."
                    st.write(f"- **{a}** ({paper.get('publication_year', '?')}) — {paper['title']}")

        with col_up_btn:
            st.subheader("Force re-fetch")
            if st.session_state.get(refetch_key):
                r = st.session_state[refetch_key]
                st.success(
                    f"Re-fetch — {r['downloaded']} downloaded, "
                    f"{r['still_url']} still URL only, "
                    f"{r['errors']} errors."
                )
            if not user_email_up:
                st.warning("Set your email in the sidebar to enable re-fetch.")
            else:
                st.caption(f"Attempt to download {len(unpaywall_papers)} papers currently stored as URL only.")
                if st.button("Re-fetch URL-only PDFs", use_container_width=True):
                    rr = {"downloaded": 0, "still_url": 0, "errors": 0}
                    progress = st.progress(0.0, text="Re-fetching...")
                    for i, paper in enumerate(unpaywall_papers):
                        progress.progress(
                            (i + 1) / len(unpaywall_papers),
                            text=f"{i+1}/{len(unpaywall_papers)} — {paper.get('title', '')[:50]}",
                        )
                        try:
                            pdf_bytes = pdf_fetch._try_download(paper["pdf_url"])
                            if pdf_bytes:
                                fname = pdf_fetch.pdf_filename(paper)
                                (pdfs_dir / fname).write_bytes(pdf_bytes)
                                db.clear_paper_pdf_url(project_dir, paper["key"])
                                rr["downloaded"] += 1
                            else:
                                rr["still_url"] += 1
                        except Exception:
                            rr["errors"] += 1
                    progress.empty()
                    st.session_state[refetch_key] = rr
                    st.rerun()

    if missing_papers:
        st.divider()
        user_data = db.get_global_user(current_user()["username"]) or {}
        user_email = user_data.get("email") or ""

        col_exp, col_fetch = st.columns([3, 1])
        with col_exp:
            with st.expander(f"Papers without a matching PDF ({no_pdf})"):
                for paper in missing_papers:
                    surnames = [
                        b.split(",")[0].strip()
                        for b in paper.get("author", "").split(";")
                        if b.strip()
                    ]
                    if not surnames:
                        a = "Unknown"
                    elif len(surnames) == 1:
                        a = surnames[0]
                    elif len(surnames) == 2:
                        a = f"{surnames[0]}, {surnames[1]}"
                    else:
                        a = f"{surnames[0]} et al."
                    st.write(f"- **{a}** ({paper.get('publication_year', '?')}) — {paper['title']}")

        with col_fetch:
            st.subheader("Fetch PDFs")
            fetch_key = f"fetch_results_{slug}"
            if st.session_state.get(fetch_key):
                r = st.session_state[fetch_key]
                st.success(
                    f"Last fetch — {r['unpaywall']} downloaded, "
                    f"{r.get('unpaywall_url', 0)} URL only (embed may be blocked), "
                    f"{r['not_found']} not found, "
                    f"{r['errors']} errors."
                )
            if not user_email:
                st.warning("Set your email in the sidebar profile to enable PDF retrieval.")
            else:
                with_doi = [p for p in missing_papers if p.get("doi")]
                st.caption(f"{len(with_doi)} of {len(missing_papers)} missing papers have a DOI.")
                if with_doi:
                    if st.button("Fetch all missing PDFs", type="primary", use_container_width=True):
                        results = {"unpaywall": 0, "unpaywall_url": 0, "not_found": 0, "errors": 0}
                        progress = st.progress(0.0, text="Fetching...")
                        for i, paper in enumerate(with_doi):
                            progress.progress(
                                (i + 1) / len(with_doi),
                                text=f"{i+1}/{len(with_doi)} — {paper.get('title', '')[:50]}",
                            )
                            try:
                                pdf_url, pdf_bytes, source = pdf_fetch.fetch_pdf(paper["doi"], user_email)
                                if source == "unpaywall" and pdf_bytes:
                                    fname = pdf_fetch.pdf_filename(paper)
                                    (pdfs_dir / fname).write_bytes(pdf_bytes)
                                    results["unpaywall"] += 1
                                elif source == "unpaywall_url" and pdf_url:
                                    db.save_paper_pdf_url(project_dir, paper["key"], pdf_url)
                                    results["unpaywall_url"] += 1
                                else:
                                    results["not_found"] += 1
                            except Exception:
                                results["errors"] += 1
                        progress.empty()
                        st.session_state[fetch_key] = results
                        st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# View: documentation
# ──────────────────────────────────────────────────────────────────────────────

def view_docs():
    if st.button("← Back"):
        st.session_state["view"] = "dashboard"
        st.rerun()
    docs_path = Path(__file__).parent / "docs.md"
    if docs_path.exists():
        st.markdown(docs_path.read_text(encoding="utf-8"), unsafe_allow_html=False)
    else:
        st.error("Documentation file not found.")


# ──────────────────────────────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────────────────────────────

if not db.global_has_users():
    view_setup()
elif not current_user():
    view_login()
else:
    _view = st.session_state.get("view", "dashboard")
    if _view == "dashboard":
        view_dashboard()
    elif _view == "new_project":
        if is_admin():
            view_new_project()
        else:
            st.error("Only admins can create projects.")
    elif _view == "admin":
        if is_admin():
            view_admin()
        else:
            st.error("Not authorized.")
    elif _view.startswith("project:"):
        view_project(_view.split(":", 1)[1])
    elif _view.startswith("files:"):
        view_files(_view.split(":", 1)[1])
    elif _view == "docs":
        view_docs()
    else:
        st.session_state["view"] = "dashboard"
        st.rerun()
