from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
response = client.get("/api/v1/costs/summary?profile_name=default")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
