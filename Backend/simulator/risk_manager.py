import asyncio
import yfinance as yf
from core.database import get_active_trades, remove_trade, update_portfolio_cash, get_portfolio, update_trade_lots_and_highest, log_partial_sale
from interfaces.telegram_bot import send_telegram_message
from core.utils import log_event

# ---------------------------------------------------------
# RISK MANAGER (2-Minute Loop for SL, TP, Trailing)
# ---------------------------------------------------------

HARD_STOP_LOSS = -1.5   # Zarar Kes %1.5
TAKE_PROFIT_HALF = 4.0  # Kar Al (Ilk Yari) %4.0
TRAIL_TRIGGER = 5.0     # Izleyen Stop tetiklenme
TRAIL_BUFFER = 2.5      # Zirveden %2.5 geri cekilirse sat

async def run_risk_manager(is_running_flag):
    """
    Arka planda 2 dakikada bir acik pozisyonlarin canli fiyatina bakar.
    """
    log_event("RISK_MANAGER", "Risk Yoneticisi (2 Dakikalik Dongu) basladi.")
    while is_running_flag():
        try:
            trades = get_active_trades() # symbol, buy_price, lot_amount, remaining_lots, buy_time, highest_seen
            if not trades:
                await asyncio.sleep(120)
                continue
                
            for t in trades:
                if not is_running_flag(): break
                symbol = t[0]
                buy_price = float(t[1])
                original_lots = int(t[2])
                remaining_lots = int(t[3])
                buy_time = t[4]
                highest_seen = float(t[5])
                
                # Fetch live price
                clean_symbol = symbol.replace('BIST:', '') + '.IS'
                ticker = yf.Ticker(clean_symbol)
                info = await asyncio.to_thread(lambda: ticker.fast_info)
                current_price = info.get('lastPrice', 0.0)
                
                if current_price <= 0:
                    continue
                    
                # Guncel kar/zarar yuzdesi (Ilk maliyete gore)
                pnl_pct = ((current_price - buy_price) / buy_price) * 100
                
                # En yuksek gorulen fiyati guncelle
                if current_price > highest_seen:
                    highest_seen = current_price
                    update_trade_lots_and_highest(symbol, remaining_lots, highest_seen)
                    
                # Zirveden ne kadar dusmus?
                drawdown_from_peak = ((current_price - highest_seen) / highest_seen) * 100
                
                sell_reason = ""
                lots_to_sell = 0
                
                # 1. KURAL: HARD STOP LOSS (-1.5%)
                if pnl_pct <= HARD_STOP_LOSS:
                    sell_reason = "Siki Zarar Kes (Hard SL)"
                    lots_to_sell = remaining_lots
                    
                # 2. KURAL: KADEMELI KAR AL (+4% olunca lotlarin yarisini sat)
                elif pnl_pct >= TAKE_PROFIT_HALF and remaining_lots == original_lots and original_lots > 1:
                    sell_reason = "Kademeli Kar Al (%4 Hedefi)"
                    lots_to_sell = original_lots // 2
                    
                # 3. KURAL: IZLEYEN STOP (En yuksek fiyattan %2.5 duserse)
                elif highest_seen >= buy_price * (1 + (TRAIL_TRIGGER / 100)):
                    # Eger zirve %5 ustune cikmissa izleyen stop aktiflesmistir.
                    if drawdown_from_peak <= -TRAIL_BUFFER:
                        sell_reason = "Izleyen Stop Kestirmesi (Trailing SL)"
                        lots_to_sell = remaining_lots
                
                # SATIS ISLEMI
                if lots_to_sell > 0:
                    total_revenue = lots_to_sell * current_price
                    pnl_amount = (current_price - buy_price) * lots_to_sell
                    
                    cash_balance, _ = get_portfolio()
                    new_cash = float(cash_balance) + total_revenue
                    update_portfolio_cash(new_cash)
                    
                    if lots_to_sell == remaining_lots:
                        # Hepsini sat ve kapat
                        remove_trade(symbol, current_price, pnl_amount, sell_reason, lots_to_sell)
                    else:
                        # Yarisini sat, kalani tut
                        remaining_lots -= lots_to_sell
                        update_trade_lots_and_highest(symbol, remaining_lots, highest_seen)
                        log_partial_sale(symbol, buy_price, current_price, lots_to_sell, pnl_amount, sell_reason, buy_time)
                        
                    durum_ikon = "🔴" if pnl_amount < 0 else "🤑"
                    msg = f"""{durum_ikon} <b>SANAL SATIS GERCEKLESTI</b> {durum_ikon}

📌 <b>Hisse:</b> {symbol}
🔔 <b>Neden:</b> {sell_reason}
🎯 <b>Alis:</b> {buy_price:.2f} | <b>Satis:</b> {current_price:.2f}
📉 <b>Kar/Zarar Yuzdesi:</b> %{pnl_pct:.2f}
💰 <b>Net K/Z:</b> {pnl_amount:.2f} TL
🛒 <b>Satilan Lot:</b> {lots_to_sell}
💼 <b>Kalan Kasa:</b> {new_cash:.2f} TL"""
                    
                    log_event("RISK_MANAGER", f"{symbol} satildi: {sell_reason}")
                    await asyncio.to_thread(send_telegram_message, msg)
                    
            await asyncio.sleep(120) # 2 DK UYU
            
        except Exception as e:
            log_event("RISK_MANAGER", f"Dongu Hatasi: {str(e)}", level="ERROR")
            await asyncio.sleep(60)
