import asyncio
from core.database import get_portfolio, save_trade, update_portfolio_cash, get_active_trades, remove_trade
from interfaces.telegram_bot import send_telegram_message
from core.utils import log_event

# --------------------------------------------------------
# VIRTUAL BROKER v2.0 (Kurumsal Kasa Yonetimi + Komisyon)
# --------------------------------------------------------

MAX_ACTIVE_TRADES = 3      # Ayni anda en fazla 3 hissede pozisyon
MAX_ALLOCATION_PCT = 0.20  # obsolete, artik volatility allocation var.

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
        existing_trade = next((t for t in active_trades if t[0] == symbol), None)
        
        if not existing_trade and len(active_trades) >= MAX_ACTIVE_TRADES:
            msg = f'Portfoy dolu: {symbol} alimi reddedildi! (Max {MAX_ACTIVE_TRADES} islem)'
            log_event('BROKER', msg, level='WARNING')
            await asyncio.to_thread(send_telegram_message, msg)
            return

        from sensors.advanced_filters import get_stock_sector, get_volatility_allocation
        
        if not existing_trade:
            new_sector = get_stock_sector(symbol)
            for t in active_trades:
                existing_sector = get_stock_sector(t[0])
                if existing_sector != 'Unknown' and existing_sector == new_sector:
                    msg = f"\u26D4 SEKTOR KOTASI REDDI \n\nHisse: {symbol}\nZaten '{existing_sector}' sektorunden hisse tasiyorsun. Riski bolmek adina alim reddedildi."
                    log_event('BROKER', msg, level='WARNING')
                    await asyncio.to_thread(send_telegram_message, msg)
                    return

        if price <= 0:
            log_event('BROKER', f'{symbol} icin gecersiz fiyat: {price}', level='ERROR')
            return

        cash_balance, _ = get_portfolio()
        cash = float(cash_balance)

        volatility_alloc = get_volatility_allocation(symbol)
        target_allocation = 12000 * volatility_alloc
        
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
        update_portfolio_cash(new_cash)

        if existing_trade:
            old_price = float(existing_trade[1])
            old_lots = int(existing_trade[3])
            new_total_lots = old_lots + lot_amount
            new_avg_price = ((old_price * old_lots) + (price * lot_amount)) / new_total_lots
            save_trade(symbol, new_avg_price, new_total_lots)
            action_title = "EK ALIM (MALIYET DUSURME)"
            avg_str = f"\nEski Maliyet: {old_price:.2f} | Yeni Ort. Maliyet: {new_avg_price:.2f}"
        else:
            save_trade(symbol, price, lot_amount)
            action_title = "YENI SANAL ALIM"
            avg_str = ""

        msg = (
            f'\u2705 <b>{action_title}</b>\n\n'
            f'Hisse: {symbol}\n'
            f'Fiyat: {price:.2f} TL\n'
            f'Adet: {lot_amount} Lot\n'
            f'Islem Tutari: {total_cost:.2f} TL (Kasanin %{volatility_alloc*100:.0f})\n'
            f'Komisyon+Kayma (%{dynamic_rate*bool(dynamic_rate)*100:.1f}): {commission_fee:.2f} TL\n'
            f'Kalan Kasa: {new_cash:.2f} TL{avg_str}\n\n'
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
                update_portfolio_cash(new_cash)

                icon = '\u2705' if net_pnl > 0 else '\u26D0'
                msg = (
                    f'{icon} <b>OTOMATIK SATIS</b>\n\n'
                    f'Hisse: {symbol}\n'
                    f'Neden: {reason}\n\n'
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

# ---------------------------------------------------------
# VIRTUAL BROKER v2.2 - VIOP (Aciga Satis / Shorting)
# ---------------------------------------------------------

async def execute_viop_short(symbol: str, price: float, ai_reason: str, ai_confidence: float):
    try:
        from core.database import get_viop_trades, save_viop_trade
        active_shorts = get_viop_trades()
        existing_trade = next((t for t in active_shorts if t[0] == symbol), None)
        
        if not existing_trade and len(active_shorts) >= MAX_ACTIVE_TRADES:
            msg = f'VIOP Portfoy dolu: {symbol} SHORT reddedildi! (Max {MAX_ACTIVE_TRADES})'
            log_event('BROKER_VIOP', msg, level='WARNING')
            await asyncio.to_thread(send_telegram_message, msg)
            return

        cash_balance, _ = get_portfolio()
        cash = float(cash_balance)
        
        from sensors.advanced_filters import get_volatility_allocation
        volatility_alloc = get_volatility_allocation(symbol)
        target_allocation = 12000 * volatility_alloc # Teminat (Margin) kullanimi

        if cash < target_allocation:
            if cash > price * 10:
                target_allocation = cash * 0.90
            else:
                msg = f'Yetersiz Bakiye: {symbol} SHORT icin kasada teminat kalmadi! ({cash:.2f} TL)'
                await asyncio.to_thread(send_telegram_message, msg)
                return

        lot_amount = int(target_allocation // price)
        if lot_amount <= 0: return

        dynamic_rate = get_dynamic_commission(symbol)
        total_value = lot_amount * price
        commission_fee = total_value * dynamic_rate
        
        new_cash = cash - commission_fee # Sadece komisyonu nakitten dusuyoruz, kalani teminat
        update_portfolio_cash(new_cash)
        
        if existing_trade:
            old_price = float(existing_trade[1])
            old_lots = int(existing_trade[2])
            new_total_lots = old_lots + lot_amount
            new_avg_price = ((old_price * old_lots) + (price * lot_amount)) / new_total_lots
            save_viop_trade(symbol, new_avg_price, new_total_lots)
            action_title = "VIOP EK SHORT (MALIYET YUKSELTME)"
            avg_str = f"\nEski Maliyet: {old_price:.2f} | Yeni Ort. Maliyet: {new_avg_price:.2f}"
        else:
            save_viop_trade(symbol, price, lot_amount)
            action_title = "YENI VIOP SHORT (DUSUSE OYNAMA)"
            avg_str = ""

        msg = (
            f'🔻 <b>{action_title}</b>\n\n'
            f'Hisse: {symbol}\n'
            f'Fiyat (Satis): {price:.2f} TL\n'
            f'Adet: {lot_amount} Lot\n'
            f'Pozisyon Buyuklugu: {total_value:.2f} TL (Kasanin %{volatility_alloc*100:.0f})\n'
            f'Komisyon+Kayma (%{dynamic_rate*100:.1f}): {commission_fee:.2f} TL\n'
            f'Kalan Kasa: {new_cash:.2f} TL{avg_str}\n\n'
            f'YZ Onay Skoru: %{ai_confidence}\n'
            f'YZ Notu: {ai_reason}'
        )
        log_event('BROKER_VIOP', f'{symbol} SHORT acildi. Buyukluk: {total_value:.2f} TL')
        await asyncio.to_thread(send_telegram_message, msg)
    except Exception as e:
        log_event('BROKER_VIOP', f'SHORT Hatasi ({symbol}): {e}', level='ERROR')

async def execute_viop_cover(symbol: str, price: float, reason: str):
    try:
        from core.database import get_viop_trades, remove_viop_trade, save_trade
        # Not: save_trade is just to keep logs, wait, trade_history handles standard trades.
        # We will write directly to trade_history via remove_viop_trade mapping if we wanted, 
        # but let's just close the trade and add profit to cash.
        trades = get_viop_trades()
        for t in trades:
            if t[0] == symbol:
                short_price = float(t[1])
                lots = int(t[2])

                dynamic_rate = get_dynamic_commission(symbol)
                
                # SHORT Kâr Hesaplama: (Short_Fiyati - Guncel_Fiyat) * Lot
                gross_pnl = (short_price - price) * lots
                
                total_value_opened = lots * short_price
                total_value_closed = lots * price
                commission_fee = (total_value_opened + total_value_closed) * dynamic_rate / 2 # simplified
                
                net_pnl = gross_pnl - commission_fee
                net_pnl_pct = (net_pnl / total_value_opened) * 100

                remove_viop_trade(symbol)

                cash, _ = get_portfolio()
                new_cash = cash + net_pnl
                update_portfolio_cash(new_cash)
                
                # Log to trade_history manually for analytics
                from core.database import _execute
                from core.utils import get_ist_time_str
                # We save it with inverted prices in trade_history so it shows properly
                q_sq = "INSERT INTO trade_history (symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, sell_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                q_pg = "INSERT INTO trade_history (symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, sell_time) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                _execute(q_sq, q_pg, (f"{symbol} (SHORT)", short_price, price, lots, net_pnl, reason, t[3], get_ist_time_str()))

                icon = '💰' if net_pnl > 0 else '🔴'
                msg = (
                    f'{icon} <b>VIOP SHORT KAPATILDI (COVER)</b>\n\n'
                    f'Hisse: {symbol}\n'
                    f'Neden: {reason}\n'
                    f'Kapatilan Lot: {lots}\n'
                    f'Short Acilis: {short_price:.2f} TL\n'
                    f'Kapanis Fiyati: {price:.2f} TL\n\n'
                    f'Komisyon+Kayma: {commission_fee:.2f} TL\n'
                    f'NET K/Z: {net_pnl:.2f} TL (%{net_pnl_pct:.2f})'
                )
                log_event('BROKER_VIOP', f'{symbol} SHORT kapandi. PNL: {net_pnl:.2f} TL')
                await asyncio.to_thread(send_telegram_message, msg)
                return True

        log_event('BROKER_VIOP', f'{symbol} COVER edilmek istendi ancak acik SHORT pozisyon yok.')
        return False

    except Exception as e:
        log_event('BROKER_VIOP', f'COVER Hatasi ({symbol}): {e}', level='ERROR')
        return False
