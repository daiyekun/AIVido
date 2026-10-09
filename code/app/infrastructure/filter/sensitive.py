from __future__ import annotations

import logging
import os

from app.core.config import settings
from app.core.exceptions import SensitiveWordError

logger = logging.getLogger("ainew.filter")

_words: set[str] | None = None


def load_words() -> set[str]:
    global _words
    if _words is not None:
        return _words
    _words = set()
    path = settings.sensitive_words_path
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            _words = {line.strip() for line in fh if line.strip()}
    return _words


def check_sensitive(text: str) -> str | None:
    if not text:
        return None
    for word in load_words():
        if word and word in text:
            return word
    return None


def assert_clean(text: str) -> None:
    hit = check_sensitive(text)
    if hit:
        raise SensitiveWordError()
