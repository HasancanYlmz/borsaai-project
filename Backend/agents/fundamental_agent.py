import sys
import os
from typing import List, Dict

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import log_event

# ---------------------------------------------------------
# BORSA AI - AJAN: TEMEL ANALİZ (KAP HABER YORUMLAYICI)
# İleride Google Gemini LLM API'si bağlanacak olan Ajan taslağıdır.
# Gelen KAP haberlerini okuyup hisse için POZİTİF/NEGATİF skor üretir.
# ---------------------------------------------------------

def analyze_news_with_ai(symbol: str, news_list: List[str]) -> Dict:
    """Yapay Zeka (LLM) ile haberlerin duygu analizini yapar."""
    log_event("AGENT_FUNDAMENTAL", f"{symbol} için {len(news_list)} KAP haberi analiz ediliyor...")
    
    if not news_list:
        return {"sentiment": "NÖTR", "score": 50, "summary": "Haber Yok"}
        
    # TODO: FAZ 5'te buraya Google Gemini AI kodları (Prompt ve API Call) eklenecek.
    # Şimdilik ana mantığı (Mock) kuruyoruz:
    
    positive_keywords = ["ihale", "kar payı", "temettü", "büyüme", "rekor", "teşvik", "anlaşma"]
    negative_keywords = ["zarar", "dava", "iptal", "satış", "ceza", "istifa", "grev"]
    
    pos_count = 0
    neg_count = 0
    
    for news in news_list:
        text = news.lower()
        pos_count += sum(1 for word in positive_keywords if word in text)
        neg_count += sum(1 for word in negative_keywords if word in text)
        
    score = 50 + (pos_count * 10) - (neg_count * 15)
    score = max(0, min(100, score)) # 0 ile 100 arasına kilitle
    
    if score > 65:
        sentiment = "POZİTİF"
    elif score < 40:
        sentiment = "NEGATİF"
    else:
        sentiment = "NÖTR"
        
    log_event("AGENT_FUNDAMENTAL", f"Yapay Zeka Kararı: {symbol} haberleri {sentiment} (Skor: {score})")
    
    return {
        "sentiment": sentiment,
        "score": score,
        "summary": "AI Prompt Motoru FAZ 5'te Aktifleşecek."
    }
