import time
from collections import defaultdict

class RateLimiter:
    """RateLimiter — diagramme Classes. NF-12 + NF-13."""

    def __init__(self):
        self.requests = defaultdict(list)
        self.max_requests = 100
        self.window = 3600

    def check_quota(self, sender: str) -> bool:
        """NF-12 — Vérifie le quota par sender."""
        now = time.time()
        self.requests[sender] = [
            t for t in self.requests[sender]
            if now - t < self.window
        ]
        if len(self.requests[sender]) >= self.max_requests:
            return False
        self.requests[sender].append(now)
        return True

    def check_and_wait_retry(self) -> None:
        """NF-13 — Attend avant retry LLM."""
        print("[RateLimiter] Attente avant retry LLM...")
        time.sleep(10)