import requests

BASE = "http://127.0.0.1:8000"

# 1. Login
r = requests.post(f"{BASE}/api/auth/login",
    data={"username": "admin@dcic.cl", "password": "Dcic2026!"},
    headers={"Content-Type": "application/x-www-form-urlencoded"})
token = r.json()["access_token"]
print("Login OK")

# 2. Ejecutar migración
headers = {"Authorization": f"Bearer {token}"}
r = requests.post(f"{BASE}/api/migracion/importar-clasificacion", headers=headers)
import json
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
