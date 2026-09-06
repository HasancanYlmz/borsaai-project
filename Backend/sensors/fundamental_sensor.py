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
        inst_pct = info.get("institutionsPercentHeld", 0) * 100 if info.get("institutionsPercentHeld") else 0
        
        # Hacim anomalisi
        vol = info.get("volume", 0)
        avg_vol = info.get("averageVolume", 1)
        vol_spike = (vol / avg_vol) if avg_vol else 1
        
        # Kendi Grafiğimiz için Son 1 Aylık Fiyat Verisi
        hist = ticker.history(period="1mo")
        chart_data = []
        chart_labels = []
        if not hist.empty:
            chart_data = [round(float(x), 2) for x in hist["Close"].tolist()]
            months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
            chart_labels = [f"{d.day} {months[d.month-1]}" for d in hist.index]
        
        target_price = info.get("targetMeanPrice", 0)
        current_price = info.get("currentPrice", 0)
        upside_potential = ((target_price - current_price) / current_price) * 100 if current_price > 0 and target_price > 0 else 0
        
        return {
            "symbol": symbol,
            "market_cap": market_cap,
            "pe_ratio": pe_ratio,
            "pb_ratio": pb_ratio,
            "inst_holdings_pct": inst_pct,
            "volume_spike": vol_spike,
            "upside_potential": upside_potential,
            "chart_data": chart_data,
            "chart_labels": chart_labels
        }
    except Exception as e:
        log_event("ERROR", f"YFinance Veri Hatasi ({symbol}): {e}", level="ERROR")
        return {
            "symbol": symbol, "market_cap": 0, "pe_ratio": 0, "pb_ratio": 0,
            "inst_holdings_pct": 0.0, "volume_spike": 1.0, "upside_potential": 0.0,
            "chart_data": [], "chart_labels": []
        }

def get_chart_data(symbol: str, period_code: str) -> dict:
    """
    Kullanicinin sectigi zaman dilimine gore (1G, 1H, 1A, 3A, 1Y) grafik verisi dondurur.
    """
    yf_symbol = f"{symbol}.IS"
    try:
        ticker = yf.Ticker(yf_symbol)
        
        # Varsayılan (1 Ay)
        period = "1mo"
        interval = "1d"
        
        if period_code == "1G":
            period = "1d"
            interval = "5m" # 15 yerine 5 dakikalık daha akıcı ve detaylı mumlar
        elif period_code == "1H":
            period = "5d"
            interval = "1h"  # Saatlik mumlar
        elif period_code == "3A":
            period = "3mo"
            interval = "1d"
        elif period_code == "1Y":
            period = "1y"
            interval = "1wk" # 1 yıl için haftalık mumlar daha temiz görünür
            
        hist = ticker.history(period=period, interval=interval)
        chart_data = []
        chart_labels = []
        
        if not hist.empty:
            chart_data = [round(float(x), 2) for x in hist["Close"].tolist()]
            
            for d in hist.index:
                if period_code in ["1G", "1H"]:
                    # Saat bazli gosterim
                    chart_labels.append(d.strftime("%H:%M"))
                else:
                    months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
                    if period_code == "1Y":
                        chart_labels.append(f"{months[d.month-1]} '{str(d.year)[2:]}")
                    else:
                        chart_labels.append(f"{d.day} {months[d.month-1]}")
            
            # Kapanış Fiyatı Düzeltmesi:
            # Gün içi verilerde son kapanış seansı (18:00-18:10) eksik kalabiliyor.
            # Grafiğin ucu her zaman resmi kapanış fiyatına (fast_info.last_price) tam otursun.
            try:
                real_close = round(float(ticker.fast_info.get("last_price", chart_data[-1])), 2)
                chart_data[-1] = real_close
                if period_code == "1G" and chart_labels[-1] < "18:00":
                    # Eger piyasa kapandiysa son etiketi Kapanis olarak belirle
                    chart_labels[-1] = "Kapanış"
            except:
                pass
                        
        return {"data": chart_data, "labels": chart_labels}
    except Exception as e:
        log_event("ERROR", f"YFinance Grafik Hatasi ({symbol} - {period_code}): {e}", level="ERROR")
        return {"data": [], "labels": []}
