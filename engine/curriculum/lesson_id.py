from __future__ import annotations
import hashlib
from urllib.parse import quote, unquote


def make_lesson_id(book_title: str, chapter: str, opinion: str) -> str:
    h = hashlib.sha256(opinion.encode("utf-8")).hexdigest()[:12]
    return f"{book_title}::{chapter}::{h}"


def encode_lesson_id(lesson_id: str) -> str:
    return quote(lesson_id, safe="")


def decode_lesson_id(encoded: str) -> str:
    return unquote(encoded)


def encode_tag(tag: str) -> str:
    """URL path segment for tags that may contain '/' (e.g. 护城河/竞争优势)."""
    return quote(tag, safe="")


def decode_tag(encoded: str) -> str:
    return unquote(encoded)
