"""Source-related text extraction helpers."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def extract_source_url(text: str) -> str | None:
    """Extract an Excel-looking URL from free text."""
    match = re.search(r"https?://[A-Za-z0-9_./:%?=&~#+-]+\.xls[xm]?", text, re.IGNORECASE)
    return match.group(0) if match else None


def derive_source_id(source_url: str | None) -> str | None:
    """Derive a stable source id from a path or URL."""
    if not source_url:
        return None
    raw_name = urlparse(source_url).path.rstrip("/").split("/")[-1]
    stem = raw_name.rsplit(".", 1)[0] if "." in raw_name else raw_name
    source_id = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_")
    return source_id or None


def guess_source_type(source_url: str | None) -> str | None:
    """Infer source type from a path or URL."""
    if not source_url:
        return None
    if source_url.lower().startswith(("http://", "https://", "svn://")):
        return "svn"
    return "local_excel"
