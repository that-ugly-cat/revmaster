# RevMaster — Documentation

**RevMaster** is a self-hosted literature review assessment tool. It supports multi-project workflows, per-reviewer independent assessments, PDF management, and configurable criteria.

---

## Contents

1. [First run & setup](#1-first-run--setup)
2. [Login and access](#2-login-and-access)
3. [Creating a project](#3-creating-a-project)
4. [Importing from Zotero](#4-importing-from-zotero)
5. [Managing PDF files](#5-managing-pdf-files)
6. [Assessment](#6-assessment)
7. [Multi-reviewer and IRR](#7-multi-reviewer-and-irr)
8. [User management](#8-user-management)
9. [Project settings](#9-project-settings)
10. [Analysis](#10-analysis)

---

## 1. First run & setup

On the very first visit, RevMaster shows a **setup screen** instead of the login page. This happens automatically when no users exist in the system.

Fill in a username, email, and password to create the **admin account**. The email is used for PDF retrieval via Unpaywall (see [Managing PDF files](#5-managing-pdf-files)) and can be updated later from the sidebar.

> The setup screen disappears permanently once the first user is created. To reset, an administrator must delete or recreate users from the Admin panel.

---

## 2. Login and access

All pages require authentication. Unauthenticated visitors see only the login screen.

**Roles:**

| Role | Can do |
|------|--------|
| `admin` | All projects, user management, project settings, delete projects |
| `reviewer` | Only projects they have been assigned to; assessment only |

Admins can create additional admin accounts from the Admin panel.

**Profile:** once logged in, use the **My profile** expander in the sidebar to update your email address.

---

## 3. Creating a project

From the dashboard, click **New project**.

**Fields:**

- **Title** — used as display name and to generate the project slug (internal identifier).
- **Description** — free text, shown on the project page.
- **Inclusion criteria** — narrative description of what makes a paper eligible. Shown to reviewers during assessment as a reference.
- **Assessment criteria** — one criterion per line. Each becomes a free-text area in the assessment form. These can be added or renamed later (see [Project settings](#9-project-settings)).
- **Extra fields** — one field per line. Each becomes a short text input in the assessment form (for structured metadata like country, funding source, target population). These can also be modified later.

Example extra fields:
```
Context
Domain
Funding source
Target population
Jurisdiction
```

After creation, the project appears on the dashboard. Papers must be imported before assessment can begin.

---

## 4. Importing from Zotero

RevMaster imports papers from a **Zotero CSV export**.

### Export from Zotero

1. In Zotero, select the collection or items to export.
2. Go to **File → Export Library** (or right-click the collection → Export Collection).
3. Choose format: **CSV**.
4. Save the file.

### Expected columns

RevMaster reads the following columns (case-insensitive):

| Column | Used for |
|--------|----------|
| `Key` | Unique paper identifier — **required** |
| `Title` | Paper title |
| `Author` | Author list |
| `Publication Year` | Year |
| `Abstract Note` or `Abstract` | Abstract text |
| `Item Type` | Document type (journal article, book, etc.) |
| `DOI` | DOI link — also used for automatic PDF retrieval |
| `URL` | URL link |
| `Manual Tags` | Zotero tags |

Papers without a `Key` value are silently skipped.

### Import

1. Open the project.
2. Go to **Settings** → upload section, or use the import button on the project page.
3. Upload the `.csv` file.
4. Papers already in the database (same `Key`) are not duplicated — re-importing is safe.

### Exporting PDFs from Zotero

If your Zotero library has attached PDFs, you can export them in bulk to upload to RevMaster.

1. In Zotero, right-click the collection → **Export Collection**.
2. Choose format: **Zotero RDF** (or any format) — but check **"Export Files"** in the options.
3. Zotero will create a folder containing all attached PDFs alongside the metadata file.
4. Alternatively: in Zotero, select all items (Ctrl+A), then go to **File → Export Items**, check **"Export Files"**.

The exported PDFs are typically named after the paper title or a Zotero-generated filename. Before uploading to RevMaster, consider **renaming them to include the first author's surname** — this improves automatic matching (see [Managing PDF files](#5-managing-pdf-files)).

### Notes

- Zotero keys are short alphanumeric strings (e.g. `AB3X9K2P`). They are stable across exports.
- If a paper appears in Zotero under multiple collections, it will have the same key and will not be duplicated on re-import.
- Column headers must match Zotero's default CSV export format. Do not rename columns before importing.

---

## 5. Managing PDF files

Open a project from the dashboard and click **Files** to access the file manager.

### Upload

Drag and drop or select one or more PDF files. Files are saved to the project's storage and are immediately available in the assessment view.

### Automatic PDF retrieval (Fetch)

RevMaster can attempt to retrieve PDFs automatically for papers that have a DOI. Click **Fetch all missing PDFs** in the Files panel.

The retrieval tries open-access sources in two steps:

1. **Direct download** — RevMaster attempts to download the PDF file from the open-access URL. If successful, the file is stored on the server and served like any locally uploaded PDF.
2. **URL fallback** — If the server blocks the download (e.g. publisher restrictions), the open-access URL is stored instead. The assessment view attempts to display it inline; if the publisher blocks embedding, an **Open in new tab** link is shown above the viewer.

The Files panel shows:
- **Via Unpaywall** — papers covered by an open-access URL (not yet downloaded as a local file).
- **Papers with Unpaywall URL** expander — lists those papers, with a **Re-fetch URL-only PDFs** button to retry the download at any time.

To enable this feature, **set your email in the sidebar profile** (My profile → Email). The email is sent to the open-access lookup service as required by their terms of use.

### Automatic matching

When a PDF is uploaded manually, RevMaster attempts to match it to a paper in the database using the **first author's surname** extracted from the filename.

Matching logic:
1. Extracts the first author's surname from the paper record.
2. Searches for PDF files whose filename contains that surname (case-insensitive, ignoring hyphens and special characters — e.g. `Abboah-Offei` matches `AbboahOffei`).
3. If multiple candidates are found, uses the first two words of the title as a tiebreak, then the publication year.

**Priority in the assessment view:**
1. Locally uploaded or downloaded file matching the paper → served from server storage.
2. Open-access URL (embed fallback) → displayed inline; **Open in new tab** link always shown.
3. Neither → shows DOI link and URL link.

### Rename

Click **Rename** next to a file to give it a new name. The `.pdf` extension is preserved automatically if omitted. Renaming is useful to improve matching for manually uploaded files.

### Delete

Click **Delete** next to a file to remove it permanently. This does not affect the paper record in the database.

### Tips

- Naming PDFs with the first author's surname increases matching accuracy (e.g. `Smith2021_ethics.pdf`).
- Unmatched PDFs are listed at the bottom of the Files panel.
- Papers without any PDF source are listed in the "Papers without a matching PDF" expander.
- Papers covered only by an open-access URL (not downloaded) are listed in the "Papers with Unpaywall URL" expander. Use **Re-fetch URL-only PDFs** to retry downloading them.

---

## 6. Assessment

Open a project, then click **Open** to go to the project view. The **Assessment** tab is the main workspace.

### Workflow

1. The table at the top lists all papers with their current assessment status and PDF availability for your account.
2. Click a row to select a paper.
3. The abstract (if available) and the PDF appear on the left; the assessment form on the right.
4. Fill in the fields and click **Save**.

### Table columns

**PDF column:**

| Icon | Meaning |
|------|---------|
| `📄` | Local PDF file available |
| `🔗` | Open-access URL available (embed may be blocked) |
| `—` | No PDF source |

**Status column:**

| Status | Meaning |
|--------|---------|
| `— pending` | Not yet assessed by you |
| `✅ Include` | You marked this paper for inclusion |
| `🔶 Maybe` | You marked this as uncertain |
| `❌ Exclude` | You marked this paper for exclusion |

Status is **per-reviewer**: your status does not affect or reveal another reviewer's status.

### Fixed fields

These fields are present in every project:

- **Include?** — radio button: Yes / Maybe / No.
- **Country** — multi-select from a predefined list.
- **Study year** — numeric, defaults to publication year.
- **Study type** — radio button: Empirical / Literature review / Other.
- **Methodology** — depends on study type; multi-select for Empirical and Literature review, free text otherwise.

### Configurable fields

- **Extra fields** — short text inputs defined at project creation (e.g. Context, Funding source). Shown above the assessment criteria.
- **Assessment criteria** — free-text areas for structured qualitative notes. One per criterion defined in the project.

Both can be added or renamed after project creation from the Settings tab.

---

## 7. Multi-reviewer and IRR

RevMaster supports **independent per-reviewer assessments** on the same set of papers. This is designed for double-blind title/abstract screening and inter-rater reliability (IRR) workflows.

### How it works

- Each reviewer has a completely separate assessment record for every paper.
- Reviewers cannot see each other's decisions or notes.
- An admin or project owner can see aggregate statistics across all reviewers in the Analysis tab.

### Setting up a multi-reviewer project

1. Create the project (admin).
2. Go to the project's **Members** tab.
3. Add the reviewers by username. They must already have a global account (see [User management](#8-user-management)).
4. Each reviewer logs in and sees the project on their dashboard.
5. Reviewers work independently on the same paper list.

### IRR analysis

The Analysis tab shows per-reviewer breakdowns alongside aggregate totals. Full IRR metrics (Cohen's kappa, etc.) are not computed inside RevMaster — export the data for analysis in R or Python.

> **Blind screening note:** reviewers see their own status only. There is no mechanism inside RevMaster to reveal another reviewer's decisions before a reconciliation phase — this must be managed externally (e.g. by the admin exporting data after both reviewers complete screening).

---

## 8. User management

Access the Admin panel via the top navigation (admin accounts only).

### Creating a user

1. Go to **Admin → Users**.
2. Enter username, email (optional), and password.
3. Choose role: `reviewer` (default) or `admin`.
4. Click **Create**.

Usernames must be unique across the installation. The email is used for PDF retrieval and can be updated by the user from their sidebar profile at any time.

### Changing a password

Select the user and use the **Change password** action.

### Deleting a user

Select the user and click **Delete**. This removes the global account but does **not** delete their assessment data in existing projects — their records remain in the database under their username.

### Assigning users to projects

From the project's **Members** tab (visible to admin and project owner):

1. Type the username of an existing global user.
2. Click **Add member**.
3. The user will see the project on their dashboard at next login.

To remove a member, click **Remove** next to their name. This does not delete their assessment data.

---

## 9. Project settings

Open a project and go to the **Settings** tab (visible to admin and project owner).

### Adding a criterion or extra field

Click **Add** under the relevant section, type the new name, and confirm. The field immediately appears in the assessment form for all reviewers.

Existing assessment records are not affected — the new field will be empty for papers already assessed.

### Renaming a criterion or extra field

Click **Rename** next to the field name. Enter the new name and confirm.

RevMaster automatically **migrates all existing assessment data**: every saved record that contains the old field name is updated to use the new name. No data is lost.

### Editing project metadata

Title, description, and inclusion criteria can be edited directly in the Settings tab.

### Deleting a project

From the **dashboard**, click **Delete** on the project card. A confirmation dialog requires you to type the exact project title before deletion proceeds.

> **Warning:** deletion is permanent and irreversible. All papers, assessments, uploaded PDFs, and retrieved PDF links for that project are deleted.

---

## 10. Analysis

Open a project and go to the **Analysis** tab.

### Your progress

Shows metrics filtered to your own assessments: total papers, how many you have assessed, and your Include / Exclude / Maybe counts, with a progress bar.

Papers you have not yet assessed are listed in a collapsible expander.

### All reviewers

A table showing assessment counts per reviewer. Visible to admins and project owners only.

### Bibliometric charts

Based on all papers in the project database (regardless of assessment status):

- **Papers per year** — publication year distribution.
- **Authors** — top 20 first authors by frequency.
- **Keywords** — top 30 keywords from Zotero manual tags.

### Assessment charts

Based on your own assessed papers:

- **Study year** — distribution of assessed study years.
- **Country** — country distribution (multi-country papers count once per country).
- **Study type** — Empirical / Literature review / Theoretical / etc.
- **Methodology** — broken down by category (Observational vs Experimental, Descriptive vs Analytical, Qualitative vs Quantitative, Longitudinal vs Cross-sectional) and literature review type.

---

*RevMaster v2 — self-hosted, no cloud dependencies.*
