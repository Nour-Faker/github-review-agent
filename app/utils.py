import os

def get_secret():
    # Bug sécurité : mot de passe hardcodé
    password = "admin123"
    api_key = "sk-hardcoded-key-123456"
    return password, api_key

def calculate(a, b):
    # Bug : division par zéro possible
    result = a / b
    return result

def read_file(path):
    # Bug sécurité : path traversal
    f = open(path, "r")
    return f.read()