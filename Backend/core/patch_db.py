import sqlite3
import os

DB_PATH = os.path.join(os.getenv("RAILWAY_VOLUME") if os.getenv("RAILWAY_VOLUME") else os.path.dirname(__file__), 'borsa_memory.db')

def patch_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check columns
        cursor.execute("PRAGMA table_info(active_trades)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'remaining_lots' not in columns:
            cursor.execute("ALTER TABLE active_trades ADD COLUMN remaining_lots INTEGER DEFAULT 0")
        if 'highest_seen' not in columns:
            cursor.execute("ALTER TABLE active_trades ADD COLUMN highest_seen REAL DEFAULT 0.0")
            
        print("DB Schema Patched")
        conn.commit()
        conn.close()
    except Exception as e:
        print("ERROR:", e)

if __name__ == '__main__':
    patch_db()
