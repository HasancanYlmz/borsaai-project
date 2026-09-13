import yfinance as yf
import pandas as pd
from core.utils import log_event

def get_stock_sector(symbol: str) -> str:
    try:
        clean_sym = symbol.replace('BIST:', '') + '.IS'
        info = yf.Ticker(clean_sym).info
        return info.get('sector', 'Unknown')
    except:
        return 'Unknown'

def get_volatility_allocation(symbol: str) -> float:
    # Hissenin son 14 gunluk oynakligina gore bakiye tahsisi yapar.
    try:
        clean_sym = symbol.replace('BIST:', '') + '.IS'
        df = yf.download(clean_sym, period='1mo', interval='1d', progress=False)
        if df.empty: return 0.15 # Varsayilan guvenli oran %15
        
        if isinstance(df.columns, pd.MultiIndex):
            close = df['Close'][clean_sym]
            high = df['High'][clean_sym]
            low = df['Low'][clean_sym]
        else:
            close, high, low = df['Close'], df['High'], df['Low']
            
        # Gunluk ortalama dalgalanma (High - Low) / Close
        daily_range_pct = ((high - low) / close).tail(14).mean()
        
        if daily_range_pct > 0.05: # Gunde %5'ten fazla dalgalaniyor (Cok Riskli)
            return 0.10 # Sadece %10 para bagla
        elif daily_range_pct > 0.03: # Orta riskli
            return 0.15
        else: # Sakin hisse (KCHOL vb.)
            return 0.25 # %25 para baglanabilir
    except Exception as e:
        log_event('ADV_FILTER', f'Volatilite hatasi ({symbol}): {e}')
        return 0.15

def check_rsi_cross_validation(symbol: str) -> tuple[bool, str]:
    # TradingView AL dediginde, RSI 70 uzerindeyse (Asiri Alim) emri reddet!
    try:
        clean_sym = symbol.replace('BIST:', '') + '.IS'
        df = yf.download(clean_sym, period='5d', interval='5m', progress=False)
        if df.empty or len(df) < 15:
            return True, 'Veri yetersiz, dogrulama atlandi.'
            
        if isinstance(df.columns, pd.MultiIndex):
            close = df['Close'][clean_sym]
        else:
            close = df['Close']
            
        # RSI Hesaplama (14 periyot)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        last_rsi = float(rsi.iloc[-1])
        
        if last_rsi > 70:
            return False, f'TV sinyali AL diyor ancak RSI {last_rsi:.1f} (Asiri Sismis!). Tepeden mal alinmaz.'
        if last_rsi < 30:
            return True, f'RSI Cok Uygun ({last_rsi:.1f}) - Harika Dip Firsati'
            
        return True, f'RSI Normal ({last_rsi:.1f})'
    except Exception as e:
        log_event('ADV_FILTER', f'RSI hesaplanamadi: {e}')
        return True, 'RSI kontrol edilemedi.'
