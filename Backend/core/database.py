import sqlite3
import os
import threading
from datetime import datetime
from typing import List, Tuple
from decimal import Decimal
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import get_ist_time_str

if os.getenv("RAILWAY_VOLUME"):
    DB_PATH = os.path.join(os.getenv("RAILWAY_VOLUME"), "borsa_memory.db")
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), 'borsa_memory.db')
db_lock = threading.Lock()

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS signals_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, symbol TEXT, signal_type TEXT,
            regime TEXT, confidence_score REAL, reason TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cash_balance REAL, total_equity REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS active_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE, buy_price REAL,
            lot_amount INTEGER, remaining_lots INTEGER, buy_time TEXT, highest_seen REAL)''')
            
        # SCHEMA MIGRATION FOR EXISTING DB
        cursor.execute("PRAGMA table_info(active_trades)")
        cols = [info[1] for info in cursor.fetchall()]
        if "remaining_lots" not in cols:
            cursor.execute("ALTER TABLE active_trades ADD COLUMN remaining_lots INTEGER DEFAULT 0")
        if "highest_seen" not in cols:
            cursor.execute("ALTER TABLE active_trades ADD COLUMN highest_seen REAL DEFAULT 0.0")
            
        cursor.execute('''CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, buy_price REAL, sell_price REAL,
            lot_amount INTEGER, pnl REAL, reason TEXT,
            buy_time TEXT, sell_time TEXT)''')

        cursor.execute("SELECT COUNT(*) FROM portfolio")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO portfolio (id, cash_balance, total_equity) VALUES (1, 12000.0, 12000.0)")
            print("[INFO] Simulator portfolio initialized with default 12,000 TRY balance.")

        
        # Temizlik: Eski veritabanindan kalan 0 lotlu hayalet islemleri sil
        cursor.execute("DELETE FROM active_trades WHERE remaining_lots <= 0")

        conn.commit()
        conn.close()

def save_signal(symbol: str, signal_type: str, regime: str, confidence: float, reason: str):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO signals_history (timestamp, symbol, signal_type, regime, confidence_score, reason) VALUES (?, ?, ?, ?, ?, ?)',
            (get_ist_time_str(), symbol, signal_type, regime, confidence, reason))
        conn.commit()
        conn.close()

def get_recent_signals(limit: int = 50) -> List[Tuple]:
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT timestamp, symbol, signal_type, regime, confidence_score, reason FROM signals_history ORDER BY id DESC LIMIT ?',
            (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows

def save_trade(symbol: str, buy_price: Decimal, lot_amount: int):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO active_trades (symbol, buy_price, lot_amount, remaining_lots, buy_time, highest_seen) VALUES (?, ?, ?, ?, ?, ?)',
            (symbol, float(buy_price), lot_amount, lot_amount, get_ist_time_str(), float(buy_price)))
        conn.commit()
        conn.close()

def update_trade_lots_and_highest(symbol: str, remaining_lots: int, highest_seen: float):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE active_trades SET remaining_lots = ?, highest_seen = ? WHERE symbol = ?', (remaining_lots, highest_seen, symbol))
        conn.commit()
        conn.close()

def get_active_trades() -> List[Tuple]:
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT symbol, buy_price, lot_amount, remaining_lots, buy_time, highest_seen FROM active_trades')
        rows = cursor.fetchall()
        conn.close()
        return rows

def get_active_symbols() -> List[str]:
    trades = get_active_trades()
    return [row[0] for row in trades]

def remove_trade(symbol: str, sell_price: float = 0.0, pnl: float = 0.0, reason: str = "", lots_sold: int = 0):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT buy_price, buy_time FROM active_trades WHERE symbol = ?', (symbol,))
        row = cursor.fetchone()
        if row:
            buy_price, buy_time = row
            cursor.execute('''
                INSERT INTO trade_history (symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, sell_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, buy_price, sell_price, lots_sold, pnl, reason, buy_time, get_ist_time_str()))
            
        cursor.execute('DELETE FROM active_trades WHERE symbol = ?', (symbol,))
        conn.commit()
        conn.close()

def log_partial_sale(symbol: str, buy_price: float, sell_price: float, lots_sold: int, pnl: float, reason: str, buy_time: str):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trade_history (symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, sell_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, buy_price, sell_price, lots_sold, pnl, reason, buy_time, get_ist_time_str()))
        conn.commit()
        conn.close()

def update_portfolio_cash(new_cash: Decimal):
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE portfolio SET cash_balance = ? WHERE id = 1', (float(new_cash),))
        conn.commit()
        conn.close()

def get_portfolio() -> Tuple:
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT cash_balance, total_equity FROM portfolio WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        return row

init_db()
