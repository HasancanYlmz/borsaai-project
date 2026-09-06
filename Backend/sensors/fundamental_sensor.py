import yfinance as yf
from typing import Dict
from core.utils import log_event

def get_stock_fundamentals(symbol: str) -> Dict:
    """
    Yahoo Finance API kullanarak hissenin kurumsal sahip (takas) oranlarini,
    temel verilerini (F/K, PD/DD, Piyasa Degeri) ve anlik hacim anomalisini ceker.
    Bu yontem banlanmaz, yasal ve kesintisizdir.
    """
    yf_symbol = f"{symbol}.IS"
    log_event("FUNDAMENTAL", f"{symbol} icin gercek zamanli kurumsal ve temel veriler cekiliyor...")
    
    try:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info
        
        market_cap = info.get("marketCap", 0)
        pe_ratio = info.get("trailingPE", 0)
        pb_ratio = info.get("priceToBook", 0)
        inst_holdings = info.get("heldPercentInstitutions", 0.0)
        avg_volume = info.get("averageVolume", 1)
        current_volume = info.get("volume", 1)
        volume_spike = (current_volume / avg_volume) if avg_volume > 0 else 1.0
        target_price = info.get("targetMeanPrice", 0)
        current_price = info.get("currentPrice", 0)
        upside_potential = ((target_price - current_price) / current_price) * 100 if current_price > 0 and target_price > 0 else 0
        
        return {
            "symbol": symbol,
            "market_cap": market_cap,
            "pe_ratio": pe_ratio,
            "pb_ratio": pb_ratio,
            "inst_holdings_pct": inst_holdings * 100 if inst_holdings else 0,
            "volume_spike": volume_spike,
            "upside_potential": upside_potential
        }
    except Exception as e:
        log_event("ERROR", f"YFinance Veri Hatasi ({symbol}): {e}", level="ERROR")
        return {
            "symbol": symbol, "market_cap": 0, "pe_ratio": 0, "pb_ratio": 0,
            "inst_holdings_pct": 0.0, "volume_spike": 1.0, "upside_potential": 0.0
        }
