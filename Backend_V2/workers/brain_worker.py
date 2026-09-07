import time
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.redis_manager import RedisClient

class AIBrainWorker:
    """
    FAZ 2 (Yapay Zeka Beyni): Redis nehrinden (Stream) anlık akan verileri yakalar.
    Matematiksel modellerden veya Makine Öğrenmesinden geçirip, emir sinyalleri (AL/SAT) üretir.
    """
    def __init__(self):
        self.redis = RedisClient()
        self.pubsub = self.redis.client.pubsub()
        self.pubsub.psubscribe(**{"market:ticks:*": self.process_tick})
        print("[BRAIN WORKER] Yapay Zeka Beyni aktif. Veri nehrini dinliyor...")

    def process_tick(self, message):
        """Her tick (fiyat degisimi) geldiginde burasi tetiklenir."""
        if message['type'] != 'pmessage':
            return
            
        try:
            data = json.loads(message['data'])
            symbol = data['symbol']
            price = data['price']
            
            # --- YAPAY ZEKA MANTIĞI BURAYA GELECEK ---
            # Şimdilik sadece çok basit bir hacim anomalisi izleyici
            if data['volume'] > 48000:  # Hacim spikeri simülasyonu
                print(f"[AI BRAIN] {symbol} tahtasında anormal hacim tespit edildi! Fiyat: {price}")
                # Kararı Redis üzerinden Emir Motoruna (Execution) yolla
                self.redis.publish_signal(symbol, "AL", 85, "Yapay Zeka: Ani Hacim Patlamasi")
                
        except Exception as e:
            print(f"[BRAIN WORKER ERROR] {e}")

    def run(self):
        # Arka planda mesajları sonsuza kadar dinle
        for message in self.pubsub.listen():
            pass

if __name__ == "__main__":
    worker = AIBrainWorker()
    worker.run()
