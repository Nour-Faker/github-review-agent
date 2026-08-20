"""
test_webhook.py — GitHub Review Agent
Tests critiques pour WebhookHandler, bot detection, rate limiter, mention handler.
Run: pytest tests/ -v --cov=app --cov-report=term-missing
"""

import pytest
import hmac
import hashlib
import json
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import sys

# ── Mock psycopg2 before any app import ──────────────────────────────────────
sys.modules["psycopg2"] = MagicMock()
sys.modules["psycopg2.extras"] = MagicMock()

from fastapi.testclient import TestClient
from app.webhook import WebhookHandler

with patch("app.database.get_connection", MagicMock()):
    from app.main import app

client = TestClient(app)
SECRET = "test_secret"


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_signature(payload: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def make_pr_payload(action: str = "opened", sender_type: str = "User", login: str = "nour") -> dict:
    return {
        "action": action,
        "sender": {"type": sender_type, "login": login},
        "pull_request": {
            "number": 42,
            "head": {"sha": "abc123"},
        },
        "repository": {"full_name": "nour/test-repo"},
    }


def make_comment_payload(body: str, sender_login: str = "nour", sender_type: str = "User") -> dict:
    return {
        "comment": {"body": body},
        "sender": {"type": sender_type, "login": sender_login},
        "repository": {"full_name": "nour/test-repo"},
        "issue": {"number": 7},
    }


# ═════════════════════════════════════════════════════════════════════════════
# 1. BOT DETECTION
# ═════════════════════════════════════════════════════════════════════════════

class TestIsBotSender:
    def setup_method(self):
        self.handler = WebhookHandler()

    def test_human_sender_not_bot(self):
        payload = {"sender": {"type": "User", "login": "nour"}}
        assert self.handler.is_bot_sender(payload) is False

    def test_bot_type_detected(self):
        payload = {"sender": {"type": "Bot", "login": "some-app"}}
        assert self.handler.is_bot_sender(payload) is True

    def test_bot_login_suffix_detected(self):
        payload = {"sender": {"type": "User", "login": "github-actions[bot]"}}
        assert self.handler.is_bot_sender(payload) is True

    def test_missing_sender_field_is_safe(self):
        """Empty payload must not crash — defaults to not-a-bot."""
        assert self.handler.is_bot_sender({}) is False

    def test_bot_type_and_bot_login_both_trigger(self):
        payload = {"sender": {"type": "Bot", "login": "dependabot[bot]"}}
        assert self.handler.is_bot_sender(payload) is True


# ═════════════════════════════════════════════════════════════════════════════
# 2. WEBHOOK ENDPOINT — HTTP layer
# ═════════════════════════════════════════════════════════════════════════════

class TestWebhookEndpoint:
    def _post(self, payload: dict, event: str, secret: str = SECRET):
        body = json.dumps(payload).encode()
        sig = make_signature(body, secret)
        return client.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": event,
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
        )

    def test_valid_signature_returns_202(self):
        with patch("app.webhook.handler.handle_webhook", new_callable=AsyncMock):
            with patch("app.config.settings.WEBHOOK_SECRET", SECRET):
                response = self._post(make_pr_payload(), "pull_request")
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"

    def test_invalid_signature_returns_401(self):
        body = json.dumps(make_pr_payload()).encode()
        response = client.post(
            "/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": "sha256=totallywrong",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 401

    def test_missing_signature_header_returns_401(self):
        body = json.dumps(make_pr_payload()).encode()
        response = client.post(
            "/webhook",
            content=body,
            headers={"X-GitHub-Event": "pull_request", "Content-Type": "application/json"},
        )
        assert response.status_code == 401

    def test_ping_event_accepted(self):
        payload = {"zen": "Keep it logically awesome."}
        with patch("app.webhook.handler.handle_webhook", new_callable=AsyncMock):
            with patch("app.config.settings.WEBHOOK_SECRET", SECRET):
                response = self._post(payload, "ping")
        assert response.status_code == 202


# ═════════════════════════════════════════════════════════════════════════════
# 3. HANDLE_WEBHOOK — routing logic
# ═════════════════════════════════════════════════════════════════════════════

class TestHandleWebhook:
    def setup_method(self):
        self.handler = WebhookHandler()

    @pytest.mark.asyncio
    async def test_bot_sender_is_ignored(self):
        """Bot payload must exit early — process_pr must never be called."""
        payload = make_pr_payload(sender_type="Bot", login="github-actions[bot]")
        with patch.object(self.handler, "process_pr", new_callable=AsyncMock) as mock_pr:
            await self.handler.handle_webhook(payload, "pull_request")
        mock_pr.assert_not_called()

    @pytest.mark.asyncio
    async def test_quota_exceeded_is_ignored(self):
        payload = make_pr_payload()
        with patch.object(self.handler.limiter, "check_quota", return_value=False):
            with patch.object(self.handler, "process_pr", new_callable=AsyncMock) as mock_pr:
                await self.handler.handle_webhook(payload, "pull_request")
        mock_pr.assert_not_called()

    @pytest.mark.asyncio
    async def test_pr_opened_triggers_process(self):
        payload = make_pr_payload(action="opened")
        with patch.object(self.handler.limiter, "check_quota", return_value=True):
            with patch("asyncio.create_task") as mock_task:
                await self.handler.handle_webhook(payload, "pull_request")
        mock_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_pr_synchronize_triggers_process(self):
        payload = make_pr_payload(action="synchronize")
        with patch.object(self.handler.limiter, "check_quota", return_value=True):
            with patch("asyncio.create_task") as mock_task:
                await self.handler.handle_webhook(payload, "pull_request")
        mock_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_pr_closed_does_nothing(self):
        """Closing a PR must not trigger a review."""
        payload = make_pr_payload(action="closed")
        with patch.object(self.handler.limiter, "check_quota", return_value=True):
            with patch("asyncio.create_task") as mock_task:
                await self.handler.handle_webhook(payload, "pull_request")
        mock_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_event_does_nothing(self):
        payload = make_pr_payload()
        with patch.object(self.handler.limiter, "check_quota", return_value=True):
            with patch("asyncio.create_task") as mock_task:
                await self.handler.handle_webhook(payload, "push")
        mock_task.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# 4. MENTION HANDLER — @ai-reviewer (NF-9)
# ═════════════════════════════════════════════════════════════════════════════

class TestHandleMentionComment:
    def setup_method(self):
        self.handler = WebhookHandler()

    @pytest.mark.asyncio
    async def test_no_mention_is_ignored(self):
        payload = make_comment_payload("just a normal comment")
        with patch("app.commenter.GitHubCommenter.post_single_comment", new_callable=AsyncMock) as mock_post:
            await self.handler.handle_mention_comment(payload)
        mock_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_bot_reply_loop_prevented(self):
        """Comments starting with 🤖 must never trigger another review."""
        payload = make_comment_payload("🤖 **@ai-reviewer** voici mon analyse...")
        with patch("app.commenter.GitHubCommenter.post_single_comment", new_callable=AsyncMock) as mock_post:
            await self.handler.handle_mention_comment(payload)
        mock_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_bot_sender_mention_ignored(self):
        payload = make_comment_payload("@ai-reviewer check this", sender_type="Bot", sender_login="github-actions[bot]")
        with patch("app.commenter.GitHubCommenter.post_single_comment", new_callable=AsyncMock) as mock_post:
            await self.handler.handle_mention_comment(payload)
        mock_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_mention_posts_comment(self):
        payload = make_comment_payload("@ai-reviewer what does this function do?")
        mock_diff = "diff --git a/app/main.py b/app/main.py\n+def foo(): pass"

        with patch.object(self.handler.extractor, "fetch_diff", new_callable=AsyncMock, return_value=mock_diff):
            with patch.object(self.handler.extractor, "is_oversized", return_value=False):
                with patch("app.llm_analyzer.LLMAnalyzer.analyze", return_value="La fonction foo ne fait rien."):
                    with patch("app.commenter.GitHubCommenter.post_single_comment", new_callable=AsyncMock) as mock_post:
                        await self.handler.handle_mention_comment(payload)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        assert "🤖" in call_kwargs["body"]
        assert call_kwargs["pr_id"] == "7"

    @pytest.mark.asyncio
    async def test_oversized_diff_uses_fallback_context(self):
        """Oversized diff must not crash — fallback message used instead."""
        payload = make_comment_payload("@ai-reviewer explain this PR")

        with patch.object(self.handler.extractor, "fetch_diff", new_callable=AsyncMock, return_value="+line\n" * 600):
            with patch.object(self.handler.extractor, "is_oversized", return_value=True):
                with patch("app.llm_analyzer.LLMAnalyzer.analyze", return_value="Analyse OK") as mock_analyze:
                    with patch("app.commenter.GitHubCommenter.post_single_comment", new_callable=AsyncMock):
                        await self.handler.handle_mention_comment(payload)

        # LLM was still called — with fallback context string
        call_args = mock_analyze.call_args[0][0]
        assert "non disponible" in call_args or "volumineux" in call_args

    @pytest.mark.asyncio
    async def test_diff_fetch_failure_uses_fallback(self):
        """If GitHub diff fetch fails, the agent must still respond gracefully."""
        payload = make_comment_payload("@ai-reviewer any bugs?")

        with patch.object(self.handler.extractor, "fetch_diff", new_callable=AsyncMock, side_effect=Exception("GitHub timeout")):
            with patch("app.llm_analyzer.LLMAnalyzer.analyze", return_value="Aucun bug détecté."):
                with patch("app.commenter.GitHubCommenter.post_single_comment", new_callable=AsyncMock) as mock_post:
                    await self.handler.handle_mention_comment(payload)

        # Must not crash — must still post a comment
        mock_post.assert_called_once()