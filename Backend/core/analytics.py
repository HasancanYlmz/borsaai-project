import asyncio
from datetime import datetime, date, timedelta
from core.database import db_lock, get_connection
from core.utils import log_event


def get_daily_analytics():
    today = date.today().strftime('%Y-%m-%d')
    from core.database import get_daily_trades
    rows = get_daily_trades(today)

    if not rows:
        return None

    total_pnl = sum(r[4] for r in rows)
    winning = [r for r in rows if r[4] > 0]
    losing = [r for r in rows if r[4] <= 0]
    best = max(rows, key=lambda r: r[4])
    worst = min(rows, key=lambda r: r[4])
    durations = []
    for r in rows:
        try:
            buy_dt = datetime.strptime(r[6][:19], '%Y-%m-%d %H:%M:%S')
            sell_dt = datetime.strptime(r[7][:19], '%Y-%m-%d %H:%M:%S')
            durations.append((sell_dt - buy_dt).seconds / 60)
        except Exception:
            pass
    avg_dur = sum(durations) / len(durations) if durations else 0
    return {
        'total_trades': len(rows),
        'winning': len(winning),
        'losing': len(losing),
        'win_rate': (len(winning) / len(rows)) * 100,
        'total_pnl': total_pnl,
        'best': {'symbol': best[0], 'pnl': best[4]},
        'worst': {'symbol': worst[0], 'pnl': worst[4]},
        'avg_dur': avg_dur,
    }


async def send_daily_report():
    from interfaces.telegram_bot import send_telegram_message
    from core.database import get_portfolio, get_active_trades
    import yfinance as yf
    import pandas as pd

    a = get_daily_analytics()
    
    port = get_portfolio()
    cash = port[0] if port else 12000.0
    active_trades = get_active_trades()
    
    total_stock_value = 0.0
    open_positions_text = ""
    
    if active_trades:
        open_positions_text += "📂 <b>AÇIK POZİSYONLAR (Bekleyen):</b>\n"
        
        tickers = [f"{t[0].replace('BIST:', '')}.IS" for t in active_trades]
        try:
            df = yf.download(tickers, period="1d", progress=False)
            if len(tickers) == 1:
                prices = {active_trades[0][0]: float(df['Close'].iloc[-1]) if not df.empty else float(active_trades[0][1])}
            else:
                prices = {}
                for t in active_trades:
                    sym = t[0]
                    clean_sym = f"{sym.replace('BIST:', '')}.IS"
                    try:
                        prices[sym] = float(df['Close'][clean_sym].iloc[-1])
                    except:
                        prices[sym] = float(t[1])
        except Exception:
            prices = {t[0]: float(t[1]) for t in active_trades}
            
        for t in active_trades:
            sym = t[0]
            buy_price = float(t[1])
            lots = int(t[3])
            curr_price = prices.get(sym, buy_price)
            
            pnl = (curr_price - buy_price) * lots
            pnl_pct = ((curr_price - buy_price) / buy_price) * 100
            
            total_stock_value += (curr_price * lots)
            
            icon = "🟢" if pnl >= 0 else "🔴"
            sign = "+" if pnl >= 0 else ""
            open_positions_text += f"🔹 {sym}: {buy_price:.2f} ➡️ {curr_price:.2f} ({sign}%{pnl_pct:.2f}) | {icon} {sign}{pnl:.2f} TL\n"
    else:
        open_positions_text += "📂 <b>AÇIK POZİSYONLAR:</b>\nAcik pozisyon yok. Tamamen nakitteyiz.\n"
        
    total_wealth = cash + total_stock_value
    daily_diff = total_wealth - 12000.0
    wealth_sign = "+" if daily_diff >= 0 else ""
    
    msg = f"📊 <b>GÜN SONU PORTFÖY RAPORU</b>\n\n"
    msg += f"💰 <b>KASA DURUMU:</b>\n"
    msg += f"Nakit: {cash:.2f} TL\n"
    msg += f"Hisseler: {total_stock_value:.2f} TL\n"
    msg += f"Toplam Varlik: {total_wealth:.2f} TL (Basi: {wealth_sign}{daily_diff:.2f} TL)\n\n"
    
    msg += open_positions_text + "\n"
    
    msg += "📉 <b>KAPANAN İŞLEMLER (Bugün):</b>\n"
    if a is None:
        msg += "Bugun satisi tamamlanan hisse olmadi."
    else:
        wr = a['win_rate']
        we = '🟢' if wr >= 60 else ('🟡' if wr >= 40 else '🔴')
        pe = '🟢' if a['total_pnl'] >= 0 else '🔴'
        
        msg += f"{we} Kazanilan: {a['winning']} | Kaybedilen: {a['losing']}\n"
        msg += f"🎯 Basari Orani: %{wr:.1f}\n"
        msg += f"{pe} Net Kar/Zarar: {a['total_pnl']:+.2f} TL\n"
        msg += f"⏱ Ort. Tutma: {a['avg_dur']:.1f} dakika\n"
        msg += f"🏆 En Iyi: {a['best']['symbol']} ({a['best']['pnl']:+.2f} TL)\n"
        msg += f"💔 En Kotu: {a['worst']['symbol']} ({a['worst']['pnl']:+.2f} TL)\n"
        
    await asyncio.to_thread(send_telegram_message, msg)

async def run_analytics_scheduler():
    from core.utils import get_ist_time
    log_event('ANALYTICS', 'Zamanlayici baslatildi.')
    while True:
        now = get_ist_time()
        target = now.replace(hour=19, minute=0, second=0, microsecond=0)
        if now >= target:
            target = target + timedelta(days=1)
        wait = (target - now).total_seconds()
        log_event('ANALYTICS', f'Sonraki rapor 19:00 (saniye: {wait}) bekleniliyor...')
        await asyncio.sleep(wait)
        await send_daily_report()
