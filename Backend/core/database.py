import os
import threading
from datetime import datetime
from typing import List, Tuple
from decimal import Decimal
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import get_ist_time_str

LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), 'borsa_memory.db')
DATABASE_URL = os.getenv("DATABASE_URL")
db_lock = threading.Lock()

_IS_POSTGRES = bool(DATABASE_URL)

if _IS_POSTGRES:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3

def get_connection():
    if _IS_POSTGRES:
        return psycopg2.connect(DATABASE_URL + '?sslmode=prefer')
    else:
        return sqlite3.connect(LOCAL_DB_PATH, check_same_thread=False)

def _execute(query_sqlite, query_pg, params=(), fetch=None):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        result = None
        try:
            if _IS_POSTGRES:
                cursor.execute(query_pg, params)
            else:
                cursor.execute(query_sqlite, params)
                
            if fetch == 'all':
                result = cursor.fetchall()
            elif fetch == 'one':
                result = cursor.fetchone()
            else:
                conn.commit()
        finally:
            conn.close()
        return result

def init_db():
    q1_sq = '''CREATE TABLE IF NOT EXISTS signals_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, symbol TEXT, signal_type TEXT,
        regime TEXT, confidence_score REAL, reason TEXT)'''
    q1_pg = '''CREATE TABLE IF NOT EXISTS signals_history (
        id SERIAL PRIMARY KEY,
        timestamp TEXT, symbol TEXT, signal_type TEXT,
        regime TEXT, confidence_score REAL, reason TEXT)'''
    _execute(q1_sq, q1_pg)
    
    q2_sq = '''CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        cash_balance REAL, total_equity REAL)'''
    q2_pg = '''CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        cash_balance REAL, total_equity REAL)'''
    _execute(q2_sq, q2_pg)

    q3_sq = '''CREATE TABLE IF NOT EXISTS active_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT UNIQUE, buy_price REAL,
        lot_amount INTEGER, remaining_lots INTEGER, buy_time TEXT, highest_seen REAL)'''
    q3_pg = '''CREATE TABLE IF NOT EXISTS active_trades (
        id SERIAL PRIMARY KEY,
        symbol TEXT UNIQUE, buy_price REAL,
        lot_amount INTEGER, remaining_lots INTEGER, buy_time TEXT, highest_seen REAL)'''
    _execute(q3_sq, q3_pg)

    q4_sq = '''CREATE TABLE IF NOT EXISTS trade_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT, buy_price REAL, sell_price REAL,
        lot_amount INTEGER, pnl REAL, reason TEXT,
        buy_time TEXT, sell_time TEXT, duration_minutes REAL)'''
    q4_pg = '''CREATE TABLE IF NOT EXISTS trade_history (
        id OID OR SERIAL,  -- we don't care, use SERIAL
        id SERIAL PRIMARY KEY,
        symbol TEXT, buy_price REAL, sell_price REAL,
        lot_amount INTEGER, pnl REAL, reason TEXT,
        buy_time TEXT, sell_time TEXT, duration_minutes REAL)'''
    _execute(q4_sq, q4_pg)

    c5 = _execute('SELECT COUNT(*) FROM portfolio', 'SELECT COUNT(*) FROM portfolio', fetch='one')
    if c5[0] == 0:
        _execute('INSERT INTO portfolio (id, cash_balance, total_equity) VALUES (1, 12000.0, 12000.0)',
                 'INSERT INTO portfolio (id, cash_balance, total_equity) VALUES (1, 12000.0, 12000.0)')

    c6 = _execute('SELECT COUNT(*) FROM active_trades', 'SELECT COUNT(*) FROM active_trades', fetch='one')
    if c6[0] == 0:
        _execute('UPDATE portfolio SET cash_balance = 12000.0, total_equity = 12000.0',
                 'UPDATE portfolio SET cash_balance = 12000.0, total_equity = 12000.0')

    _execute('DELETE FROM active_trades WHERE remaining_lots <= 0', 'DELETE FROM active_trades WHERE remaining_lots <= 0')

def save_signal(symbol: str, signal_type: str, regime: str, confidence: float, reason: str):
    q_sq = 'INSERT INTO signals_history (timestamp, symbol, signal_type, regime, confidence_score, reason) VALUES (?, ?, ?, ?, ?, ?)'
    q_pg = 'INSERT INTO signals_history (timestamp, symbol, signal_type, regime, confidence_score, reason) VALUES (%s, %s, %s, %s, %s, %s)'
    _execute(q_sq, q_pg, (get_ist_time_str(), symbol, signal_type, regime, confidence, reason))

def get_recent_signals(imit: int = 50) -> List[Tuple]:
    q_sq = 'SELECT timestamp, symbol, signal_type, regime, confidence_score, reason FROM signals_history ORDER BY id DESC LIMIT ?'
    q_pg = 'SELECT timestamp, symbol, signal_type, regime, confidence_score, reason FROM signals_history ORDER BY id DESC LIMIT %s'
    return _execute(q_sq, q_pg, (imit,), fetch='all')

