import pytest
from app.diff_extractor import DiffExtractor, DiffHunk

extractor = DiffExtractor()

SAMPLE_DIFF = """diff --git a/app/main.py b/app/main.py
index 1234567..abcdefg 100644
--- a/app/main.py
+++ b/app/main.py
@@ -1,5 +1,8 @@
 import os
+import sys
 from fastapi import FastAPI
+app = FastAPI()
+
 def main():
     pass
"""

def test_parse_hunks_returns_list():
    hunks = extractor.parse_hunks(SAMPLE_DIFF)
    assert isinstance(hunks, list)

def test_parse_hunks_detects_file():
    hunks = extractor.parse_hunks(SAMPLE_DIFF)
    assert len(hunks) >= 1
    assert hunks[0].file == "app/main.py"

def test_parse_hunks_content_not_empty():
    hunks = extractor.parse_hunks(SAMPLE_DIFF)
    assert hunks[0].content.strip() != ""

from unittest.mock import patch

def test_is_oversized_false_for_small_diff():
    small_diff = "\n".join(["+line"] * 100)
    with patch("app.diff_extractor.get_setting", return_value="500"):
        assert extractor.is_oversized(small_diff) is False

def test_is_oversized_true_for_large_diff():
    large_diff = "\n".join(["+line"] * 600)
    with patch("app.diff_extractor.get_setting", return_value="500"):
        assert extractor.is_oversized(large_diff) is True


def test_parse_hunks_empty_diff():
    hunks = extractor.parse_hunks("")
    assert hunks == []
