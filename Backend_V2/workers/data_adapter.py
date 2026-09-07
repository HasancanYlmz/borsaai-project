import time
import json
import random
import os
import sys
from datetime import datetime
import pytz

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.redis_manager import RedisClient

# BİST30 sembollerinin bir kısmı
TARGET_SYMBOLS = ["THYAO", "KCHOL", "ISCTR", "TUPRS", "GARAN", "ASELS", "BIMAS"]
IST_TZ = pytz.timezone('Europe/Istanbul')

def run_data_fetcher():
    """
    FAZ 1 (Veri Damarı): Matriks/iDeal API alınana kadar Yahoo/Mock verisi üreten
    ve bunu Redis'e saniyede 1 kez pompalayan veri işçisi (Data Worker).
    """
    print("[DATA WORKER] Baslatiliyor...")
    redis_client = RedisClient()
    
    if not redis_client.client:
        print("[DATA WORKER] Redis baglantisi yok! Lutfen Redis server calistirin.")
        return

    print("[DATA WORKER] Veri akisi (Stream) aktif. Matriks IQ baglantisi bekleniyor (Mock Mode).")
    
    # Basit bir fiyat hafızası (Mock için)
    base_prices = {sym: random.uniform(10.0, 100.0) for sym in TARGET_SYMBOLS}
    
    while True:
        try:
            now_str = datetime.now(IST_TZ).strftime("%Y-%m-%d %H:%M:%S")
            
            for symbol in TARGET_SYMBOLS:
                # Rastgele ufak fiyat hareketleri (%0.1)
                change = base_prices[symbol] * random.uniform(-0.001, 0.001)
                base_prices[symbol] += change
                
                live_price = round(base_prices[symbol], 2)
                live_volume = int(random.uniform(5000, 50000))
                
                # Suyu nehre (Redis) döküyoruz!
                redis_client.publish_tick(symbol, live_price, live_volume, now_str)
            
            # Matriks IQ'dan saniyede 1 kez (veya tik başı) veri gelir.
            time.sleep(1)
            
        except Exception as e:
            print(f"[DATA WORKER ERROR] {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_data_fetcher()
