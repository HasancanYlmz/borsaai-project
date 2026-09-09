import asyncio
import sys
import os
import signal
from decimal import Decimal
from datetime import time as dt_time

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.database import init_db, get_portfolio, get_active_symbols, get_active_trades, remove_trade, save_trade, save_signal, update_portfolio_cash
from core.utils import log_event, get_ist_time
from core.models import Portfolio, SignalType
from core.signal_generator import generate_signal

from sensors.yahoo_finance import calculate_dynamic_rvol
from sensors.tradingview_sensor import get_tv_analysis
from sensors.fundamental_sensor import get_stock_fundamentals
from sensors.kap_scraper import get_kap_news
from quant.dominance import detect_spoofing_and_dominance
from agents.committee import evaluate_stock_committee
from agents.fundamental_agent import analyze_news_with_ai
from simulator.order_router import execute_virtual_order, execute_virtual_sell
from interfaces.telegram_bot import telegram_bot_listener, send_telegram_message

IS_RUNNING = True

# 7/24 toplanan verilerin saklandığı Küresel Hafıza (Memory)
_GLOBAL_MEMORY = {}

from core.config import load_config

_cfg = load_config()
_trading_cfg = _cfg.get("trading", {})
TARGET_SYMBOLS = _trading_cfg.get("symbols", [
    "AKBNK", "ALARK", "ASELS", "ASTOR", "BIMAS", "BRSAN", "DOAS", "EKGYO", 
    "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", "ISCTR", "KCHOL", 
    "KONTR", "KOZAL", "KRDMD", "ODAS", "OYAKC", "PETKM", "PGSUS", "SAHOL", 
    "SASA", "SISE", "TCELL", "THYAO", "TOASO", "TUPRS", "YKBNK",
    # BIST50 İlaveleri
    "MGROS", "SOKM", "MAVI", "TAVHL", "TTRAK", "CCOLA", "AEFES", "ULKER",
    "VAKBN", "HALKB", "ISMEN", "DOHOL", "KOZAA", "IPEKE", "AKSEN", "GWIND",
    "ALFAS", "EUPWR", "CWENE", "KORDS"
])

def handle_exit(sig, frame):
    global IS_RUNNING
    log_event("SYSTEM", "Shutdown signal received. Terminating processes safely.", level="WARNING")
    IS_RUNNING = False

async def news_and_tv_watcher():
    """Market data watcher process (KAP & TradingView)."""
    log_event("WATCHER", "Data watcher process initialized.")
    while IS_RUNNING:
        try:
            for symbol in TARGET_SYMBOLS:
                if not IS_RUNNING: break
                
                # Use to_thread for synchronous network calls to prevent blocking the event loop
                tv_data = await asyncio.to_thread(get_tv_analysis, symbol)
                news_list = await asyncio.to_thread(get_kap_news, symbol)
                news_data = await asyncio.to_thread(analyze_news_with_ai, symbol, news_list)
                
                # Hafızaya kaydet
                _GLOBAL_MEMORY[symbol] = {
                    "tv_data": tv_data,
                    "news_data": news_data
                }
                
                await asyncio.sleep(1) # API'leri yormamak için kısa bekleme
                
            # Tüm listeyi taradıktan sonra 3 dakika dinlen
            for _ in range(180):
                if not IS_RUNNING: break
                await asyncio.sleep(1)
                
        except Exception as e:
            log_event("ERROR", f"Data watcher loop error: {e}", level="ERROR")
            await asyncio.sleep(10)

from core.sectors import get_sector

def check_bist100_health() -> float:
    """BIST100 endeksinin günlük yüzde değişimini hesaplar."""
    try:
        import yfinance as yf
        t = yf.Ticker("XU100.IS")
        prev = t.fast_info.get("previousClose", 1.0)
        curr = t.fast_info.get("lastPrice", prev)
        return ((curr - prev) / prev) * 100
    except:
        return 0.0

