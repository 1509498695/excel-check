"""Compatibility adapter for legacy smart-rule prompt templates."""

from __future__ import annotations


def normalize_legacy_template_text(text: str) -> str:
    """Return text in the current short-DSL-compatible shape.

    The third-round refactor only centralizes the compatibility boundary. It
    intentionally keeps the accepted grammar unchanged so existing snapshots
    continue to be the source of truth.
    """
    return text or ""
