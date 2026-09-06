import sys
import os
from typing import Dict

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.database import get_connection

# ---------------------------------------------------------
# BORSA AI - API: İSTATİSTİK VE PERFORMANS MERKEZİ
# C# Midas arayüzü (Frontend) için veritabanını analiz eder
# ve Kâr/Zarar (PnL), Kazanma Oranı (Win Rate) gibi metrikleri sunar.
# ---------------------------------------------------------

def calculate_system_stats() -> Dict:
    """Veritabanını okuyup sistemin genel MRG (Röntgen) sonucunu çıkarır."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Kasa Durumu
    cursor.execute("SELECT cash_balance, total_equity FROM portfolio WHERE id=1")
    row = cursor.fetchone()
    cash = row[0] if row else 10000.0
    equity = row[1] if row else 10000.0
    
    # 2. Aktif İşlemler
    cursor.execute("SELECT COUNT(*) FROM active_trades")
    active_count = cursor.fetchone()[0]
    
    # 3. Sinyal Sayısı
    cursor.execute("SELECT COUNT(*) FROM signals_history WHERE signal_type='BUY'")
    total_buy_signals = cursor.fetchone()[0]
    
    conn.close()
    
    # Kâr/Zarar Yüzdesi Hesaplama
    pnl_percent = round(((equity - 10000.0) / 10000.0) * 100, 2)
    
    return {
        "baslangic_bakiyesi": 10000.0,
        "guncel_nakit": round(cash, 2),
        "toplam_varlik": round(equity, 2),
        "kardayiz_yuzdesi": pnl_percent,
        "acik_pozisyon_sayisi": active_count,
        "alinan_buy_sinyali": total_buy_signals
    }
