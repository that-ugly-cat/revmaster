import re
import requests

TIMEOUT_META = 10
TIMEOUT_PDF  = 30

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RevMaster/2.0)"}


def get_unpaywall_pdf_url(doi: str, email: str) -> str | None:
    """Return the best OA PDF URL from Unpaywall, or None if not available."""
    try:
        meta = requests.get(
            f"https://api.unpaywall.org/v2/{doi}?email={email}",
            timeout=TIMEOUT_META,
            headers=_HEADERS,
        )
        if meta.status_code != 200:
            return None
        data = meta.json()
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf")
        if not pdf_url:
            for loc in data.get("oa_locations", []):
                if loc.get("url_for_pdf"):
                    pdf_url = loc["url_for_pdf"]
                    break
        return pdf_url or None
    except Exception:
        return None



def _normalize_doi(doi: str) -> str:
    """Strip URL prefix — Unpaywall and Sci-Hub expect bare DOIs like 10.xxxx/yyyy."""
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/"):
        if doi.lower().startswith(prefix):
            return doi[len(prefix):]
    return doi


def _try_download(url: str) -> bytes | None:
    """Attempt to download a PDF from a direct URL. Returns bytes or None."""
    try:
        r = requests.get(url, timeout=TIMEOUT_PDF, allow_redirects=True, headers=_HEADERS)
        if r.status_code == 200 and len(r.content) > 10_000:
            ct = r.headers.get("Content-Type", "")
            if "pdf" in ct or r.content[:4] == b"%PDF":
                return r.content
    except Exception:
        pass
    return None


def fetch_pdf(doi: str, email: str) -> tuple[str | None, bytes | None, str]:
    """
    Try Unpaywall: attempt to download the PDF directly. If the download
    succeeds, return bytes (source='unpaywall'). If blocked/unavailable, keep
    the URL as fallback (source='unpaywall_url').
    Returns (pdf_url, pdf_bytes, source):
      - Unpaywall downloaded: (None, bytes, 'unpaywall')
      - Unpaywall URL only:   (url, None, 'unpaywall_url')
      - Not found:            (None, None, '')
    """
    if not doi:
        return None, None, ""
    doi = _normalize_doi(doi)
    pdf_url = get_unpaywall_pdf_url(doi, email)
    if pdf_url:
        pdf_bytes = _try_download(pdf_url)
        if pdf_bytes:
            return None, pdf_bytes, "unpaywall"
        return pdf_url, None, "unpaywall_url"
    return None, None, ""


def pdf_filename(paper: dict) -> str:
    author = paper.get("author") or ""
    surname = author.split(";")[0].split(",")[0].strip()
    surname_clean = re.sub(r"[^a-zA-Z]", "", surname) or "Unknown"
    year = paper.get("publication_year") or ""
    key = (paper.get("key") or "")[:6]
    return f"{surname_clean}{year}_{key}.pdf"
