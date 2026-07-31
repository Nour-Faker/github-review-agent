# tests/clean_code.py — no vulnerabilities

import os

def add(a: int, b: int) -> int:
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("Both arguments must be integers")
    return a + b

def divide(a: int, b: int) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def read_file_safe(base_dir: str, filename: str) -> str:
    safe_path = os.path.join(base_dir, os.path.basename(filename))
    with open(safe_path, "r", encoding="utf-8") as f:
        return f.read()