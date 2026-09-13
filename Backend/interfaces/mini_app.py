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
        msg = f"⛔ RSI Dogrulama REDDI \n\nHisse: {symbol}\nSebep: {rsi_msg}\n\nTV Sinyali sismis/gecikmeli olabilir."
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
        msg = f"⛔ <b>PİYASA FİLTRESİ REDDİ</b> ⛔\n\n🏢 <b>Hisse:</b> {symbol}\n⚠️ BIST100 düşüş trendinde (BEAR). Sistem güvenli modda olduğu için alım durduruldu."
        await asyncio.to_thread(send_telegram_message, msg)
        log_event("AI_AGENT", f"{symbol} reddedildi: Piyasa Rejimi BEAR")
        return

    if decision == "APPROVE" and confidence >= 60.0:
        await execute_virtual_buy(symbol, price, reason, confidence)
    else:
        msg = f"🛑 <b>YZ TARAFINDAN REDDEDILDI</b> 🛑\n\n🏢 <b>Hisse:</b> {symbol}\n📊 <b>Skor:</b> %{confidence}\n📉 <b>Neden:</b> {reason}"
        await asyncio.to_thread(send_telegram_message, msg)
        log_event("AI_AGENT", f"{symbol} reddedildi: {reason}")

# --- FRONTEND APIs ---

async def api_data(request):
    try:
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
        log_event("API_ERROR", f"/api/data hatasi: {e}")
        return web.json_response({"signals": []})

async def api_performance(request):
    try:
        port = get_portfolio()
        if port:
            cash, _ = port
        else:
            cash = 12000.0
            
        trades = get_active_trades()
        positions = []
        
        total_eq = cash
        total_cost = 0
        
        for t in trades:
            if len(t) < 6: continue
            sym = t[0]
            bp = t[1]
            lots = t[3]
            cp = t[5] 
            pnl = (cp - bp) * lots
            pnl_pct = ((cp - bp) / bp * 100) if bp > 0 else 0
            
            total_eq += (cp * lots)
            total_cost += (bp * lots)
            
            positions.append({
                "symbol": sym,
                "lot_amount": lots,
                "buy_price": bp,
                "current_price": cp,
                "pnl": pnl,
                "pnl_pct": pnl_pct
            })
            
        return web.json_response({
            "total_portfolio_value": total_eq,
            "total_cash": cash,
            "total_pnl": total_eq - 12000,
            "positions": positions
        })
    except Exception as e:
        log_event("API_ERROR", f"/api/performance hatasi: {e}")
        return web.json_response({
            "total_portfolio_value": 12000.0,
            "total_cash": 12000.0,
            "total_pnl": 0.0,
            "positions": []
        })


async def api_sell(request):
    try:
        symbol = request.query.get("symbol")
        if not symbol:
            return web.json_response({"status": "error", "message": "Symbol eksik"})
        
        trades = get_active_trades()
        for t in trades:
            if t[0] == symbol:
                bp = t[1]
                lots = t[3]
                from core.database import remove_trade
                # mock current price as bp for manual quick sell, or fetch live
                # for speed in UI, just close it at bp or last seen
                cp = t[5] if t[5] > 0 else bp 
                pnl = (cp - bp) * lots
                
                remove_trade(symbol, cp, pnl, "Manuel UI Satisi", lots)
                
                from core.database import get_portfolio, update_portfolio_cash
                cash, _ = get_portfolio()
                update_portfolio_cash(cash + (cp * lots))
                
                from interfaces.telegram_bot import send_telegram_message
                import asyncio
                msg = f"🔴 <b>MANUEL SATIS</b> 🔴\n\n📌 Hisse: {symbol}\n💰 Satilan: {lots} Lot"
                asyncio.create_task(asyncio.to_thread(send_telegram_message, msg))
                
                return web.json_response({"status": "success", "message": f"{symbol} basariyla satildi!"})
                
        return web.json_response({"status": "error", "message": "Aktif pozisyon bulunamadi."})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)})


async def api_history(request):
    try:
        symbol = request.query.get("symbol")
        if not symbol:
            return web.json_response({"status": "error", "message": "Symbol eksik"})
            
        import yfinance as yf
        import asyncio
        import pandas as pd
        
        # BIST sembolleri yfinance'ta .IS uzantilidir
        ticker = f"{symbol}.IS"
        
        def fetch_data():
            df = yf.download(ticker, period="3mo", interval="1d", progress=False)
            if df.empty:
                return []
            
            # Create a list of dicts: {time: 'YYYY-MM-DD', value: close_price}
            data = []
            for date, row in df.iterrows():
                # Handling pandas MultiIndex if it occurs
                close_val = row["Close"].iloc[0] if isinstance(row["Close"], pd.Series) else row["Close"]
                if pd.isna(close_val):
                    continue
                data.append({
                    "time": date.strftime("%Y-%m-%d"),
                    "value": float(close_val)
                })
            return data
            
        data = await asyncio.to_thread(fetch_data)
        return web.json_response({"status": "success", "data": data})
    except Exception as e:
        log_event("API_ERROR", f"/api/history hatasi: {e}")
        return web.json_response({"status": "error", "message": str(e)})

async def api_market(request):
    return web.json_response({
        "bist100_value": 9850.50,
        "bist100_pct": 1.2,
        "market_regime": "YUKSELIS (BOGA)",
        "volatility_index": "DUSUK"
    })

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
