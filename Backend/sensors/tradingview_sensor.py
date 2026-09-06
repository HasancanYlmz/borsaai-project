from tradingview_ta import TA_Handler, Interval, Exchange
from typing import Optional, Dict
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import log_event

# ---------------------------------------------------------
# BORSA AI - SENSÖR: TRADINGVIEW (Canlı Fiyat ve Teknikler)
# ---------------------------------------------------------

_TV_CACHE = {}
CACHE_TTL_SECONDS = 30 # Bir hisse sorulduğunda 30 sn boyunca TV'yi tekrar rahatsız etme!

def get_tv_analysis(symbol: str) -> Optional[Dict]:
    """Hissenin anlık TradingView özetini ve indikatörlerini getirir (Ban Korumalı)."""
    clean_symbol = symbol.replace('.IS', '').upper()
    
    # --- BAN KORUMASI (ÖN BELLEK KONTROLÜ) ---
    current_time = time.time()
    if clean_symbol in _TV_CACHE:
        cached_data, timestamp = _TV_CACHE[clean_symbol]
        if current_time - timestamp < CACHE_TTL_SECONDS:
            return cached_data
            
    try:
        handler = TA_Handler(
            symbol=clean_symbol,
            exchange="BIST",
            screener="turkey",
            interval=Interval.INTERVAL_15_MINUTES
        )
        
        analysis = handler.get_analysis()
        
        result = {
            "symbol": clean_symbol,
            "close_price": analysis.indicators.get("close"),
            "recommendation": analysis.summary.get("RECOMMENDATION"),
            "rsi_14": round(analysis.indicators.get("RSI", 0), 2),
            "macd": round(analysis.indicators.get("MACD.macd", 0), 2),
            "volume": analysis.indicators.get("volume", 0)
        }
        
        log_event("TRADINGVIEW", f"{clean_symbol} anlık analizi çekildi. TV Tavsiyesi: {result['recommendation']}")
        
        # Gelecek sorular için hafızaya kaydet
        _TV_CACHE[clean_symbol] = (result, current_time)
        return result
        
    except Exception as e:
        log_event("TRADINGVIEW", f"{symbol} için TradingView verisi çekilemedi: {e}", level="ERROR")
        return None
