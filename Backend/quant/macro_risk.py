import yfinance as yf
from typing import Dict
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import log_event

# ---------------------------------------------------------
# BORSA AI - QUANT: MAKRO RİSK TERMOMETRESİ
# Dünyadaki küresel korkuyu (VIX), Doları ve BİST100'ü ölçer.
# Hem Küresel (Risk-Off) hem de Yerel (İç Piyasa) kriz günlerinde 
# robotun alım yapmasını acımasızca yasaklar.
# ---------------------------------------------------------

def check_global_risk() -> Dict:
    """Korku Endeksi, Dolar ve BİST100 iç piyasa çöküş analizini yapar."""
    log_event("MACRO_RISK", "Makro risk termometresi çalıştırılıyor...")
    
    try:
        # VIX, Dolar/TL ve BİST100 Endeksi (Yerel Krizler İçin)
        tickers = yf.download("^VIX TRY=X XU100.IS", period="2d", progress=False)
        
        if tickers.empty:
            raise ValueError("Yahoo Finance Makro Veri Döndürmedi.")
            
        vix_close = float(tickers['Close']['^VIX'].iloc[-1])
        usd_try_close = float(tickers['Close']['TRY=X'].iloc[-1])
        
        # BİST 100 Günlük Düşüş Hesabı (Yerel Kriz)
        bist_today = float(tickers['Close']['XU100.IS'].iloc[-1])
        bist_yesterday = float(tickers['Close']['XU100.IS'].iloc[-2])
        bist_change_pct = ((bist_today - bist_yesterday) / bist_yesterday) * 100
        
        is_trade_allowed = True
        risk_level = "NORMAL"
        
        # 1. KÜRESEL KRİZ KONTROLÜ
        if vix_close >= 30.0:
            is_trade_allowed = False
            risk_level = "KURESEL_PANIK"
            log_event("MACRO_RISK", f"VIX {vix_close}! Küresel Panik. İşlemler DURDURULDU.", level="WARNING")
        elif vix_close >= 20.0:
            risk_level = "DIKKATLI_OL"
        
        # 2. YEREL KRİZ KONTROLÜ (TÜRKİYE)
        if bist_change_pct <= -3.0:
            is_trade_allowed = False
            risk_level = "YEREL_COKUS"
            log_event("MACRO_RISK", f"BİST100 %{abs(bist_change_pct):.2f} DÜŞÜYOR! Yerel Kriz. İşlemler DURDURULDU.", level="WARNING")
            
        return {
            "vix_score": round(vix_close, 2),
            "usd_try": round(usd_try_close, 4),
            "bist_change_pct": round(bist_change_pct, 2),
            "risk_level": risk_level,
            "is_trade_allowed": is_trade_allowed
        }
        
    except Exception as e:
        log_event("MACRO_RISK", f"Makro veriler çekilirken hata: {e}", level="ERROR")
        return {
            "vix_score": 0.0, "usd_try": 0.0, "bist_change_pct": 0.0,
            "risk_level": "BILINMIYOR", "is_trade_allowed": False
        }
