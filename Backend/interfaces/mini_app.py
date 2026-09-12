import json
import os
import asyncio
from aiohttp import web
from core.utils import log_event
from agents.gemini_analyst import analyze_stock_with_gemini
from simulator.virtual_broker import execute_virtual_buy

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Frontend"))

async def handle_tradingview_webhook(request):
    try:
        data = await request.json()
        
        if data.get("secret") != "BorsaAI_Gizli_Anahtar_2026":
            return web.json_response({"status": "error", "message": "Unauthorized"}, status=401)
            
        symbol = data.get("symbol")
        action = data.get("action")
        price_str = data.get("price")
        
        if not symbol or not action:
            return web.json_response({"status": "error", "message": "Missing fields"}, status=400)
            
        try:
            price = float(price_str)
        except:
            price = 0.0
            
        log_event("WEBHOOK", f"TradingView Sinyali Alindi: {action} {symbol} @ {price}")
        
        from interfaces.telegram_bot import send_telegram_message
        msg_ilk = f"🚨 <b>TRADINGVIEW SINYALI</b> 🚨\n\n📌 <b>Hisse:</b> {symbol}\n🎯 <b>Yon:</b> {action}\n💰 <b>Fiyat:</b> {price} TL\n\n<i>Yapay zeka haber onayi bekleniyor...</i>"
        send_telegram_message(msg_ilk)
        
        asyncio.create_task(process_ai_and_buy(symbol, price))
        
        return web.json_response({"status": "success", "message": "Sinyal isleme alindi"})
        
    except Exception as e:
        log_event("WEBHOOK_ERROR", f"Hata: {str(e)}", level="ERROR")
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def process_ai_and_buy(symbol: str, price: float):
    ai_result = await analyze_stock_with_gemini(symbol)
    decision = ai_result.get("decision", "REJECT")
    confidence = ai_result.get("confidence", 0.0)
    reason = ai_result.get("reason", "N/A")
    
    if decision == "APPROVE" and confidence >= 60.0:
        await execute_virtual_buy(symbol, price, reason, confidence)
    else:
        from interfaces.telegram_bot import send_telegram_message
        msg = f"❌ <b>YZ TARAFINDAN REDDEDILDI</b> ❌\n\n📌 <b>Hisse:</b> {symbol}\n🤖 <b>Skor:</b> %{confidence}\n📝 <b>Neden:</b> {reason}"
        await asyncio.to_thread(send_telegram_message, msg)
        log_event("AI_AGENT", f"{symbol} reddedildi: {reason}")

async def index_handler(request):
    return web.FileResponse(os.path.join(FRONTEND_DIR, 'index.html'))

async def start_mini_app_server():
    app = web.Application()
    
    # Routes
    app.router.add_post('/api/webhook/tv', handle_tradingview_webhook)
    app.router.add_get('/', index_handler)
    
    # Frontend statik dosyalari
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
