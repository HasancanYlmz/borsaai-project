import sys
import os
from typing import Dict

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import log_event
from sensors.yahoo_finance import get_market_context

# ---------------------------------------------------------
# BORSA AI - QUANT: RVOL VE REJİM MOTORU
# Hissedeki canlı hacmin, geçmiş 22 güne kıyasla ne kadar
# patlayıcı olduğunu (RVOL) hesaplayıp 100 üzerinden puanlar.
# ---------------------------------------------------------

def evaluate_momentum(symbol: str, current_volume: float) -> Dict:
    """Canlı hacmi alıp, sistemin rejimine göre Momentum Skoru üretir."""
    log_event("QUANT_RVOL", f"{symbol} için hacim anormalliği hesaplanıyor...")
    
    context = get_market_context(symbol)
    if not context or context["avg_volume"] == 0:
        return {"rvol": 0, "momentum_score": 0, "regime": "BILINMIYOR", "is_strong": False}
        
    rvol = current_volume / context["avg_volume"]
    regime = context["regime"]
    
    # 100 üzerinden Momentum Skoru Hesaplama
    momentum_score = 0
    is_strong = False
    
    if regime == "RALLİ":
        # Trend zaten yukarıysa, ufak hacim bile çok değerlidir.
        momentum_score = min(100, int((rvol / 1.5) * 100))
        if rvol >= 1.2:
            is_strong = True
    elif regime == "YATAY":
        # Uykudaki hisseyi uyandırmak için dev hacim gerekir.
        momentum_score = min(100, int((rvol / 2.5) * 100))
        if rvol >= 2.0:
            is_strong = True
    elif regime == "ÇÖKÜŞ":
        # Çöken hissede hacim tehlikelidir (Mal boşaltma olabilir), skor 0 kalır.
        momentum_score = 0
        is_strong = False
        
    return {
        "rvol": round(rvol, 2),
        "momentum_score": momentum_score,
        "regime": regime,
        "is_strong": is_strong
    }
