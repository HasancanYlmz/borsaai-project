import os
import sys
import json
import asyncio
from aiohttp import web

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.database import get_portfolio, get_active_trades
from core.utils import log_event

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Frontend"))

async def handle_index(request):
    """Serve the Mini App HTML file."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return web.Response(text=content, content_type='text/html')
    return web.Response(text="Frontend bulunamadi.", status=404)

async def handle_api_data(request):
    """Return JSON data for the Mini App dashboard."""
    from core.database import get_recent_signals
    try:
        cash, equity = get_portfolio()
        trades = get_active_trades()
        signals_db = get_recent_signals(limit=10)
        
        trade_list = []
        for t in trades:
            symbol, buy_price, lot, buy_time = t
            trade_list.append({
                "symbol": symbol,
                "buy_price": float(buy_price),
                "lot_amount": float(lot),
                "buy_time": buy_time
            })
            
        signal_list = []
        for s in signals_db:
            timestamp, symbol, sig_type, regime, conf, reason = s
            signal_list.append({
                "timestamp": timestamp,
                "symbol": symbol,
                "type": sig_type,
                "confidence": conf,
                "reason": reason
            })
            
        data = {
            "cash": float(cash),
            "equity": float(equity),
            "trades": trade_list,
            "signals": signal_list
        }
        return web.json_response(data)
    except Exception as e:
        log_event("MINI_APP", f"API Hatasi: {e}", level="ERROR")
        return web.json_response({"error": str(e)}, status=500)

async def handle_api_stock(request):
    """Return fundamental data and news for a specific stock."""
    from sensors.fundamental_sensor import get_stock_fundamentals
    from sensors.kap_scraper import get_kap_news
    
    symbol = request.query.get('symbol')
    if not symbol:
        return web.json_response({"error": "Symbol parameter is missing"}, status=400)
        
    try:
        # Offload to threads if they are blocking, but these are fast enough for now
        fund_data = await asyncio.to_thread(get_stock_fundamentals, symbol)
        news_data = await asyncio.to_thread(get_kap_news, symbol)
        
        return web.json_response({
            "symbol": symbol,
            "fundamentals": fund_data,
            "news": news_data
        })
    except Exception as e:
        log_event("MINI_APP", f"Stock API Hatasi ({symbol}): {e}", level="ERROR")
        return web.json_response({"error": str(e)}, status=500)

async def handle_api_performance(request):
    """Her açık pozisyonun anlık kâr/zarar durumunu hesaplar ve döndürür."""
    import yfinance as yf
    try:
        trades = get_active_trades()
        results = []
        total_pnl = 0.0
        
        for trade in trades:
            symbol, buy_price, lot_amount, buy_time = trade
            try:
                # Anlık fiyatı yfinance'ten çek
                ticker = yf.Ticker(f"{symbol}.IS")
                current_price = ticker.fast_info.get("last_price") or ticker.info.get("currentPrice", 0)
                if not current_price or current_price == 0:
                    current_price = buy_price  # Fiyat çekilemezse maliyeti göster
            except:
                current_price = buy_price

            cost = float(buy_price) * int(lot_amount)
            value = float(current_price) * int(lot_amount)
            pnl = value - cost
            pnl_pct = (pnl / cost) * 100 if cost > 0 else 0
            total_pnl += pnl

            results.append({
                "symbol": symbol,
                "buy_price": float(buy_price),
                "current_price": float(current_price),
                "lot_amount": int(lot_amount),
                "buy_time": buy_time,
                "cost": cost,
                "value": value,
                "pnl": pnl,
                "pnl_pct": pnl_pct
            })

        return web.json_response({
            "positions": results,
            "total_pnl": total_pnl
        })
    except Exception as e:
        log_event("MINI_APP", f"Performance API Hatasi: {e}", level="ERROR")
        return web.json_response({"error": str(e)}, status=500)

async def start_mini_app_server():
    """Start the Aiohttp web server on port 8080."""
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_get('/api/data', handle_api_data)
    app.router.add_get('/api/stock', handle_api_stock)
    app.router.add_get('/api/performance', handle_api_performance)
    # Yeni Grafik Verisi Endpoint'i (Zaman dilimli: 1G, 1H, 1A, 3A, 1Y)
    async def handle_api_chart(request):
        symbol = request.query.get('symbol', 'THYAO')
        period = request.query.get('period', '1A')
        
        try:
            from sensors.fundamental_sensor import get_chart_data
            data = await asyncio.to_thread(get_chart_data, symbol, period)
            return web.json_response(data)
        except Exception as e:
            return web.json_response({"data": [], "labels": []})
            
    app.router.add_get('/api/chart', handle_api_chart)
    
    # Yeni Tüm Piyasa Yüzdelik Değişimleri
    async def handle_api_market(request):
        try:
            import yfinance as yf
            symbols = "AKBNK.IS ALARK.IS ASELS.IS ASTOR.IS BIMAS.IS BRSAN.IS DOAS.IS EKGYO.IS ENKAI.IS EREGL.IS FROTO.IS GARAN.IS GUBRF.IS HEKTS.IS ISCTR.IS KCHOL.IS KONTR.IS KOZAL.IS KRDMD.IS ODAS.IS OYAKC.IS PETKM.IS PGSUS.IS SAHOL.IS SASA.IS SISE.IS TCELL.IS THYAO.IS TOASO.IS TUPRS.IS YKBNK.IS MGROS.IS SOKM.IS MAVI.IS TAVHL.IS TTRAK.IS CCOLA.IS AEFES.IS ULKER.IS VAKBN.IS HALKB.IS ISMEN.IS DOHOL.IS KOZAA.IS IPEKE.IS AKSEN.IS GWIND.IS ALFAS.IS EUPWR.IS CWENE.IS KORDS.IS"
            
            def fetch_batch():
                tickers = yf.Tickers(symbols)
                res = {}
                for sym, t in tickers.tickers.items():
                    try:
                        # yfinance cache'lenmiş olabileceği için fast_info kullanıyoruz
                        prev = t.fast_info.get("previousClose", 0.0)
                        curr = t.fast_info.get("lastPrice", prev)
                        if prev and prev > 0:
                            pct = ((curr - prev) / prev) * 100
                        else:
                            pct = 0.0
                            
                        # RVOL Hesaplama
                        vol = t.fast_info.get("lastVolume", 1)
                        avg_vol = t.fast_info.get("threeMonthAverageVolume", 1)
                        if avg_vol and avg_vol > 0:
                            rvol = vol / avg_vol
                        else:
                            rvol = 0.0
                            
                        clean_sym = sym.replace(".IS", "")
                        res[clean_sym] = {
                            "percent": round(pct, 2),
                            "price": round(curr, 2) if curr else 0.0,
                            "rvol": round(rvol, 2)
                        }
                    except:
                        pass
                return res
                
            data = await asyncio.to_thread(fetch_batch)
            return web.json_response(data)
        except:
            return web.json_response({})
            
    app.router.add_get('/api/market', handle_api_market)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Railway sets PORT env variable. Fall back to 8080 for local dev.
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log_event("MINI_APP", f"Telegram Mini App sunucusu {port} portunda basladi.")
    
    # Keep the server running
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    import asyncio
    asyncio.run(start_mini_app_server())
