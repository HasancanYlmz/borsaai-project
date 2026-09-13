import asyncio
import yfinance as yf
from core.database import get_active_trades, update_trade_lots_and_highest
from simulator.virtual_broker import execute_virtual_sell
from core.utils import log_event

# ---------------------------------------------------------
# RISK MANAGER v2.2 (Bagimsiz Guvenlik Bekcisi)
# ---------------------------------------------------------

HARD_STOP_LOSS = -2.0    # Acil Durum Zarar Kes (-%2.5)
TRAIL_TRIGGER = 3.0      # Izleyen stop'un devreye girecegi kar (+%3)
TRAIL_BUFFER = 1.4       # Zirveden geri cekilme tahammulu (-%2)


async def run_risk_manager():
    log_event("RISK_MANAGER", "Bagimsiz Risk Yoneticisi baslatildi.")
    
    while True:
        try:
            trades = get_active_trades()
            if not trades:
                await asyncio.sleep(120)
                continue
                
            for t in trades:
                symbol = t[0]
                buy_price = float(t[1])
                highest_seen = float(t[5])
                
                clean_symbol = symbol.replace('BIST:', '') + '.IS'
                ticker = yf.Ticker(clean_symbol)
                info = await asyncio.to_thread(lambda: ticker.fast_info)
                current_price = info.get('lastPrice', 0.0)
                
                if current_price <= 0:
                    continue
                    
                pnl_pct = ((current_price - buy_price) / buy_price) * 100
                
                if current_price > highest_seen:
                    highest_seen = current_price
                    update_trade_lots_and_highest(symbol, int(t[3]), highest_seen)
                    
                drawdown_from_peak = ((current_price - highest_seen) / highest_seen) * 100
                
                sell_reason = ""
                
                if pnl_pct <= HARD_STOP_LOSS:
                    sell_reason = f"Acil Zarar Kes (Hard SL %{HARD_STOP_LOSS})"
                    
                elif highest_seen >= buy_price * (1 + (TRAIL_TRIGGER / 100)):
                    if drawdown_from_peak <= -TRAIL_BUFFER:
                        sell_reason = f"Izleyen Stop (Zirveden %}TRAIL_BUFFER} dusus)"
                
                if sell_reason:
                    log_event("RISK_MANAGER", f"{symbol} icin koruma kalkani devrede: {sell_reason}")
                    await execute_virtual_sell(symbol, current_price, sell_reason)
                    
            await asyncio.sleep(120)
            
        except Exception as e:
            log_event("RISK_MANAGER", f"Hata: {str(e)}", level="ERROR")
            await asyncio.sleep(60)
