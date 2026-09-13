import asyncio
from core.database import get_portfolio, save_trade, update_portfolio_cash, get_active_trades, remove_trade
from interfaces.telegram_bot import send_telegram_message
from core.utils import log_event

# --------------------------------------------------------
# VIRTUAL BROKER v2.0 (Kurumsal Kasa Yonetimi + Komisyon)
# --------------------------------------------------------

MAX_ACTIVE_TRADES = 3      # Ayni anda en fazla 3 hissede pozisyon
MAX_ALLOCATION_PCT = 0.20  # Tek isleme kasanin yuzde 20si

def get_dynamic_commission(symbol: str) -> float:
    try:
        from sensors.fundamental_sensor import get_stock_fundamentals
        funds = get_stock_fundamentals(symbol)
        mcap = funds.get("market_cap", 0)
        
        if mcap > 50_000_000_000:
            return 0.004
        elif mcap > 10_000_000_000:
            return 0.008
        else:
            return 0.015
    except:
        return 0.008

async def execute_virtual_buy(symbol: str, price: float, ai_reason: str, ai_confidence: float):
    try:
        active_trades = get_active_trades()
        if len(active_trades) >= MAX_ACTIVE_TRADES:
            msg = f'Portfoy dolu: {symbol} alimi reddedildi! (Max {MAX_ACTIVE_TRADES} islem)'
            log_event('BROKER', msg, level='WARNING')
            await asyncio.to_thread(send_telegram_message, msg)
            return

        if price <= 0:
            log_event('BROKER', f'{symbol} icin gecersiz fiyat: {price}', level='ERROR')
            return

        cash_balance, _ = get_portfolio()
        cash = float(cash_balance)

        target_allocation = 12000 * MAX_ALLOCATION_PCT

        if cash < target_allocation:
            if cash > price * 10:
                target_allocation = cash * 0.90
            else:
                msg = f'Yetersiz Bakiye: {symbol} alimi icin kasada para kalmadi! ({cash:.2f} TL)'
                log_event('BROKER', msg, level='WARNING')
                await asyncio.to_thread(send_telegram_message, msg)
                return

        lot_amount = int(target_allocation // price)
        if lot_amount <= 0:
            return

        dynamic_rate = get_dynamic_commission(symbol)
        total_cost = lot_amount * price
        commission_fee = total_cost * dynamic_rate
        total_deduction = total_cost + commission_fee

        if cash < total_deduction:
            lot_amount = int(cash // (price * (1 + dynamic_rate)))
            if lot_amount <= 0:
                return
            total_cost = lot_amount * price
            commission_fee = total_cost * dynamic_rate
            total_deduction = total_cost + commission_fee

        new_cash = cash - total_deduction

        save_trade(symbol, price, lot_amount)
        update_portfolio_cash(new_casi)

        msg = (
            '?? <b>SANAL ALIM GERCEKLESTI</b>\n\n'
            f'Hisse: {symbol}\n'
            f'Fiyat: {price:.2f} TL\n'
            f'Adet: {lot_amount} Lot\n'
            f'Islem Tutari: {total_cost:.2f} TL\n'
            f'Komisyon+Kayma (%{dynamic_rate*100:.1}): {commission_fee:.2f} TL\n'
            f'Kalan Kasa: {new_cash:.2f} TL\n\n'
            f'YZ Onay Skoru: %{ai_confidence}\n'
            f'YZ Notu: {ai_reason}'
        )
        log_event('BROKER', f'{symbol} alindi. Maliyet: {total_cost:.2f} TL')
        await asyncio.to_thread(send_telegram_message, msg)

    except Exception as e:
        log_event('BROKER', f'Alim Hatasi ({symbol}): {e}', level='ERROR')

async def execute_virtual_sell(symbol: str, price: float, reason: str):
    try:
        trades = get_active_trades()
        for t in trades:
            if t[0] == symbol:
                buy_price = float(t[1])
                lots = int(t[3])

                dynamic_rate = get_dynamic_commission(symbol)

                total_value = lots * price
                commission_fee = total_value * dynamic_rate
                net_revenue = total_value - commission_fee

                total_cost = (lots * buy_price) * (1 + dynamic_rate)
                net_pnl = net_revenue - total_cost
                net_pnl_pct = (net_pnl / total_cost) * 100

                remove_trade(symbol, price, net_pnl, reason, lots)

                cash, _ = get_portfolio()
                new_cash = cash + net_revenue
                update_portfolio_cash(new_casi)

                icon = '??' if net_pnl > 0 else '??'
                msg = (
                    f'{icon} <b>OTOMATIK SATIS</b0\n\n'
                    f'Hisse: {symbol}\n'
                    f'Neden: {reason}\n'
                    f'Satilan Lot: {lots}\n'
                    f'Alis Fiyati: {buy_price:.2f} TL\n'
                    f'Satis Fiyati: {price:.2f} TL\n\n'
                    f'Net Gelir: {net_revenue:.2f} TL (Komisyon+Kayma: {commission_fee:.2f} TL)\n'
                    f'NET K/Z: {net_pnl:.2f} TL (%{net_pnl_pct:.2f})'
                )
                log_event('BROKER', f'{symbol} satildi. PNL: {net_pnl:.2f} TL')
                await asyncio.to_thread(send_telegram_message, msg)
                return True

        log_event('BROKER', f'{symbol} satilmak istendi ancak acik pozisyon yok.')
        return False

    except Exception as e:
        log_event('BROKER', f'Satis Hatasi ({symbol}): {e}', level='ERROR')
        return False
