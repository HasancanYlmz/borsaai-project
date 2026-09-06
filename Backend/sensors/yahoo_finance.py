import yfinance as yf
import pandas as pd
from typing import Optional, Dict
import time
import warnings

# Terminali kirleten Pandas FutureWarning mesajlarını sustur
warnings.simplefilter(action='ignore', category=FutureWarning)

# ---------------------------------------------------------
# BORSA AI - SENSÖR: YAHOO FINANCE (V2 - Dinamik Rejimli)
# Bu modül 22 günlük (1 İş Ayı) oturaklı ortalama alır.
# Sadece hacme değil, fiyatın "RALLİ" mi yoksa "YATAY" mı 
# olduğuna (SMA-20) bakarak trendi kaçırmamızı engeller.
# ---------------------------------------------------------

_YAHOO_CACHE = {}
YAHOO_CACHE_TTL = 900 # Geçmiş ortalamalar gün içinde değişmez, 15 dakika hafızada tut!

def get_market_context(symbol: str) -> Optional[Dict]:
    """
    Belirtilen hissenin 22 günlük ortalama hacmini ve güncel piyasa rejimini hesaplar.
    """
    clean_symbol = f"{symbol}.IS" if not symbol.endswith('.IS') else symbol
    
    current_time = time.time()
    if clean_symbol in _YAHOO_CACHE:
        cached_data, timestamp = _YAHOO_CACHE[clean_symbol]
        if current_time - timestamp < YAHOO_CACHE_TTL:
            return cached_data

    try:
        # 2 aylık veri indirilir ki tatiller çıksa bile elimizde net 22 gün kalsın
        data = yf.download(clean_symbol, period="2mo", progress=False)
        
        if data.empty or len(data) < 22:
            return None
        
        recent_data = data.tail(22)
        avg_volume = float(recent_data['Volume'].mean())
        
        # Fiyat Trendi (20 Günlük Basit Hareketli Ortalama - SMA20)
        current_price = float(recent_data['Close'].iloc[-1])
        sma_20 = float(recent_data['Close'].mean())
        
        # --- REJİM (TREND) BELİRLEME ---
        if current_price > (sma_20 * 1.05):
            regime = "RALLİ"
        elif current_price < (sma_20 * 0.95):
            regime = "ÇÖKÜŞ"
        else:
            regime = "YATAY"
            
        result = {
            "avg_volume": avg_volume,
            "sma_20": sma_20,
            "regime": regime
        }
        
        # Sonucu cache'e yaz (Bu satır eksikti! Cache hiç çalışmıyordu!)
        _YAHOO_CACHE[clean_symbol] = (result, current_time)
        return result
        
    except Exception as e:
        print(f"[SENSÖR HATASI] {symbol} geçmiş verisi çekilemedi: {e}")
        return None

def calculate_dynamic_rvol(symbol: str, current_volume: float) -> Optional[Dict]:
    """
    Rejime bağlı akıllı RVOL hesaplayıcı.
    Döndürdüğü veri: RVOL Skoru ve 'Is_Buyable' (Alınabilir mi?) onayı.
    """
    context = get_market_context(symbol)
    
    if not context or context["avg_volume"] == 0:
        return None
        
    rvol = current_volume / context["avg_volume"]
    rvol = round(rvol, 2)
    regime = context["regime"]
    
    # --- YAPAY ZEKA DİNAMİK KURALLARI ---
    is_buyable = False
    
    if regime == "YATAY" and rvol >= 2.0:
        # Uyuyan hisse uyanıyor, kesinlikle AL!
        is_buyable = True
    elif regime == "RALLİ" and rvol >= 1.2:
        # Hisse zaten trendde (şişmiş), ufak bir para girişi bile AL için yeterli!
        is_buyable = True
    elif regime == "ÇÖKÜŞ":
        # Bıçak düşerken tutulmaz, hacim olsa bile ALMA!
        is_buyable = False
        
    return {
        "rvol_score": rvol,
        "regime": regime,
        "is_buyable": is_buyable
    }