def save_trade(symbol: str, buy_price: Decimal, lot_amount: int):
    q_sq = 'INSERT OR REPLACE INTO active_trades (symbol, buy_price, lot_amount, remaining_lots, buy_time, highest_seen) VALUES (?, ?, ?, ?, ?, ?)'
    q_pg = '''INSERT INTO active_trades (symbol, buy_price, lot_amount, remaining_lots, buy_time, highest_seen) VALUES (%s, %s, %s, %s, %s, %s)
             ON CONFLICT (symbol) DO UPDATE SET 
             buy_price = EXCLUDED.buy_price,
             lot_amount = EXCLUDED.lot_amount,
             remaining_lots = EXCLUDED.remaining_lots,
             buy_time = EXCLUDED.buy_time,
             highest_seen = EXCLUDED.highest_seen'''
    _execute(q_sq, q_pg, (symbol, float(buy_price), lot_amount, lot_amount, get_ist_time_str(), float(buy_price)))

def update_trade_lots_and_highest(symbol: str, remaining_lots: int, highest_seen: float):
    q_sq = 'UPDATE active_trades SET remaining_lots = ?, highest_seen = ? WHERE symbol = ?'
    q_pg = 'UPDATE active_trades SET remaining_lots = %s, highest_seen = %s WHERE symbol = %s'
    _execute(q_sq, q_pg, (remaining_lots, highest_seen, symbol))

def get_active_trades() -> List[Tuple]:
    return _execute('SELECT symbol, buy_price, lot_amount, remaining_lots, buy_time, highest_seen FROM active_trades', 'SELECT symbol, buy_price, lot_amount, remaining_lots, buy_time, highest_seen FROM active_trades', fetch='all')

def remove_trade(symbol: str, sell_price: float = 0.0, pnl: float = 0.0, reason: str = "", lots_sold: int = 0):
    row = _execute('SELECT buy_price, buy_time FROM active_trades WHERE symbol = ?', 'SELECT buy_price, buy_time FROM active_trades WHERE symbol = %s', (symbol,), fetch='one')
    if row:
        buy_price, buy_time = row
        q_sq = 'INSERT INTO trade_history (symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, sell_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
        q_pg = 'INSERT INTO trade_history (symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, sell_time) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'
        _execute(q_sq, q_pg, (symbol, buy_price, sell_price, lots_sold, pnl, reason, buy_time, get_ist_time_str()))
    _execute('DELETE FROM active_trades WHERE symbol = ?', 'DELETE FROM active_trades WHERE symbol = %s', (symbol,))

def log_partial_sale(symbol: str, buy_price: float, sell_price: float, lots_sold: int, pnl: float, reason: str, buy_time: str):
    q_sq = 'INSERT INTO trade_history (symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, sell_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    q_pg = 'INSERT INTO trade_history (symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, sell_time) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'
    _execute(q_sq, q_pg, (symbol, buy_price, sell_price, lots_sold, pnl, reason, buy_time, get_ist_time_str()))

def update_portfolio_cash(new_cash: Decimal):
    _execute('UPDATE portfolio SET cash_balance = ? WHERE id = 1', 'UPDATE portfolio SET cash_balance = %s WHERE id = 1', (float(new_cash),))

def get_portfolio() -> Tuple:
    return _execute('SELECT cash_balance, total_equity FROM portfolio WHERE id = 1', 'SELECT cash_balance, total_equity FROM portfolio WHERE id = 1', fetch='one')

init_db()

def get_daily_trades(today: str):
    q_sq = 'SELECT symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, sell_time FROM trade_history WHERE sell_time LIKE ? ORDER BY sell_time DESC'
    q_pg = 'SELECT symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, sell_time FROM trade_history WHERE sell_time LIKE %s ORDER BY sell_time DESC'
    return _execute(q_sq, q_pg, (today + '%',), fetch='all')

def init_viop_db():
    q_sq = 'CREATE TABLE IF NOT EXISTS viop_trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT UNIQUE, short_price REAL, lot_amount INTEGER, short_time TEXT, lowest_seen REAL)'
    q_pg = 'CREATE TABLE IF NOT EXISTS viop_trades (id SERIAL PRIMARY KEY, symbol TEXT UNIQUE, short_price REAL, lot_amount INTEGER, short_time TEXT, lowest_seen REAL)'
    _execute(q_sq, q_pg)

def save_viop_trade(symbol: str, short_price: float, lot_amount: int):
    q_sq = 'INSERT OR REPLACE INTO viop_trades (symbol, short_price, lot_amount, short_time, lowest_seen) VALUES (?, ?, ?, ?, ?)'
    q_pg = """INSERT INTO viop_trades (symbol, short_price, lot_amount, short_time, lowest_seen) VALUES (%s, %s, %s, %s, %s)
              ON CONFLICT (symbol) DO UPDATE SET 
              short_price = EXCLUDED.short_price,
              lot_amount = EXCLUDED.lot_amount,
              short_time = EXCLUDED.short_time,
              lowest_seen = EXCLUDED.lowest_seen"""
    from core.utils import get_ist_time_str
    _execute(q_sq, q_pg, (symbol, float(short_price), int(lot_amount), get_ist_time_str(), float(short_price)))

def get_viop_trades():
    return _execute('SELECT symbol, short_price, lot_amount, short_time, lowest_seen FROM viop_trades', 'SELECT symbol, short_price, lot_amount, short_time, lowest_seen FROM viop_trades', fetch='all')

def remove_viop_trade(symbol: str):
    _execute('DELETE FROM viop_trades WHERE symbol = ?', 'DELETE FROM viop_trades WHERE symbol = %s', (symbol,))

init_viop_db()
