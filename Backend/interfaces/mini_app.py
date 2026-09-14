import json

import os

import asyncio

from aiohttp import web

from core.utils import log_event

from agents.gemini_analyst import analyze_stock_with_gemini

from simulator.virtual_broker import execute_virtual_buy

from core.database import get_recent_signals, get_portfolio, get_active_trades

import yfinance as yf



FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Frontend"))



async def handle_tradingview_webhook(request):

    try:

        data = await request.json()

        symbol = data.get("symbol", "")

        action = data.get("action", "").upper()

        price = float(data.get("price", 0.0))



        if not symbol or not action:

            return jsonify({"status": "error", "message": "Gecersiz Payload"}), 400



        if action in ["AL", "BUY"]:

            log_event("WEBHOOK", f"{symbol} icin AL sinyali alindi, YZ analizine gonderiliyor.")

            asyncio.create_task(process_ai_and_buy(symbol, price))

            return jsonify({"status": "received", "action": "buy_process_started"}), 200



        elif action in ["SAT", "SELL"]:

            log_event("WEBHOOK", f"{symbol} icin SAT sinyali alindi, satis basliyor.")

            from simulator.virtual_broker import execute_virtual_sell

            asyncio.create_task(execute_virtual_sell(symbol, price, "TradingView Sinyali (SAT)"))

            return jsonify({"status": "received", "action": "sell_executed"}), 200





        return jsonify({"status": "ignored", "message": "Bilinmeyen Aksiyon"}), 200



    except Exception as e:

        log_event("WEBHOOK_ERROR", f"Hata: {e}", level="ERROR")

        return jsonify({"status": "error", "message": str(e)}), 500



async def process_ai_and_buy(symbol: str, price: float):

    from sensors.trend_filter import check_higher_timeframe_trend

    from interfaces.telegram_bot import send_telegram_message

    trend_ok, trend_msg = check_higher_timeframe_trend(symbol)

    if not trend_ok:

        msg = f"Trend Filtresi REDDI \n\nHisse: {symbol}\nSebep: {trend_msg}\n\nBoga tuzagi riski nedeniyle AL sinyali iptal edildi."

        import asyncio

        await asyncio.to_thread(send_telegram_message, msg)

        return

    from sensors.advanced_filters import check_rsi_cross_validation

    rsi_ok, rsi_msg = check_rsi_cross_validation(symbol)

    if not rsi_ok:

        msg = f" RSI Dogrulama REDDI \n\nHisse: {symbol}\nSebep: {rsi_msg}\n\nTV Sinyali sismis/gecikmeli olabilir."

        import asyncio

        await asyncio.to_thread(send_telegram_message, msg)

        return

    scores_file = r'C:\Users\Hasancan\Desktop\BorsaAI_Proje\Backend\data\ai_scores.json'

    decision = "APPROVE"

    confidence = 75.0

    reason = "Otomatik Onay (AI Skoru Bulunamadi)"

    regime = "BULL"

    if os.path.exists(scores_file):

        try:

            with open(scores_file, 'r', encoding='utf-8') as f:

                scores = json.load(f)

                regime = scores.get("MARKET_REGIME", "BULL")

                if symbol in scores:

                    decision = scores[symbol].get("decision", "REJECT")

                    confidence = scores[symbol].get("confidence", 0.0)

                    reason = scores[symbol].get("reason", "N/A")

        except:

            pass



    from interfaces.telegram_bot import send_telegram_message

    if regime == "BEAR":

        msg = f" <b>PİYASA FİLTRESİ REDDİ</b> \n\n <b>Hisse:</b> {symbol}\n️ BIST100 düşüş trendinde (BEAR). Sistem güvenli modda olduğu için alım durduruldu."

        await asyncio.to_thread(send_telegram_message, msg)

        log_event("AI_AGENT", f"{symbol} reddedildi: Piyasa Rejimi BEAR")

        return



    if decision == "APPROVE" and confidence >= 60.0:

        await execute_virtual_buy(symbol, price, reason, confidence)

    else:

        msg = f" <b>YZ TARAFINDAN REDDEDILDI</b> \n\n <b>Hisse:</b> {symbol}\n <b>Skor:</b> %{confidence}\n <b>Neden:</b> {reason}"

        await asyncio.to_thread(send_telegram_message, msg)

        log_event("AI_AGENT", f"{symbol} reddedildi: {reason}")



