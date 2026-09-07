import redis
import json
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RedisManager")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class RedisClient:
    def __init__(self):
        try:
            self.client = redis.from_url(REDIS_URL, decode_responses=True)
            self.client.ping()
            logger.info(f"Connected to Redis at {REDIS_URL}")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.client = None

    def publish_tick(self, symbol: str, price: float, volume: float, timestamp: str):
        """Veri Sağlayıcıdan gelen anlık fiyatı (tick) sisteme pompalar."""
        if not self.client: return
        payload = {
            "symbol": symbol,
            "price": price,
            "volume": volume,
            "timestamp": timestamp
        }
        self.client.publish(f"market:ticks:{symbol}", json.dumps(payload))
        # Ayrıca en son fiyatı memory'de tutalım ki API hızlıca okuyabilsin
        self.client.hset("market:latest_prices", symbol, json.dumps(payload))

    def publish_signal(self, symbol: str, decision: str, confidence: int, reason: str):
        """Yapay Zeka (Brain Worker) karar verdiğinde emir motoruna sinyal gönderir."""
        if not self.client: return
        payload = {
            "symbol": symbol,
            "decision": decision,
            "confidence": confidence,
            "reason": reason
        }
        self.client.publish("ai:signals", json.dumps(payload))
