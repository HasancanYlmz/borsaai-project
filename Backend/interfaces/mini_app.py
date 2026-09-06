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

async def start_mini_app_server():
    """Start the Aiohttp web server on port 8080."""
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_get('/api/data', handle_api_data)
    
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