# --- FRONTEND APIs ---





MARKET_CACHE = {}

LAST_MARKET_UPDATE = 0



async def api_data(request):

    try:

        from core.database import get_recent_signals

        rows = get_recent_signals(10)

        sigs = []

        for r in rows:

            sigs.append({

                "timestamp": r[0],

                "symbol": r[1],

                "type": r[2],

                "reason": r[5],

                "confidence": r[4]

            })

        return web.json_response({"signals": sigs})

    except Exception as e:

        return web.json_response({"signals": []})



async def fetch_market_data_bg():

    global MARKET_CACHE, LAST_MARKET_UPDATE

    import yfinance as yf

    import asyncio

    import time

    import json

    import os

    symbols = ["AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKSA.IS", "AKSEN.IS", "ALARK.IS", "ALBRK.IS", "ASGYO.IS", "ASELS.IS", "ASTOR.IS", "AYDEM.IS", "BAGFS.IS", "BERA.IS", "BIMAS.IS", "BIOEN.IS", "BRISA.IS", "BRSAN.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS", "CEMTS.IS", "CIMSA.IS", "CWENE.IS", "DOAS.IS", "DOHOL.IS", "ECILC.IS", "EGEEN.IS", "EKGYO.IS", "ENJSA.IS", "ENKAI.IS", "EREGL.IS", "EUREN.IS", "FROTO.IS", "GARAN.IS", "GESAN.IS", "GOLTS.IS", "GOZDE.IS", "GSDHO.IS", "GUBRF.IS", "GWIND.IS", "HALKB.IS", "HEKTS.IS", "IPEKE.IS", "ISCTR.IS", "ISFIN.IS", "ISGYO.IS", "ISMEN.IS", "IZENR.IS", "KARSN.IS", "KCAER.IS", "KCHOL.IS", "KMPUR.IS", "KONTR.IS", "KORDS.IS", "KOZAA.IS", "KOZAL.IS", "KRDMD.IS", "LOGO.IS", "MAVI.IS", "MGROS.IS", "MIATK.IS", "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PARSN.IS", "PETKM.IS", "PGSUS.IS", "PSGYO.IS", "QUAGR.IS", "SAHOL.IS", "SASA.IS", "SISE.IS", "SMRTG.IS", "SOKM.IS", "TATGD.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TTRAK.IS", "TUKAS.IS", "TUPRS.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YKBNK.IS", "YYLGD.IS", "ZOREN.IS", "XU100.IS"]

    try:

        df = yf.download(symbols, period="2d", interval="1d", progress=False)

        if not df.empty:

            cache = {}

            for sym in symbols:

                clean_sym = sym.replace(".IS", "")

                if clean_sym == "XU100": clean_sym = "BIST100"

                try:

                    import math

                    close_today = float(df['Close'][sym].iloc[-1])

                    close_yest = float(df['Close'][sym].iloc[-2])

                    if math.isnan(close_today): close_today = 0.0

                    if math.isnan(close_yest) or close_yest == 0:

                        pct = 0.0

                    else:

                        pct = ((close_today - close_yest) / close_yest) * 100

                        if math.isnan(pct): pct = 0.0

                    cache[clean_sym] = {"price": close_today, "percent": pct, "rvol": 1.0}

                except:

                    cache[clean_sym] = {"price": 0.0, "percent": 0.0, "rvol": 1.0}

            # Read market regime

            scores_file = r'C:\Users\Hasancan\Desktop\BorsaAI_Proje\Backend\data\ai_scores.json'

            regime = "BILINMIYOR"

            if os.path.exists(scores_file):

                try:

                    with open(scores_file, 'r', encoding='utf-8') as sf:

                        sc = json.load(sf)

                        regime = sc.get("MARKET_REGIME", "BILINMIYOR")

                except: pass

            if "BIST100" in cache:

                cache["BIST100"]["regime"] = regime

            MARKET_CACHE = cache

            LAST_MARKET_UPDATE = time.time()

    except:

        pass



