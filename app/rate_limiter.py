import time
from collections import defaultdict

class RateLimiter:
    """RateLimiter — diagramme Classes."""

    def __init__(self):
        self.requests = defaultdict(list)
        self.max_requests = 100  # ← change 10 par 100
        self.window = 3600

    def check_quota(self, sender: str) -> bool:
        """Vérifie si le sender n'a pas dépassé son quota."""
        now = time.time()
        # Garder seulement les requêtes dans la fenêtre
        self.requests[sender] = [
            t for t in self.requests[sender]
            if now - t < self.window
        ]
        if len(self.requests[sender]) >= self.max_requests:
            return False
        self.requests[sender].append(now)
        return True

    def check_and_wait_retry(self) -> None:
        """Attend avant de retry si quota LLM dépassé — NF-13."""
        print("[RateLimiter] Attente avant retry LLM...")
        time.sleep(10)