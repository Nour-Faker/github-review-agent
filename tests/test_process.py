"""
test_process_pr.py — GitHub Review Agent
Tests for the process_pr pipeline (webhook.py lines 104-173)

4 paths:
  1. Oversized diff      → DB "oversized" + warning comment
  2. Empty hunks         → DB "analysed" + no-changes comment
  3. Valid hunks + bugs  → LLM analysis + post_review + DB "analysed"
  4. WebSocket broadcast → fires after successful review
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import sys

# ── Mock psycopg2 before any app import ──────────────────────────────────────
sys.modules["psycopg2"] = MagicMock()
sys.modules["psycopg2.extras"] = MagicMock()

from app.webhook import WebhookHandler
from app.diff_extractor import DiffHunk


# ── Shared fixtures ───────────────────────────────────────────────────────────

REPO = "nour/test-repo"
PR_NUMBER = 42
COMMIT_SHA = "abc123"

SAMPLE_DIFF = """diff --git a/app/main.py b/app/main.py
+def foo():
+    pass
"""

def make_hunk(filename="app/main.py"):
    return DiffHunk(file=filename, lines="+def foo():\n+    pass", content="+def foo():\n+    pass", position=1)
def make_analysis_result(is_valid=True, comments=None):
    result = MagicMock()
    result.is_valid = is_valid
    result.comments = comments or ["Potential bug: foo does nothing"]
    return result


# ═════════════════════════════════════════════════════════════════════════════
# PATH 1 — Oversized diff
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_process_pr_oversized_diff():
    """
    When diff exceeds MAX_LINES:
    - DB saved as "processing" then updated to "oversized"
    - Warning comment posted on PR
    - LLM never called
    """
    handler = WebhookHandler()

    with patch("app.database.save_review") as mock_save, \
         patch("app.database.update_review") as mock_update, \
         patch.object(handler.extractor, "fetch_diff", new_callable=AsyncMock, return_value="+line\n" * 600), \
         patch.object(handler.extractor, "is_oversized", return_value=True), \
         patch("app.commenter.GitHubCommenter.post_single_comment", new_callable=AsyncMock) as mock_comment, \
         patch("app.llm_analyzer.LLMAnalyzer.analyze_hunk") as mock_llm:

        await handler.process_pr(REPO, PR_NUMBER, COMMIT_SHA)

    # DB flow
    mock_save.assert_called_once_with(pr_number=PR_NUMBER, repo=REPO, status="processing", bugs=0)
    mock_update.assert_called_once_with(pr_number=PR_NUMBER, repo=REPO, status="oversized", bugs=0)

    # Warning comment posted
    mock_comment.assert_called_once()
    comment_body = mock_comment.call_args.kwargs["body"]
    assert "⚠️" in comment_body

    # LLM never touched
    mock_llm.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# PATH 2 — Empty hunks (no code changes detected)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_process_pr_empty_hunks():
    """
    When diff has no parseable hunks:
    - DB updated to "analysed" with 0 bugs
    - "No changes detected" comment posted
    - LLM never called
    """
    handler = WebhookHandler()

    with patch("app.database.save_review") as mock_save, \
         patch("app.database.update_review") as mock_update, \
         patch.object(handler.extractor, "fetch_diff", new_callable=AsyncMock, return_value=""), \
         patch.object(handler.extractor, "is_oversized", return_value=False), \
         patch.object(handler.extractor, "parse_hunks", return_value=[]), \
         patch("app.commenter.GitHubCommenter.post_single_comment", new_callable=AsyncMock) as mock_comment, \
         patch("app.llm_analyzer.LLMAnalyzer.analyze_hunk") as mock_llm:

        await handler.process_pr(REPO, PR_NUMBER, COMMIT_SHA)

    mock_save.assert_called_once_with(pr_number=PR_NUMBER, repo=REPO, status="processing", bugs=0)
    mock_update.assert_called_once_with(pr_number=PR_NUMBER, repo=REPO, status="analysed", bugs=0)

    mock_comment.assert_called_once()
    comment_body = mock_comment.call_args.kwargs["body"]
    assert "Aucune modification" in comment_body

    mock_llm.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# PATH 3 — Valid hunks with bugs found
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_process_pr_valid_hunks_with_bugs():
    """
    When diff has valid hunks and LLM finds bugs:
    - Each hunk analyzed in parallel
    - post_review called with results
    - DB updated to "analysed" with correct bug count
    """
    handler = WebhookHandler()
    hunks = [make_hunk("app/main.py"), make_hunk("app/utils.py")]
    analysis = make_analysis_result(is_valid=True)

    with patch("app.database.save_review"), \
         patch("app.database.update_review") as mock_update, \
         patch.object(handler.extractor, "fetch_diff", new_callable=AsyncMock, return_value=SAMPLE_DIFF), \
         patch.object(handler.extractor, "is_oversized", return_value=False), \
         patch.object(handler.extractor, "parse_hunks", return_value=hunks), \
         patch("app.llm_analyzer.LLMAnalyzer.analyze_hunk", return_value=analysis), \
         patch("app.commenter.GitHubCommenter.post_review", new_callable=AsyncMock) as mock_review:

        await handler.process_pr(REPO, PR_NUMBER, COMMIT_SHA)

    # post_review called once with all results
    mock_review.assert_called_once()
    call_kwargs = mock_review.call_args.kwargs
    assert call_kwargs["repo"] == REPO
    assert call_kwargs["pr_number"] == PR_NUMBER
    assert call_kwargs["commit_sha"] == COMMIT_SHA
    assert len(call_kwargs["results"]) == 2

    # 2 hunks both flagged as bugs → total_bugs = 2
    mock_update.assert_called_once_with(pr_number=PR_NUMBER, repo=REPO, status="analysed", bugs=2)


@pytest.mark.asyncio
async def test_process_pr_valid_hunks_no_bugs():
    """
    When LLM finds no bugs (is_valid=False for all hunks):
    - DB updated with bugs=0
    """
    handler = WebhookHandler()
    hunks = [make_hunk()]
    clean_analysis = make_analysis_result(is_valid=False, comments=[])

    with patch("app.database.save_review"), \
         patch("app.database.update_review") as mock_update, \
         patch.object(handler.extractor, "fetch_diff", new_callable=AsyncMock, return_value=SAMPLE_DIFF), \
         patch.object(handler.extractor, "is_oversized", return_value=False), \
         patch.object(handler.extractor, "parse_hunks", return_value=hunks), \
         patch("app.llm_analyzer.LLMAnalyzer.analyze_hunk", return_value=clean_analysis), \
         patch("app.commenter.GitHubCommenter.post_review", new_callable=AsyncMock):

        await handler.process_pr(REPO, PR_NUMBER, COMMIT_SHA)

    mock_update.assert_called_once_with(pr_number=PR_NUMBER, repo=REPO, status="analysed", bugs=0)


# ═════════════════════════════════════════════════════════════════════════════
# PATH 4 — WebSocket broadcast (NF-27)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_process_pr_websocket_broadcast_fires():
    handler = WebhookHandler()
    hunks = [make_hunk()]
    analysis = make_analysis_result(is_valid=True)

    mock_manager = MagicMock()
    mock_manager.broadcast = AsyncMock()

    with patch("app.database.save_review"), \
         patch("app.database.update_review"), \
         patch.object(handler.extractor, "fetch_diff", new_callable=AsyncMock, return_value=SAMPLE_DIFF), \
         patch.object(handler.extractor, "is_oversized", return_value=False), \
         patch.object(handler.extractor, "parse_hunks", return_value=hunks), \
         patch("app.llm_analyzer.LLMAnalyzer.analyze_hunk", return_value=analysis), \
         patch("app.commenter.GitHubCommenter.post_review", new_callable=AsyncMock), \
         patch.dict("sys.modules", {"app.main": MagicMock(manager=mock_manager)}), \
         patch("app.webhook.asyncio.create_task") as mock_task:

        await handler.process_pr(REPO, PR_NUMBER, COMMIT_SHA)

    mock_task.assert_called()

@pytest.mark.asyncio
async def test_process_pr_websocket_failure_does_not_crash():
    """
    If WebSocket manager import fails, process_pr must complete without raising.
    This tests the try/except around the broadcast block.
    """
    handler = WebhookHandler()
    hunks = [make_hunk()]
    analysis = make_analysis_result(is_valid=True)

    with patch("app.database.save_review"), \
         patch("app.database.update_review"), \
         patch.object(handler.extractor, "fetch_diff", new_callable=AsyncMock, return_value=SAMPLE_DIFF), \
         patch.object(handler.extractor, "is_oversized", return_value=False), \
         patch.object(handler.extractor, "parse_hunks", return_value=hunks), \
         patch("app.llm_analyzer.LLMAnalyzer.analyze_hunk", return_value=analysis), \
         patch("app.commenter.GitHubCommenter.post_review", new_callable=AsyncMock), \
         patch("app.webhook.asyncio.create_task", side_effect=RuntimeError("no event loop")):

        # Must not raise — exception is caught internally
        await handler.process_pr(REPO, PR_NUMBER, COMMIT_SHA)