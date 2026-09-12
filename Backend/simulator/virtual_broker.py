import asyncio
from core.database import get_portfolio, save_trade, update_portfolio_cash
from interfaces.telegram_bot import send_telegram_message
from core.utils import log_event

# ---------------------------------------------------------
# VIRTUAL BROKER (Kurumsal Kasa Yonetimi)
# ---------------------------------------------------------

MAX_ALLOCATION_PCT = 0.20 # Tek isleme kasanin %20'si (2400 TL)

async def execute_virtual_buy(symbol: str, price: float, ai_reason: str, ai_confidence: float):
    """
    Satin alma islemini yonetir, lot sayisini hesaplar.
    """
    try:
        if price <= 0:
            log_event("BROKER", f"{symbol} icin gecersiz fiyat: {price}", level="ERROR")
            return
            
        cash_balance, _ = get_portfolio()
        cash = float(cash_balance)
        
        # 12.000 TL total varsayiyoruz (VEYA kasada ne kadar varsa). 
        # Kurumsal mantik: Kasamizin %20'si ile isleme girelim.
        # Sabit 2400 TL civari (Kasa buyudukce artar)
        target_allocation = 12000 * MAX_ALLOCATION_PCT
        
        # Eger kasmada yeterli para yoksa:
        if cash < target_allocation:
            # Kasadaki paranin %90'ini kullan (Geriye cok az kalmissa)
            if cash > price * 10: # En az 10 lot alinabiliyorsa
                target_allocation = cash * 0.90
            else:
                msg = f"❌ Yetersiz Bakiye: {symbol} alimi icin kasada para kalmadi! ({cash:.2f} TL)"
                log_event("BROKER", msg, level="WARNING")
                await asyncio.to_thread(send_telegram_message, msg)
                return
                
        # Lot hesabi
        lot_amount = int(target_allocation // price)
        if lot_amount <= 0:
            return
            
        total_cost = lot_amount * price
        new_cash = cash - total_cost
        
        # Veritabanina isliyoruz (remaining_lots = lot_amount baslangicta)
        save_trade(symbol, price, lot_amount)
        update_portfolio_cash(new_cash)
        
        msg = f"""🟢 <b>SANAL ALIM GERCEKLESTI</b> 🟢

📌 <b>Hisse:</b> {symbol}
💰 <b>Fiyat:</b> {price:.2f} TL
🛒 <b>Adet (Lot):</b> {lot_amount} Lot
💵 <b>Toplam Maliyet:</b> {total_cost:.2f} TL
💼 <b>Kalan Kasa:</b> {new_cash:.2f} TL

🤖 <b>YZ Onay Skoru:</b> %{ai_confidence}
📝 <b>YZ Notu:</b> <i>{ai_reason}</i>"""

        log_event("BROKER", f"{symbol} alindi. Maliyet: {total_cost:.2f} TL")
        await asyncio.to_thread(send_telegram_message, msg)
        
    except Exception as e:
        log_event("BROKER", f"Alim Hatasi ({symbol}): {e}", level="ERROR")
