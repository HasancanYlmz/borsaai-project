import yfinance as yf
import pandas as pd
from core.utils import log_event

def check_higher_timeframe_trend(symbol: str) -> tuple[bool, str]:
    try:
        clean_symbol = symbol.replace('BIST:', '') + '.IS'
        df = yf.download(clean_symbol, period="6mo", interval="1d", progress=False)
        
        if df.empty or len(df) < 50:
            return True, "Veri yetersiz, trend filtresi pas gecildi."
            
        if isinstance(df.columns, pd.MultiIndex):
            close_series = df['Close'][clean_symbol]
        else:
            close_series = df['Close']
            
        ema50 = close_series.ewm(span=50, adjust=False).mean()
        
        last_price = float(close_series.iloc[-1])
        last_ema50 = float(ema50.iloc[-1])
        
        if last_price < last_ema50:
            return False, f"Hisse Gunluk EMA50 (:.2f}) yin altinda! Ana trend DUSUS.".format(last_ema50)
            
        return True, f'Trend Onaylandi (Fiyat {last_price:.2f} > EMA50 {last_ema50:.2f})'
        
    except Exception as e:
        log_event("TREND_FILTER", f"{symbol} icin trend kontrolu basarisiz: {e}", level="WARNING")
        return True, "Trend kontrol edilemedi."
