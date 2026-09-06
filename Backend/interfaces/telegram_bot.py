import asyncio
import requests
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.config import load_config
from core.utils import log_event
from core.database import get_portfolio, get_active_trades, get_recent_signals

_cfg = load_config()

# Environment variables take priority (Railway deployment).
# Falls back to config.json for local development.
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or _cfg.get("api_keys", {}).get("telegram_bot_token", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or _cfg.get("api_keys", {}).get("telegram_chat_id", "")

def send_telegram_message(text: str):
    """Sends a push notification to the user's Telegram."""
    if not BOT_TOKEN or BOT_TOKEN == "BURAYA_BOT_TOKEN_GELECEK":
        return
    if not CHAT_ID or CHAT_ID == "BURAYA_CHAT_ID_GELECEK":
        return
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        log_event("TELEGRAM_BOT", f"Mesaj gonderilemedi: {e}", level="ERROR")

def get_updates(offset=None):
    if not BOT_TOKEN or BOT_TOKEN == "BURAYA_BOT_TOKEN_GELECEK":
        return []
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    # Long-polling: sunucu 30 sn bekler, mesaj gelince aninda cevap verir
    # Bu sayede mesajlar sırada beklemez, anında işlenir
    params = {"timeout": 30, "offset": offset, "allowed_updates": ["message"]}
    try:
        response = requests.get(url, params=params, timeout=35)
        if response.status_code == 200:
            return response.json().get("result", [])
    except Exception:
        pass
    return []

async def telegram_bot_listener():
    """ÇEKİRDEK 3 (ASİSTAN): Telegram'dan gelen mesajları dinler ve yanıtlar."""
    log_event("TELEGRAM_BOT", "Telegram Asistan Cekirdegi Basladi.")
    if not BOT_TOKEN or BOT_TOKEN == "BURAYA_BOT_TOKEN_GELECEK":
        log_event("TELEGRAM_BOT", "Bot Token eksik. Asistan pasif durumda.", level="WARNING")
        return

    offset = None
    while True:
        try:
            updates = await asyncio.to_thread(get_updates, offset)
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message", {})
                chat_id = str(message.get("chat", {}).get("id", ""))
                text = message.get("text", "")
                
                if text:
                    log_event("TELEGRAM_BOT", f"Yeni mesaj alindi: {text} (Chat ID: {chat_id})")
                    
                    # Güvenlik: Sadece kayıtlı Chat ID'ye cevap ver
                    if CHAT_ID and CHAT_ID != "BURAYA_CHAT_ID_GELECEK" and chat_id != str(CHAT_ID):
                        log_event("TELEGRAM_BOT", f"Yetkisiz erisim denemesi! Chat ID: {chat_id}", level="WARNING")
                        continue
                        
                    # Eğer config'de chat_id boşsa, ilk mesaj atan kişinin id'sini logla (Kurulum kolaylığı)
                    if not CHAT_ID or CHAT_ID == "BURAYA_CHAT_ID_GELECEK":
                        log_event("TELEGRAM_BOT", f"--- DIKKAT --- Sizin Chat ID'niz: {chat_id}. Bunu config.json'a kaydedin!")
                    
                    # Komutları işle
                    await handle_command(chat_id, text)
                    
        except Exception as e:
            log_event("TELEGRAM_BOT", f"Dinleyici Hatasi: {e}", level="ERROR")
            
        await asyncio.sleep(1)

async def handle_command(chat_id: str, text: str):
    if text.startswith("/start"):
        msg = "🤖 <b>Borsa AI Asistanina Hosgeldiniz!</b>\n\nKomutlar:\n/portfoy - Cuzdan ve aktif hisseler\n/durum - Sistem durumu\n/sinyaller - Son 5 AI karari"
        send_reply(chat_id, msg)
        
    elif text.startswith("/portfoy"):
        cash, equity = get_portfolio()
        trades = get_active_trades()
        
        msg = f"💼 <b>Portfoy Durumu</b>\n"
        msg += f"Nakit Bakiye: <code>{cash:,.2f} TL</code>\n"
        msg += f"Toplam Ozvarlik: <code>{equity:,.2f} TL</code>\n\n"
        
        msg += "📈 <b>Aktif Hisseler:</b>\n"
        if trades:
            for t in trades:
                symbol, buy_price, lot, buy_time = t
                msg += f"• <b>{symbol}</b>: {lot} Lot (Maliyet: {buy_price:.2f})\n"
        else:
            msg += "<i>Su an aktif hisse bulunmuyor.</i>"
            
        send_reply(chat_id, msg)
        
    elif text.startswith("/sinyaller"):
        signals = get_recent_signals(limit=5)
        msg = "⚡ <b>Son 5 Yapay Zeka Sinyali</b>\n\n"
        for s in signals:
            timestamp, symbol, sig_type, regime, conf, reason = s
            emoji = "🟢" if sig_type == "BUY" else "🔴" if sig_type == "SELL" else "⚪"
            msg += f"{emoji} <b>{symbol}</b>: {sig_type} (Guven: {conf})\n<i>{reason}</i>\n\n"
            
        if not signals:
            msg = "Henuz sinyal yok."
        send_reply(chat_id, msg)
        
    elif text.startswith("/durum"):
        msg = "✅ <b>Sistem Aktif ve Calisiyor.</b>\nPiyasa saatleri icerisinde otomatik tarama ve islem yapiliyor."
        send_reply(chat_id, msg)
        
    elif text.startswith("/canli"):
        parts = text.strip().split()
        if len(parts) < 2:
            send_reply(chat_id, "Kullanim: /canli THYAO")
            return
        symbol = parts[1].upper()
        try:
            import yfinance as yf
            ticker = yf.Ticker(f"{symbol}.IS")
            fi = ticker.fast_info
            price = fi.get("last_price", 0)
            prev_close = fi.get("previous_close", price)
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0
            volume = fi.get("last_volume", 0)
            market_cap = fi.get("market_cap", 0)
            direction = "+" if change >= 0 else ""
            msg = (
                f"<b>{symbol} Canli Veri</b>\n"
                f"Fiyat: <code>{price:.2f} TL</code>\n"
                f"Degisim: <code>{direction}{change:.2f} ({direction}{change_pct:.2f}%)</code>\n"
                f"Hacim: <code>{volume:,}</code>\n"
                f"Piyasa Degeri: <code>{market_cap:,.0f} TL</code>"
            )
        except Exception as e:
            msg = f"{symbol} verisi alinamadi: {e}"
        send_reply(chat_id, msg)
        
    else:
        send_reply(chat_id, "Bilinmeyen komut. Gecerli komutlar: /portfoy, /sinyaller, /durum, /canli HISSE")

def send_reply(chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass
