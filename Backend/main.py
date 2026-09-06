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
    "AKBNK", "ALARK", "ASELS", "ASTOR", "BIMAS", "BRSAN", "CWISE", "DOAS", "EKGYO", "ENKAI", 
    "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", "ISCTR", "KCHOL", "KONTR", "KOZAA", "KOZAL", 
    "KRDMD", "ODAS", "OYAKC", "PETKM", "PGSUS", "SAHOL", "SASA", "SISE", "TCELL", "THYAO", 
    "TOASO", "TUPRS", "YKBNK"
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
            
            log_event("LOOP", f"New trading cycle started. Cash: {portfolio.cash_balance:.2f} TRY, Active trades: {len(active_symbols)}")
            
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
                live_price_raw = tv_data.get("close", 0)
                if live_price_raw and live_price_raw > 0:
                    current_price = Decimal(str(live_price_raw))
                    
                    if sig.signal_type == SignalType.BUY and symbol not in active_symbols:
                        trade = execute_virtual_order(sig, portfolio, current_price, active_symbols)
                        if trade:
                            save_trade(trade.symbol, trade.buy_price, trade.lot_amount)
                            update_portfolio_cash(portfolio.cash_balance)
                            active_symbols.append(trade.symbol)
                            await asyncio.to_thread(send_telegram_message, f"🟢 <b>ALIM YAPILDI:</b> {trade.symbol}\nFiyat: {trade.buy_price:.2f} TL\nLot: {trade.lot_amount}")
                            
                    elif sig.signal_type == SignalType.SELL and symbol in active_symbols:
                        full_trades = get_active_trades()
                        sell_result = execute_virtual_sell(sig, portfolio, current_price, full_trades)
                        if sell_result:
                            remove_trade(symbol)
                            update_portfolio_cash(portfolio.cash_balance)
                            active_symbols.remove(symbol)
                            durum = "KAR" if sell_result['pnl'] > 0 else "ZARAR"
                            await asyncio.to_thread(send_telegram_message, f"🔴 <b>SATIS YAPILDI:</b> {symbol}\nSonuc: {sell_result['pnl']:.2f} TL {durum}")
                            
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
