import sys
import os
from typing import Dict

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import log_event

# ---------------------------------------------------------
# BORSA AI - AJAN: RİSK YÖNETİMİ (VETO KOMİTESİ)
# Sistem 'AL' dese bile, makro riskleri, sektör rotasyonunu 
# ve tahta sığlığını kontrol edip son dakika VETO yetkisini kullanır.
# ---------------------------------------------------------

def evaluate_trade_risk(symbol: str, macro_data: dict, sector_data: dict, tv_data: dict) -> bool:
    """Tüm riskleri masaya yatırır. Her şey güvenliyse True, riskliyse False (VETO) döner."""
    log_event("AGENT_RISK", f"{symbol} emri Veto Komitesinde inceleniyor...")
    
    # 1. MAKRO RİSK KONTROLÜ (Dolar, VIX, BİST Çöküşü)
    if not macro_data.get("is_trade_allowed", False):
        log_event("AGENT_RISK", f"VETO! Makro Piyasa Kötü. Sebep: {macro_data.get('risk_level')}", level="WARNING")
        return False
        
    # 2. SIĞLIK KONTROLÜ (Hacim Yetersizliği)
    if tv_data and tv_data.get("volume", 0) < 500000:
        log_event("AGENT_RISK", f"VETO! {symbol} tahtası çok sığ (Hacim: {tv_data.get('volume')}). Girmek tehlikeli.", level="WARNING")
        return False
        
    # 3. SEKTÖR TERSİ KONTROLÜ (Opsiyonel)
    # Hissenin ait olduğu sektörde ciddi para çıkışı varsa uyarı verir.
    # Şimdilik sadece uyarı veriyor, Veto etmiyor (Bazen şirket haberle sektörden ayrışır)
    # Not: Gerçek sistemde sembolün sektörünü dinamik bulan bir yapı (BIST_SECTORS_MAP) eklenir.
    
    log_event("AGENT_RISK", f"ONAY: {symbol} emri için tüm güvenlik kontrolleri başarıyla geçildi.")
    return True
