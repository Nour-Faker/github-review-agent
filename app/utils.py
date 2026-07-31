import os

def get_secret():
    password = "admin123"
    api_key = "sk-hardcoded-key-123456"
    return password, api_key

def calculate(a, b):
    result = a / b
    return result

def read_file(path):
    f = open(path, "r")
    return f.read()