import asyncio
from datetime import datetime, date, timedelta
from core.database import db_lock, get_connection
from core.utils import log_event


def get_daily_analytics():
    today = date.today().strftime('%Y-%m-%d')
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(trade_history)')
        cols = [info[1] for info in cursor.fetchall()]
        if 'duration_minutes' not in cols:
            cursor.execute('ALTER TABLE trade_history ADD COLUMN duration_minutes REAL DEFAULT 0')
            conn.commit()
        cursor.execute(
            'SELECT symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, sell_time FROM trade_history WHERE sell_time LIKE ? ORDER BY sell_time DESC',
            (today + '%',))
        rows = cursor.fetchall()
        conn.close()

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
    a = get_daily_analytics()
    if a is None:
        msg = 'Bugun huc islem gercekkesmedi. Piyasa izleniyor...'
        await asyncio.to_thread(send_telegram_message, msg)
        return
    wr = a['win_rate']
    we = 'u?' if wr >= 60 else ('u?' if wr >= 40 else 'u?')
    pe = 'u?' if a['total_pnl'] >= 0 else 'u?'
    lines = [
        'u? Gunluk Performans Raporu',
        '---------------',
        f"{we} Kazanilan: {a['winning']} | Kaybedilen: {a['losing']}",
        f"u? Basari Orani: %{wr:.1f}",
        f"{pe} Net Kar/Zarar: {a['total_pnl']:+.2f} TL",
        f"u? Ort. Tutma:  {a['avg_dur']:.1f} dakika",
        f"u? En Iyi: {a['best']['symbol']} ({a['best']['pnl']:+2f} TL)",
        f"u? En Kotu: {a['worst']['symbol']} ({a['worst']['pnl']:+2f} TL)",
        'u? BorsaAI v2.1 - Otomatik Rapor'
    ]
    msg = '\n'.join(lines)
    await asyncio.to_thread(send_telegram_message, msg)
    log_event('ANALYTICS', f"Rapor gonderildi. PnL: {a['total_pnl']:.2f}")


async def run_analytics_scheduler():
    log_event('ANALYTICS', 'Zamanlayici baslatildi.')
    while True:
        now = datetime.now()
        target = now.replace(hour=18, minute=0, second=0, microsecond=0)
        if now >= target:
            target = target + timedelta(days=1)
        wait = (target - now).total_seconds()
        log_event('ANALYTICS', f'Sonraki rapor bekleniliyor: ')
        await asyncio.sleep(wait)
        await send_daily_report()
