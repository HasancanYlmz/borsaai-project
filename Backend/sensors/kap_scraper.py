import requests
import time
from typing import List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import log_event

# ---------------------------------------------------------
# BORSA AI - SENSÖR: KAP CANLI VERİ KAZIYICI
# KAP'ın açık API'sine bağlanıp şirketin son 24 saatteki
# resmi bildirimlerini çeker. IP Ban yememek için 30 dk Cache kullanır.
# ---------------------------------------------------------

_KAP_CACHE = {}
KAP_CACHE_TTL = 1800 # Haberler çok sık düşmez, 30 dakika hafızada tut

def get_kap_news(symbol: str) -> List[str]:
    """Hisseye ait güncel KAP haberlerinin başlıklarını liste olarak döndürür."""
    current_time = time.time()
    
    if symbol in _KAP_CACHE:
        cached_data, timestamp = _KAP_CACHE[symbol]
        if current_time - timestamp < KAP_CACHE_TTL:
            return cached_data
            
    try:
        # KAP Genel Bildirimler API'si (Halka Açık)
        url = "https://www.kap.org.tr/tr/api/disclosures"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            news_list = []
            
            # API'den gelen devasa listeyi tara ve sadece bizim hissemizi bul
            for item in data:
                codes = item.get("stockCodes", "")
                if codes and symbol in codes:
                    title = item.get("disclosureClass", "BİLDİRİM") + " - " + item.get("disclosureName", "")
                    news_list.append(title)
            
            # Eğer KAP'ta o gün haber yoksa, YFinance'in global/günlük haber ağını kontrol et
            if not news_list:
                import yfinance as yf
                try:
                    yf_news = yf.Ticker(f"{symbol}.IS").news
                    for n in yf_news[:3]: # Son 3 haber
                        title = n.get("title", "")
                        if title:
                            news_list.append(f"HABER - {title}")
                except:
                    pass
            
            log_event("KAP_SENSOR", f"{symbol} için {len(news_list)} adet haber bulundu.")
            
            # Sonucu hafızaya (Cache) mühürle
            _KAP_CACHE[symbol] = (news_list, current_time)
            return news_list
            
        return []
        
    except Exception as e:
        log_event("KAP_SENSOR", f"Haber Bağlantı Hatası ({symbol}): {e}", level="WARNING")
        return []
