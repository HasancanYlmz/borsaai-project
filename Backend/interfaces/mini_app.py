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

        if action == "AL":
            log_event("WEBHOOK", f"{symbol} icin AL sinyali alindi, YZ analizine gonderiliyor.")
            asyncio.create_task(process_ai_and_buy(symbol, price))
            return jsonify({"status": "received", "action": "buy_process_started"}), 200

        elif action == "SAT":
            log_event("WEBHOOK", f"{symbol} icin SAT sinyali alindi, satis basliyor.")
            from simulator.virtual_broker import execute_virtual_sell
            asyncio.create_task(execute_virtual_sell(symbol, price, "TradingView Sinyali (SAT)"))
            return jsonify({"status": "received", "action": "sell_executed"}), 200

        elif action == "SHORT":
            log_event("WEBHOOK", f"{symbol} icin SHORT sinyali alindi.")
            from simulator.virtual_broker import execute_viop_short
            asyncio.create_task(execute_viop_short(symbol, price, "TradingView SHORT Sinyali", 80.0))
            return jsonify({"status": "received", "action": "short_executed"}), 200
            
        elif action in ["COVER", "SHORT_KAPAT"]:
            log_event("WEBHOOK", f"{symbol} icin COVER sinyali alindi.")
            from simulator.virtual_broker import execute_viop_cover
            asyncio.create_task(execute_viop_cover(symbol, price, "TradingView COVER Sinyali"))
            return jsonify({"status": "received", "action": "cover_executed"}), 200

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
    
    symbols = ["AKBNK.IS", "ALARK.IS", "ASELS.IS", "ASTOR.IS", "BIMAS.IS", "BRSAN.IS", "DOAS.IS", "EKGYO.IS", "ENKAI.IS", "EREGL.IS", "FROTO.IS", "GARAN.IS", "GUBRF.IS", "HEKTS.IS", "ISCTR.IS", "KCHOL.IS", "KONTR.IS", "KOZAL.IS", "KRDMD.IS", "ODAS.IS", "OYAKC.IS", "PETKM.IS", "PGSUS.IS", "SAHOL.IS", "SASA.IS", "SISE.IS", "TCELL.IS", "THYAO.IS", "TOASO.IS", "TUPRS.IS", "YKBNK.IS", "XU100.IS"]
    try:
        df = yf.download(symbols, period="2d", interval="1d", progress=False)
        if not df.empty:
            cache = {}
            for sym in symbols:
                clean_sym = sym.replace(".IS", "")
                if clean_sym == "XU100": clean_sym = "BIST100"
                try:
                    close_today = float(df['Close'][sym].iloc[-1])
                    close_yest = float(df['Close'][sym].iloc[-2])
                    pct = ((close_today - close_yest) / close_yest) * 100
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
        from core.database import get_portfolio, get_active_trades, get_viop_trades
        port = get_portfolio()
        cash = port[0] if port else 12000.0
            
        trades = get_active_trades()
        viop = get_viop_trades()
        
        positions = []
        total_eq = cash
        
        # LONG Positions
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
            
        # SHORT Positions
        for v in viop:
            sym = v[0]
            sp = float(v[1])
            lots = int(v[2])
            cp = MARKET_CACHE.get(sym, {}).get("price", sp)
            if cp == 0: cp = sp
            
            pnl = (sp - cp) * lots
            pnl_pct = ((sp - cp) / sp * 100) if sp > 0 else 0
            
            total_eq += (sp * lots) + pnl
            
            positions.append({
                "symbol": sym, "type": "SHORT", "lot_amount": lots,
                "buy_price": sp, "current_price": cp, "pnl": pnl, "pnl_pct": pnl_pct
            })
            
        return web.json_response({
            "total_portfolio_value": total_eq,
            "total_cash": cash,
            "total_pnl": total_eq - 12000.0,
            "positions": positions
        })
    except Exception as e:
        return web.json_response({"error": str(e)})

async def api_sell(request):
    try:
        symbol = request.query.get("symbol")
        if not symbol: return web.json_response({"status": "error", "message": "Symbol eksik"})
        
        from core.database import get_active_trades, get_viop_trades
        from simulator.virtual_broker import execute_virtual_sell, execute_viop_cover
        
        trades = get_active_trades()
        for t in trades:
            if t[0] == symbol:
                cp = MARKET_CACHE.get(symbol, {}).get("price", t[1])
                import asyncio
                asyncio.create_task(execute_virtual_sell(symbol, cp, "Arayuz Manuel Satis"))
                return web.json_response({"status": "success", "message": f"{symbol} LONG pozisyonu kapatiliyor..."})
                
        viop = get_viop_trades()
        for v in viop:
            if v[0] == symbol:
                cp = MARKET_CACHE.get(symbol, {}).get("price", v[1])
                import asyncio
                asyncio.create_task(execute_viop_cover(symbol, cp, "Arayuz Manuel Cover"))
                return web.json_response({"status": "success", "message": f"{symbol} SHORT pozisyonu kapatiliyor..."})
                
        return web.json_response({"status": "error", "message": "Acik pozisyon bulunamadi."})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)})

async def api_history(request):
    try:
        symbol = request.query.get("symbol")
        import yfinance as yf
        import asyncio
        import pandas as pd
        
        ticker = f"{symbol}.IS"
        def fetch_data():
            df = yf.download(ticker, period="3mo", interval="1d", progress=False)
            if df.empty: return []
            data = []
            for date, row in df.iterrows():
                close_val = row["Close"].iloc[0] if isinstance(row["Close"], pd.Series) else row["Close"]
                if pd.isna(close_val): continue
                data.append({"time": date.strftime("%Y-%m-%d"), "value": float(close_val)})
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