async def api_market(request):

    import time

    if time.time() - LAST_MARKET_UPDATE > 120:

        import asyncio

        asyncio.create_task(fetch_market_data_bg())

    return web.json_response(MARKET_CACHE)



async def api_performance(request):
    try:
        from core.database import get_portfolio, get_active_trades
        port = get_portfolio()
        cash = port[0] if port else 12000.0
        trades = get_active_trades()
        positions = []
        total_eq = cash
        for t in trades:
            sym = t[0]
            bp = float(t[1])
            lots = int(t[3])
            cp = MARKET_CACHE.get(sym, {}).get("price", bp)
            if cp == 0: cp = bp
            pnl = (cp - bp) * lots
            pnl_pct = ((cp - bp) / bp * 100) if bp > 0 else 0
            total_eq += (cp * lots)
            positions.append({
                "symbol": sym, "type": "LONG", "lot_amount": lots,
                "buy_price": bp, "current_price": cp, "pnl": pnl, "pnl_pct": pnl_pct
            })
            
        return web.json_response({
            "status": "success",
            "total_cash": cash,
            "total_portfolio_value": total_eq,
            "total_pnl": total_eq - 12000.0,
            "positions": positions
        })
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)})



async def api_history(request):
    try:
        symbol = request.query.get("symbol")
        p = request.query.get("period", "3A")
        
        if p == "1G":
            yf_period = "1d"
            yf_interval = "5m"
        elif p == "1H":
            yf_period = "5d"
            yf_interval = "15m"
        elif p == "1A":
            yf_period = "1mo"
            yf_interval = "1d"
        elif p == "1Y":
            yf_period = "1y"
            yf_interval = "1d"
        else:
            yf_period = "3mo"
            yf_interval = "1d"
            
        import yfinance as yf
        import asyncio
        import pandas as pd
        import math
        ticker = f"{symbol}.IS"
        def fetch_data():
            df = yf.download(ticker, period=yf_period, interval=yf_interval, progress=False)
            if df.empty: return []
            data = []
            for date, row in df.iterrows():
                try:
                    o = float(row["Open"].iloc[0] if isinstance(row["Open"], pd.Series) else row["Open"])
                    h = float(row["High"].iloc[0] if isinstance(row["High"], pd.Series) else row["High"])
                    l = float(row["Low"].iloc[0] if isinstance(row["Low"], pd.Series) else row["Low"])
                    c = float(row["Close"].iloc[0] if isinstance(row["Close"], pd.Series) else row["Close"])
                    v = float(row["Volume"].iloc[0] if isinstance(row["Volume"], pd.Series) else row["Volume"])
                    if math.isnan(o) or math.isnan(c): continue
                    
                    if yf_interval == "1d":
                        t = date.strftime("%Y-%m-%d")
                    else:
                        t = int(date.timestamp()) + 10800
                    
                    data.append({
                        "time": t,
                        "open": o, "high": h, "low": l, "close": c,
                        "value": v
                    })
                except:
                    continue
            return data
        data = await asyncio.to_thread(fetch_data)
        return web.json_response({"status": "success", "data": data})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)})



async def index_handler(request):

    return web.FileResponse(os.path.join(FRONTEND_DIR, 'index.html'))



async def start_mini_app_server():

    app = web.Application()

    app.router.add_post('/api/webhook/tv', handle_tradingview_webhook)

    app.router.add_get('/api/data', api_data)

    app.router.add_get('/api/performance', api_performance)

    app.router.add_get('/api/market', api_market)

    app.router.add_get('/api/history', api_history)

    app.router.add_post('/api/sell', api_sell)

    app.router.add_get('/', index_handler)

    if os.path.exists(FRONTEND_DIR):

        app.router.add_static('/', FRONTEND_DIR)

    port = int(os.environ.get("PORT", 8080))

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(runner, '0.0.0.0', port)

    await site.start()

    log_event("MINI_APP", f"Telegram Mini App sunucusu {port} portunda basladi.")

    while True:

        await asyncio.sleep(3600)