import time
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.redis_manager import RedisClient

class ExecutionWorker:
    """
    FAZ 3 (Emir ve Risk Motoru): Beyinden (Brain Worker) gelen AL/SAT sinyallerini dinler.
    Körlemesine işlem yapmaz; Kasa yönetimi (Kelly), Komisyon ve Kayma (Slippage)
    hesaplamalarını yaparak gerçek/sanal emri borsaya iletir.
    """
    def __init__(self):
        self.redis = RedisClient()
        self.pubsub = self.redis.client.pubsub()
        self.pubsub.psubscribe(**{"ai:signals": self.process_signal})
        
        # Şimdilik Hafızada Tutulan Sanal Portföy (V1'deki SQLite'ın yeni ve hızlı hali)
        self.portfolio = {
            "cash": 10000.0,
            "positions": {}
        }
        print("[EXECUTION WORKER] Emir Motoru ve Risk Yonetimi aktif. Sinyaller bekleniyor...")

    def process_signal(self, message):
        """Yapay Zeka bir AL/SAT kararı verdiğinde tetiklenir."""
        if message['type'] != 'pmessage':
            return
            
        try:
            data = json.loads(message['data'])
            symbol = data['symbol']
            decision = data['decision']
            reason = data['reason']
            
            # Redis'ten hissenin o anki milisaniyelik fiyatını çek (Derinlik verisi)
            raw_price = self.redis.client.hget("market:latest_prices", symbol)
            if not raw_price:
                print(f"[EXECUTION] {symbol} icin anlik fiyat bulunamadi, islem iptal.")
                return
                
            price_info = json.loads(raw_price)
            current_price = price_info['price']

            # RISK YÖNETİMİ VE İŞLEM
            if decision == "AL" and symbol not in self.portfolio["positions"]:
                self.execute_buy(symbol, current_price, reason)
            elif decision == "SAT" and symbol in self.portfolio["positions"]:
                self.execute_sell(symbol, current_price, reason)
                
        except Exception as e:
            print(f"[EXECUTION ERROR] {e}")

    def execute_buy(self, symbol, price, reason):
        """Kasa yönetimi yaparak alım emrini işler."""
        # KELLY KRİTERİ (Basitleştirilmiş): Kasanın maksimum %20'si ile tek işleme gir.
        max_investment = self.portfolio["cash"] * 0.20
        
        # Slippage (Kayma) ve Komisyon Simülasyonu (Fiyatı %0.2 daha pahalıya alıyormuş gibi)
        execution_price = price * 1.002 
        
        lot = int(max_investment / execution_price)
        if lot > 0:
            total_cost = lot * execution_price
            self.portfolio["cash"] -= total_cost
            self.portfolio["positions"][symbol] = {
                "buy_price": execution_price,
                "lot": lot
            }
            print(f"[EXECUTION] 🟢 ALIM YAPILDI: {symbol} | Maliyet: {execution_price:.2f} | Lot: {lot} | Kalan Nakit: {self.portfolio['cash']:.2f}")
            
            # Telegram Bot'a mesaj atması için Redis'e fırlat
            # self.redis.client.publish("telegram:alerts", ...)

    def execute_sell(self, symbol, price, reason):
        """Hisse satış emrini işler ve Kar/Zarar (PnL) hesaplar."""
        position = self.portfolio["positions"].pop(symbol)
        
        # Slippage ve Komisyon (Fiyatı %0.2 daha ucuza satıyormuş gibi)
        execution_price = price * 0.998
        
        revenue = position["lot"] * execution_price
        self.portfolio["cash"] += revenue
        
        pnl = revenue - (position["buy_price"] * position["lot"])
        durum = "KAR" if pnl > 0 else "ZARAR"
        
        print(f"[EXECUTION] 🔴 SATIS YAPILDI: {symbol} | Satis Fiyati: {execution_price:.2f} | Sonuc: {pnl:.2f} TL {durum}")

    def run(self):
        for message in self.pubsub.listen():
            pass

if __name__ == "__main__":
    worker = ExecutionWorker()
    worker.run()
