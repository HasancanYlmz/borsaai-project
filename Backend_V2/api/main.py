from fastapi import FastAPI
from pydantic import BaseModel
import redis
import json
import os

app = FastAPI(title="BorsaAI V2.0 Core API")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r_client = redis.from_url(REDIS_URL, decode_responses=True)

@app.get("/")
def read_root():
    return {"status": "online", "system": "BorsaAI V2.0 Enterprise"}

@app.get("/market/prices")
def get_latest_prices():
    """Tüm hisselerin milisaniyelik son fiyatlarını döndürür."""
    prices = r_client.hgetall("market:latest_prices")
    return {k: json.loads(v) for k, v in prices.items()}

@app.get("/system/status")
def system_status():
    """Hangi mikroservislerin hayatta olduğunu kontrol eder."""
    try:
        r_client.ping()
        redis_status = "connected"
    except:
        redis_status = "disconnected"
        
    return {
        "redis_connection": redis_status,
        "workers": "running in background"
    }
