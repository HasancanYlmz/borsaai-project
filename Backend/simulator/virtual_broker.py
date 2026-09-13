import asyncio
from core.database import get_portfolio, save_trade, update_portfolio_cash, get_active_trades, remove_trade
from interfaces.telegram_bot import send_telegram_message
from core.utils import log_event

# ---------------------------------------------------------
# VIRTUAL BROKER (Kurumsal Kasa Yonetimi + Komisyon)
# ---------------------------------------------------------

MAX_ACTIVE_TRADES = 3     # Ayni anda en fazla 3 hissede pozisyon
MAX_ALLOCATION_PCT = 0.20 # Tek isleme kasanin %20'si (2400 TL)
COMMISSION_RATE = 0.0045  # %0.45 (Binde 2.5 Komisyon + Binde 2.0 Sığ Tahta Kayması/Slippage)

async def execute_virtual_buy(symbol: str, price: float, ai_reason: str, ai_confidence: float):
    try:
        if price <= 0:
            log_event("BROKER", f"{symbol} icin gecersiz fiyat: {price}", level="ERROR")
            return
            
        cash_balance, _ = get_portfolio()
        cash = float(cash_balance)
        
        target_allocation = 12000 * MAX_ACTIVE_TRADES = 3     # Ayni anda en fazla 3 hissede pozisyon
MAX_ALLOCATION_PCT
        
        if cash < target_allocation:
            if cash > price * 10: 
                target_allocation = cash * 0.90
            else:
                msg = f"📉 Yetersiz Bakiye: {symbol} alimi icin kasada para kalmadi! ({cash:.2f} TL)"
                log_event("BROKER", msg, level="WARNING")
                await asyncio.to_thread(send_telegram_message, msg)
                return
                
        # Lot hesabi
        lot_amount = int(target_allocation // price)
        if lot_amount <= 0:
            return
            
        total_cost = lot_amount * price
        commission_fee = total_cost * COMMISSION_RATE
        total_deduction = total_cost + commission_fee
        
        if cash < total_deduction:
             lot_amount = int(cash // (price * (1 + COMMISSION_RATE)))
             if lot_amount <= 0: return
             total_cost = lot_amount * price
             commission_fee = total_cost * COMMISSION_RATE
             total_deduction = total_cost + commission_fee

        new_cash = cash - total_deduction
        
        # Veritabanina isliyoruz
        save_trade(symbol, price, lot_amount)
        update_portfolio_cash(new_cash)
        
        msg = f"""🟢 <b>SANAL ALIM GERCEKLESTI</b> 🟢

🏢 <b>Hisse:</b> {symbol}
💰 <b>Fiyat:</b> {price:.2f} ₺
📦 <b>Adet (Lot):</b> {lot_amount} Lot
💳 <b>İşlem Tutarı:</b> {total_cost:.2f} ₺
💸 <b>Slippage+Komisyon:</b> {commission_fee:.2f} ₺
💼 <b>Kalan Kasa:</b> {new_cash:.2f} ₺

🤖 <b>YZ Onay Skoru:</b> %{ai_confidence}
📝 <b>YZ Notu:</b> <i>{ai_reason}</i>"""

        log_event("BROKER", f"{symbol} alindi. Maliyet: {total_cost:.2f} ₺")
        await asyncio.to_thread(send_telegram_message, msg)
        
    except Exception as e:
        log_event("BROKER", f"Alim Hatasi ({symbol}): {e}", level="ERROR")

async def execute_virtual_sell(symbol: str, price: float, reason: str):
    try:
        trades = get_active_trades()
        for t in trades:
            if t[0] == symbol:
                buy_price = float(t[1])
                lots = int(t[3])
                
                # Satis degeri ve komisyon
                total_value = lots * price
                commission_fee = total_value * COMMISSION_RATE
                net_revenue = total_value - commission_fee
                
                # Toplam maliyet (alirken de komisyon odenmisti)
                total_cost = (lots * buy_price) * (1 + COMMISSION_RATE)
                
                net_pnl = net_revenue - total_cost
                net_pnl_pct = (net_pnl / total_cost) * 100
                
                remove_trade(symbol, price, net_pnl, reason, lots)
                
                cash, _ = get_portfolio()
                new_cash = cash + net_revenue
                update_portfolio_cash(new_cash)
                
                icon = "🔥" if net_pnl > 0 else "🛑"
                
                msg = f"""{icon} <b>OTOMATİK SATIŞ GERÇEKLEŞTİ</b> {icon}

🏢 <b>Hisse:</b> {symbol}
📉 <b>Neden:</b> {reason}
📦 <b>Satılan Lot:</b> {lots}
🎯 <b>Alış Fiyatı:</b> {buy_price:.2f} ₺
💸 <b>Satış Fiyatı:</b> {price:.2f} ₺

💳 <b>Net Gelir:</b> {net_revenue:.2f} ₺ (Komisyon: {commission_fee:.2f} ₺)
💰 <b>NET K/Z:</b> {net_pnl:.2f} ₺ (%{net_pnl_pct:.2f})"""

                log_event("BROKER", f"{symbol} satildi. PNL: {net_pnl:.2f} ₺")
                await asyncio.to_thread(send_telegram_message, msg)
                return True
                
        log_event("BROKER", f"{symbol} satilmak istendi ancak acik pozisyon yok.")
        return False
    except Exception as e:
        log_event("BROKER", f"Satis Hatasi ({symbol}): {e}", level="ERROR")
        return False
