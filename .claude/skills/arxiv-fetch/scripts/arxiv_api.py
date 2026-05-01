"""Talk to arxiv.org: parse IDs, fetch metadata, download e-print, unpack archive.

Everything in this module is about the *external* arXiv interface; nothing
here knows about LaTeX structure beyond "the e-print blob may be a tarball,
a single gzipped .tex, or a PDF".
"""

from __future__ import annotations

import gzip
import io
import re
import sys
import tarfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ARXIV_ID_RE = re.compile(
    r"""
    (?:arXiv:)?
    (?:https?://arxiv\.org/(?:abs|pdf|e-print)/)?
    (?P<id>\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})
    (?:v(?P<version>\d+))?
    (?:\.pdf)?
    """,
    re.VERBOSE,
)
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
USER_AGENT = "wikip-arxiv-fetch/0.1 (https://github.com; mailto:noreply@example.com)"


def parse_arxiv_id(raw: str) -> tuple[str, str | None]:
    """Return (id, version) from any accepted input form."""
    m = ARXIV_ID_RE.search(raw.strip())
    if not m:
        sys.exit(f"could not parse arxiv id from: {raw!r}")
    return m.group("id"), m.group("version")


def http_get(url: str, *, accept: str = "*/*", retries: int = 3) -> bytes:
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            last_err = e
        except urllib.error.URLError as e:
            last_err = e
        time.sleep(2 ** attempt)
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_err}")


def fetch_metadata(arxiv_id: str) -> dict:
    """Pull title, authors, abstract, etc. from the arXiv API."""
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    body = http_get(url, accept="application/atom+xml")
    root = ET.fromstring(body)
    entry = root.find(f"{ATOM_NS}entry")
    if entry is None:
        return {"arxiv_id": arxiv_id, "title": None, "authors": [], "abstract": None}
    title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
    summary = (entry.findtext(f"{ATOM_NS}summary") or "").strip()
    authors = [
        (a.findtext(f"{ATOM_NS}name") or "").strip()
        for a in entry.findall(f"{ATOM_NS}author")
    ]
    primary = entry.find(f"{ARXIV_NS}primary_category")
    primary_class = primary.get("term") if primary is not None else None
    categories = [c.get("term") for c in entry.findall(f"{ATOM_NS}category") if c.get("term")]
    id_url = (entry.findtext(f"{ATOM_NS}id") or "").strip()
    version = id_url.rsplit("v", 1)[-1] if "v" in id_url.rsplit("/", 1)[-1] else None
    return {
        "arxiv_id": arxiv_id,
        "title": " ".join(title.split()),
        "authors": authors,
        "abstract": " ".join(summary.split()),
        "primary_class": primary_class,
        "categories": categories,
        "version": version,
        "abs_url": id_url,
    }


def download_eprint(arxiv_id: str, version: str | None) -> bytes:
    suffix = f"v{version}" if version else ""
    url = f"https://arxiv.org/e-print/{arxiv_id}{suffix}"
    return http_get(url)


def looks_like_pdf(blob: bytes) -> bool:
    return blob[:5] == b"%PDF-"


def looks_like_gzip(blob: bytes) -> bool:
    return blob[:2] == b"\x1f\x8b"


def extract_source(blob: bytes, dest: Path) -> Path:
    """Unpack the e-print blob into dest/. Returns dest.

    Handles: tar.gz archives (most papers), bare gzipped .tex (single-file papers),
    bare .tex (rare; arxiv occasionally returns uncompressed source).
    """
    dest.mkdir(parents=True, exist_ok=True)
    if not looks_like_gzip(blob):
        # arxiv occasionally returns a bare .tex
        (dest / "main.tex").write_bytes(blob)
        return dest
    decompressed = gzip.decompress(blob)
    # Could be a tar archive or a single .tex file
    try:
        with tarfile.open(fileobj=io.BytesIO(decompressed)) as tf:
            kwargs = {"filter": "data"} if sys.version_info >= (3, 12) else {}
            tf.extractall(dest, **kwargs)
        return dest
    except tarfile.TarError:
        (dest / "main.tex").write_bytes(decompressed)
        return dest
