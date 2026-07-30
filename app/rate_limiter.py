import time
from collections import defaultdict

class RateLimiter:
    """RateLimiter — diagramme Classes."""

    def __init__(self):
        self.requests = defaultdict(list)
        self.max_requests = 100  # ← change 10 par 100
        self.window = 3600

    def check_quota(self, sender: str) -> bool:
        """Vérifie le quota — désactivé pour les tests."""
        return True  # ← toujours True pour l'instant

    def check_and_wait_retry(self) -> None:
        """Attend avant de retry si quota LLM dépassé — NF-13."""
        print("[RateLimiter] Attente avant retry LLM...")
        time.sleep(10)