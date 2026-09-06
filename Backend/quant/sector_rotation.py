import yfinance as yf
from typing import Dict, List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import log_event

# ---------------------------------------------------------
# BORSA AI - QUANT: SEKTÖREL ROTASYON 
# Para Bankalara mı giriyor (XBANK), Sanayiye mi (XUSIN) yoksa 
# Ulaştırmaya mı (XUMES)? Robotun doğru okyanusta balık 
# tutmasını sağlayan pusula modülüdür.
# ---------------------------------------------------------

# BİST Ana Sektör Endekslerinin Yahoo Finance Karşılıkları
SECTOR_INDICES = {
    "XU100": "BİST 100",
    "XBANK": "Bankacılık",
    "XUSIN": "Sınai (Sanayi)",
    "XUMES": "Metal Ana",
    "XILTM": "İletişim"
}

def analyze_sector_rotation() -> Dict[str, str]:
    """
    Sektör endekslerinin günlük değişimlerini kıyaslayarak
    hangi sektöre para girdiğini, hangisinden çıktığını bulur.
    """
    log_event("SECTOR", "Sektörel para rotasyonu analiz ediliyor...")
    
    rotation_result = {}
    
    try:
        # Tüm endekslerin son 2 günlük verisini tek seferde çek (.IS formatında)
        symbols = " ".join([f"{ticker}.IS" for ticker in SECTOR_INDICES.keys()])
        data = yf.download(symbols, period="5d", progress=False)
        
        if data.empty:
            return rotation_result
            
        for ticker, name in SECTOR_INDICES.items():
            full_ticker = f"{ticker}.IS"
            
            try:
                # Kapanış fiyatı sütunundan sadece o endekse ait olanı al
                close_prices = data['Close'][full_ticker].dropna()
                
                if len(close_prices) >= 2:
                    today = float(close_prices.iloc[-1])
                    yesterday = float(close_prices.iloc[-2])
                    
                    # Günlük Yüzde Değişim
                    change_pct = ((today - yesterday) / yesterday) * 100
                    
                    if change_pct > 1.5:
                        trend = "GÜÇLÜ PARA GİRİŞİ"
                    elif change_pct < -1.5:
                        trend = "GÜÇLÜ PARA ÇIKIŞI"
                    else:
                        trend = "YATAY/STABİL"
                        
                    rotation_result[ticker] = {
                        "name": name,
                        "change_pct": round(change_pct, 2),
                        "trend": trend
                    }
            except KeyError:
                continue
                
        log_event("SECTOR", f"Rotasyon haritası çıkarıldı. Analiz edilen sektör sayısı: {len(rotation_result)}")
        return rotation_result
        
    except Exception as e:
        log_event("SECTOR", f"Sektör verisi çekilemedi: {e}", level="ERROR")
        return {}
