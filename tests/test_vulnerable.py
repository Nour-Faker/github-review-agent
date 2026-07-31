# tests/test_vulnerable.py
# Demo PR — intentional vulnerabilities to test the agent

import os
import sqlite3

# VULN 1 — Hardcoded credentials
PASSWORD = "admin123"
API_KEY = "sk-1234567890abcdef"
SECRET_KEY = "hardcoded-secret-do-not-use"

# VULN 2 — SQL Injection
def get_user(username):
    conn = sqlite3.connect("db.sqlite")
    query = f"SELECT * FROM users WHERE name = '{username}'"
    return conn.execute(query)

# VULN 3 — Path traversal
def read_file(filename):
    with open("/var/data/" + filename) as f:
        return f.read()

# VULN 4 — Division by zero
def calculate_ratio(a, b):
    return a / b

# VULN 5 — Debug mode hardcoded
DEBUG = True