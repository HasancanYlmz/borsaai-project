import sys
import os
import json
from typing import List, Dict

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import log_event
from core.config import load_config

_cfg = load_config()

# ---------------------------------------------------------
# BORSA AI - AJAN: TEMEL ANALİZ (KAP HABER YORUMLAYICI)
# Google Gemini LLM API'si kullanılarak KAP haberlerini okur
# ve hisse için POZİTİF/NEGATİF skor üretir.
# ---------------------------------------------------------

def analyze_news_with_ai(symbol: str, news_list: List[str]) -> Dict:
    """Yapay Zeka (LLM) ile haberlerin duygu analizini yapar."""
    log_event("AGENT_FUNDAMENTAL", f"{symbol} için {len(news_list)} KAP haberi analiz ediliyor...")
    
    if not news_list:
        return {"sentiment": "NÖTR", "score": 50, "summary": "Haber Yok"}

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or _cfg.get("api_keys", {}).get("gemini", "")
    
    # API key yoksa basit algoritma (Fallback) çalışsın
    if not GEMINI_API_KEY or GEMINI_API_KEY == "BURAYA_GEMINI_KEY_GELECEK" or GEMINI_API_KEY == "USE_ENV_VAR":
        return _fallback_keyword_analysis(symbol, news_list)

    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        news_text = "\n".join(news_list)
        prompt = f"""
        Aşağıda Borsa İstanbul'da işlem gören {symbol} hissesiyle ilgili son dakika KAP bildirimleri ve haber başlıkları yer almaktadır:
        
        {news_text}
        
        Sen kurumsal bir borsa analisti yapay zekasısın. Bu haberlerin {symbol} hissesine olası 'kısa vadeli' etkisini hesapla.
        Bana sadece geçerli bir JSON objesi döndür, başka hiçbir metin (markdown dahil) ekleme. JSON şu formatta olsun:
        {{"sentiment": "POZİTİF" veya "NEGATİF" veya "NÖTR", "score": (0 ile 100 arası tamsayı, 50 nötrdür), "summary": "Kısa 1-2 cümlelik Türkçe haber özeti"}}
        """
        
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
        )
        
        text = response.text.strip()
        # Temizleme (Eğer model inat edip markdown basarsa)
        if text.startswith('```json'): text = text[7:]
        if text.startswith('```'): text = text[3:]
        if text.endswith('```'): text = text[:-3]
        
        result = json.loads(text.strip())
        
        sentiment = result.get("sentiment", "NÖTR")
        score = result.get("score", 50)
        
        log_event("AGENT_FUNDAMENTAL", f"Gemini Analizi: {symbol} -> {sentiment} (Skor: {score})")
        return {
            "sentiment": sentiment,
            "score": score,
            "summary": result.get("summary", "")
        }
        
    except Exception as e:
        log_event("AGENT_FUNDAMENTAL", f"Gemini API Hatası ({symbol}): {e}", level="ERROR")
        return _fallback_keyword_analysis(symbol, news_list)


def _fallback_keyword_analysis(symbol: str, news_list: List[str]) -> Dict:
    """Eğer API limitlere takılırsa veya Key yoksa, hayat kurtaran ilkel algoritma."""
    positive_keywords = ["ihale", "kar payı", "temettü", "büyüme", "rekor", "teşvik", "anlaşma"]
    negative_keywords = ["zarar", "dava", "iptal", "satış", "ceza", "istifa", "grev"]
    
    pos_count = 0
    neg_count = 0
    
    for news in news_list:
        text = news.lower()
        pos_count += sum(1 for word in positive_keywords if word in text)
        neg_count += sum(1 for word in negative_keywords if word in text)
        
    score = 50 + (pos_count * 10) - (neg_count * 15)
    score = max(0, min(100, score))
    
    if score > 65:
        sentiment = "POZİTİF"
    elif score < 40:
        sentiment = "NEGATİF"
    else:
        sentiment = "NÖTR"
        
    return {
        "sentiment": sentiment,
        "score": score,
        "summary": "AI API kapalı. Kelime taraması ile tespit edildi."
    }