def check_global_panic() -> bool:
    """VIX endeksini kontrol ederek küresel panik olup olmadığını saptar."""
    try:
        import yfinance as yf
        t = yf.Ticker("^VIX")
        vix_price = t.fast_info.get("lastPrice", 0.0)
        if vix_price >= 25.0:
            return True
        return False
    except:
        return False

def check_sector_exposure(new_symbol: str, active_symbols: list) -> bool:
    """Aynı sektörden 2'den fazla hisse alınmasını engeller."""
    target_sector = get_sector(new_symbol)
    if target_sector == "UNKNOWN":
        return True # Bilinmeyen sektöre izin ver
        
    count = 0
    for sym in active_symbols:
        if get_sector(sym) == target_sector:
            count += 1
            
    return count < 2 # 2'den küçükse izin ver (En fazla 2)

async def market_trader():
    """Market trader process (AKD, RVOL, Order routing)."""
    log_event("TRADER", "Market trader process initialized.")
    while IS_RUNNING:
        try:
            now = get_ist_time()
            # Sadece Hafta İçi ve 09:55 - 18:10 arası işlem yap (Sanal Testin Gerçekçi Olması İçin)
            if now.weekday() >= 5 or not (dt_time(9, 55) <= now.time() <= dt_time(18, 10)):
                log_event("TRADER", f"Piyasa kapali. Bekleniyor... ({now.strftime('%H:%M')})")
                await asyncio.sleep(300) # 5 dk uyu
                continue
                
            # Borsa Açık! Cüzdanı çek.
            cash, equity = get_portfolio()
            portfolio = Portfolio(id=1, cash_balance=Decimal(str(cash)), total_equity=Decimal(str(equity)))
            active_symbols = get_active_symbols()
            
            # --- PİYASA REJİMİ FİLTRESİ (BIST100 KALKANI) ---
            bist100_change = await asyncio.to_thread(check_bist100_health)
            is_market_crashing = bist100_change < -1.0 # Endeks %1'den fazla eksideyken kalkanı aç
            
            # --- KÜRESEL PANİK RADARI (VIX KALKANI) ---
            is_global_panic = await asyncio.to_thread(check_global_panic)
            
            log_event("LOOP", f"New trading cycle. Cash: {portfolio.cash_balance:.2f} TRY, Active trades: {len(active_symbols)}, BIST100: %{bist100_change:.2f}")
            if is_market_crashing:
                log_event("SHIELD", f"BIST100 KALKANI AKTİF! Endeks çöküşte (%{bist100_change:.2f}). Yeni alımlar durduruldu.")
            if is_global_panic:
                log_event("SHIELD", f"VIX KÜRESEL PANİK RADARI AKTİF! Wall Street çöküşte (VIX >= 25). BIST30 alımları askıya alındı.")
            
            for symbol in TARGET_SYMBOLS:
                if not IS_RUNNING: break
                
                # Gece nöbetçisinin (Watcher) hafızasındaki verileri al
                memory = _GLOBAL_MEMORY.get(symbol, {})
                tv_data = memory.get("tv_data")
                news_data = memory.get("news_data", {"sentiment": "NÖTR", "score": 50})
                
                if not tv_data:
                    continue # Nöbetçi henüz veriyi çekmemişse atla
                
                # Anlık Gündüz Verilerini Çek (RVOL ve Kurumsal Veriler)
                live_volume = tv_data.get("volume", 0)
                rvol_data = await asyncio.to_thread(calculate_dynamic_rvol, symbol, live_volume) 
                if not rvol_data:
                    rvol_data = {"momentum_score": 0, "regime": "YATAY", "rvol_score": 0}
                    
                # YFinance üzerinden Kurumsal Takas Oranı ve Hacim Anomalisi (Eski Telegram AKD'si yerine)
                fundamental_data = await asyncio.to_thread(get_stock_fundamentals, symbol)
                
                # Komiteye Gönder
                payload = {
                    "tv_data": tv_data,
                    "rvol_data": rvol_data,
                    "fundamental_data": fundamental_data,
                    "news_data": news_data
                }
                
                committee_res = await asyncio.to_thread(evaluate_stock_committee, symbol, payload)
                sig = generate_signal(committee_res)
                save_signal(sig.symbol, sig.signal_type.value, sig.regime.value, sig.confidence_score, sig.reason)
                
                # Alım/Satım Emirleri
                live_price_raw = tv_data.get("close_price", 0)
                if live_price_raw and live_price_raw > 0:
                    current_price = Decimal(str(live_price_raw))
                    
                    # --- MANUEL PORTFÖY İZLEYEN STOP VE ZARAR KES ---
                    user_trades = get_active_trades()
                    user_owns_symbol = False
                    pnl_pct = 0.0
                    
                    for t in user_trades:
                        if t[0] == symbol:
                            user_owns_symbol = True
                            buy_price = float(t[1])
                            curr_price = float(current_price)
                            
                            memory = _GLOBAL_MEMORY.setdefault(symbol, {})
                            highest_seen = memory.get("highest_seen", buy_price)
                            
                            if curr_price > highest_seen:
                                memory["highest_seen"] = curr_price
                                highest_seen = curr_price
                            
                            pnl_pct = ((curr_price - buy_price) / buy_price) * 100
                            
                            trailing_stop_price = highest_seen * 0.9825 # -%1.75
                            
                            if curr_price <= trailing_stop_price and pnl_pct > 0:
                                sig.signal_type = SignalType.SELL
                                sig.reason = f"İzleyen Stop Kırıldı"
                            elif pnl_pct <= -2.0:
                                sig.signal_type = SignalType.SELL
                                sig.reason = f"Sıkı Zarar Kes Kırıldı"
                            break
                    # -----------------------------------------------
                    
                    # Sadece NET SİNYALLER, GEREKSİZ MESAJ YOK
                    # Alarmın tekrarlamaması için kısa hafıza (Throttle)
                    sig_memory = _GLOBAL_MEMORY.setdefault("last_signals", {})
                    last_sig_time = sig_memory.get(symbol, 0)
                    import time
                    now = time.time()
                    
                    if sig.signal_type == SignalType.BUY and not user_owns_symbol:
                        if not is_market_crashing and not is_global_panic:
                            if now - last_sig_time > 3600: # Aynı hisseye saatte 1 alarm
                                sig_memory[symbol] = now
                                await asyncio.to_thread(send_telegram_message, f"🟢 <b>AL:</b> {symbol}")
                            
                    elif sig.signal_type == SignalType.SELL and user_owns_symbol:
                        if now - last_sig_time > 1800:
                            sig_memory[symbol] = now
                            durum_text = "KAR" if pnl_pct > 0 else "ZARAR"
                            await asyncio.to_thread(send_telegram_message, f"🔴 <b>SAT:</b> {symbol} (Guncel: %{pnl_pct:.2f} {durum_text})")
                            
                await asyncio.sleep(2) # IP Ban koruması
                
            # Tur bitince 60 saniye dinlen
            for _ in range(60):
                if not IS_RUNNING: break
                await asyncio.sleep(1)
                
        except Exception as e:
            log_event("ERROR", f"Market trader loop error: {e}", level="ERROR")
            await asyncio.sleep(5)

from interfaces.telegram_bot import telegram_bot_listener, send_telegram_message
from interfaces.mini_app import start_mini_app_server

# ... skipping down ...
async def main():
    init_db()
    log_event("SYSTEM", "System initialized. Starting background processes.")
    
    # 4 görevi paralel çalıştırır (Nöbetçi, Avcı, Tel Bot, Mini App)
    await asyncio.gather(
        news_and_tv_watcher(),
        market_trader(),
        telegram_bot_listener(),
        start_mini_app_server()
    )

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    
    # Python asyncio motorunu başlat
    asyncio.run(main())
