import time
from collections import defaultdict

class RateLimiter:
    """RateLimiter — diagramme Classes."""

    def __init__(self):
        # Dictionnaire : sender -> liste des timestamps
        self.requests = defaultdict(list)
        # Maximum 10 requêtes par heure par sender
        self.max_requests = 10
        self.window = 3600  # 1 heure en secondes

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