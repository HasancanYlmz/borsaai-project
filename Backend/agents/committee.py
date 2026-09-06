# -*- coding: utf-8 -*-
import sys
import os
from typing import Dict

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import log_event

# ---------------------------------------------------------
# BORSA AI - AJAN: KARAR KOMİTESİ (THE BRAIN)
# Bütün sensörlerden (TradingView, RVOL, Makro, AKD, KAP)
# gelen verileri birleştirir. Nihai Güven Skorunu hesaplar.
# ---------------------------------------------------------

# Haber duygusu için geniş toleranslı anahtar kelime eşleştirme
POZITIF_KELIMELER = ["pozitif", "positive", "pozi"]
NEGATIF_KELIMELER = ["negatif", "negative", "nega"]
KURUMSAL_ALIM_KELIMELER = ["kurumsal_alim", "kurumsal alim", "alim"]
KURUMSAL_SATIS_KELIMELER = ["kurumsal_satis", "kurumsal satis", "satis bosal"]


def _normalize(text: str) -> str:
    """Türkçe karakterleri ASCII'ye çevirir, küçük harfe indirir."""
    replacements = {
        "ı": "i", "İ": "I", "ğ": "g", "Ğ": "G",
        "ü": "u", "Ü": "U", "ş": "s", "Ş": "S",
        "ö": "o", "Ö": "O", "ç": "c", "Ç": "C"
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.lower()


def evaluate_stock_committee(symbol: str, payload: dict) -> Dict:
    """Tüm verileri masaya yatırır ve 100 üzerinden Karar Skoru üretir."""
    log_event("COMMITTEE", f"{symbol} icin Karar Komitesi toplandi.")

    tv_data = payload.get("tv_data", {})
    rvol_data = payload.get("rvol_data", {})
    akd_data = payload.get("akd_data", {})
    news_data = payload.get("news_data", {})

    score = 0.0
    reasons = []

    # 1. TRADINGVIEW (Teknik Analiz Oyu - %30 Etki)
    tv_rec = _normalize(tv_data.get("recommendation", "neutral"))
    if "buy" in tv_rec:
        score += 20.0 if "strong" in tv_rec else 10.0
        reasons.append(f"Teknik: {tv_data.get('recommendation', '')}")
    elif "sell" in tv_rec:
        score -= 20.0
        reasons.append(f"Teknik: {tv_data.get('recommendation', '')}")

    # 2. RVOL VE MOMENTUM (Hacim Oyu - %40 Etki)
    momentum = float(rvol_data.get("momentum_score", 0))
    score += (momentum * 0.4)
    if momentum > 70:
        reasons.append(f"Guclu Hacim (RVOL: {rvol_data.get('rvol_score', '?')})")

    # 3. DOMİNASYON (Köpekbalığı Oyu - %20 Etki)
    verdict_norm = _normalize(akd_data.get("verdict", ""))
    is_alim = any(k in verdict_norm for k in KURUMSAL_ALIM_KELIMELER)
    is_spoofing = akd_data.get("is_spoofing_suspected", False)

    if is_alim and not is_spoofing:
        score += 20.0
        reasons.append("Kurumsal Para Girisi")
    if is_spoofing:
        score -= 50.0
        reasons.append("SPOOFING (Tuzak) Sphesi!")

    # 4. TEMEL HABER (KAP Oyu - %10 Etki)
    sentiment_norm = _normalize(news_data.get("sentiment", ""))
    if any(k in sentiment_norm for k in POZITIF_KELIMELER):
        score += 10.0
        reasons.append("Pozitif KAP Haberi")
    elif any(k in sentiment_norm for k in NEGATIF_KELIMELER):
        score -= 20.0
        reasons.append("Negatif KAP Haberi")

    # Güvenli dönüşüm: önce sınırla, sonra int'e çevir
    final_score = max(0, min(100, int(round(score))))

    # Aksiyon Kararı (Sinir: >=75 AL | 31-74 TUT | <=30 SAT)
    if final_score >= 75:
        decision = "AL"
    elif final_score <= 30:
        decision = "SAT"
    else:
        decision = "TUT"

    log_event("COMMITTEE", f"{symbol} Karari: {decision} (Skor: {final_score}) - Nedenler: {', '.join(reasons)}")

    return {
        "symbol": symbol,
        "score": final_score,
        "decision": decision,
        "reasons": ", ".join(reasons) if reasons else "Notr Piyasa",
        "regime": rvol_data.get("regime", "YATAY")
    }
