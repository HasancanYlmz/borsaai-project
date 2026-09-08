import sqlite3
import os
import threading
from datetime import datetime
from typing import List, Tuple
from decimal import Decimal
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import get_ist_time_str

# ---------------------------------------------------------
# SYSTEM: DATABASE MANAGER (Thread-Safe)
# Handles SQLite connections and basic CRUD operations
# for signals, order history, and portfolio states.
# ---------------------------------------------------------

if os.getenv("RAILWAY_VOLUME"):
    DB_PATH = os.path.join(os.getenv("RAILWAY_VOLUME"), "borsa_memory.db")
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), 'borsa_memory.db')
db_lock = threading.Lock()

def get_connection():
    """Provides a thread-safe SQLite connection."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS signals_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, symbol TEXT, signal_type TEXT,
            regime TEXT, confidence_score REAL, reason TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS akd_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, symbol TEXT, top_buyer TEXT,
            top_buyer_lot INTEGER, top_seller TEXT,
            top_seller_lot INTEGER, net_difference INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cash_balance REAL, total_equity REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS active_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE, buy_price REAL,
            lot_amount INTEGER, buy_time TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, buy_price REAL, sell_price REAL,
            lot_amount INTEGER, pnl REAL, reason TEXT,
            buy_time TEXT, sell_time TEXT)''')

        cursor.execute("SELECT COUNT(*) FROM portfolio")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO portfolio (id, cash_balance, total_equity) VALUES (1, 10000.0, 10000.0)")
            print("[INFO] Simulator portfolio initialized with default 10,000 TRY balance.")

        conn.commit()
        conn.close()

# --- SIGNAL FUNCTIONS ---

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

# --- PORTFOLIO & TRADE FUNCTIONS ---

def save_trade(symbol: str, buy_price: Decimal, lot_amount: int):
    """Records a new long position in the active_trades table."""
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO active_trades (symbol, buy_price, lot_amount, buy_time) VALUES (?, ?, ?, ?)',
            (symbol, float(buy_price), lot_amount, get_ist_time_str()))
        conn.commit()
        conn.close()

def get_active_trades() -> List[Tuple]:
    """Retrieves all currently held positions."""
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT symbol, buy_price, lot_amount, buy_time FROM active_trades')
        rows = cursor.fetchall()
        conn.close()
        return rows

def get_active_symbols() -> List[str]:
    """Returns a list of symbols currently held in the portfolio."""
    trades = get_active_trades()
    return [row[0] for row in trades]

def remove_trade(symbol: str, sell_price: float = 0.0, pnl: float = 0.0, reason: str = ""):
    """Archives a sold position to trade_history and removes it from active_trades."""
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Eski işlemi bul
        cursor.execute('SELECT buy_price, lot_amount, buy_time FROM active_trades WHERE symbol = ?', (symbol,))
        row = cursor.fetchone()
        
        if row:
            buy_price, lot_amount, buy_time = row
            # 2. Arşive (Geçmişe) kaydet
            cursor.execute('''
                INSERT INTO trade_history (symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, sell_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, buy_price, sell_price, lot_amount, pnl, reason, buy_time, get_ist_time_str()))
            
        # 3. Aktif tablodan sil
        cursor.execute('DELETE FROM active_trades WHERE symbol = ?', (symbol,))
        conn.commit()
        conn.close()

def update_portfolio_cash(new_cash: Decimal):
    """Updates the available cash balance in the portfolio."""
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE portfolio SET cash_balance = ? WHERE id = 1', (float(new_cash),))
        conn.commit()
        conn.close()

def get_portfolio() -> Tuple:
    """Returns the current portfolio cash balance and total equity."""
    with db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT cash_balance, total_equity FROM portfolio WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        return row

init_db()
