import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.models import Signal, SignalType, RegimeType
from core.utils import log_event

# ---------------------------------------------------------
# BORSA AI - CORE: SİNYAL ÜRETİCİ
# Komiteden çıkan ham kararı, sistemin bozulmaz (Pydantic)
# yapısına çevirip Simülatöre/Veritabanına yollayan Formatter.
# ---------------------------------------------------------

def generate_signal(committee_result: dict, is_brut_takas: bool = False) -> Signal:
    """Komite kararını alır, geçerli ve korumalı bir Signal modeline çevirir."""
    symbol = committee_result["symbol"]
    decision = committee_result["decision"]
    
    # Kararı Pydantic Enum'a güvenle dönüştür
    if decision == "AL":
        sig_type = SignalType.BUY
    elif decision == "SAT":
        sig_type = SignalType.SELL
    else:
        sig_type = SignalType.HOLD
        
    # Rejimi Pydantic Enum'a güvenle dönüştür
    reg_raw = committee_result.get("regime", "YATAY")
    if reg_raw == "RALLİ":
        reg_type = RegimeType.RALLY
    elif reg_raw == "ÇÖKÜŞ":
        reg_type = RegimeType.CRASH
    else:
        reg_type = RegimeType.RANGE
        
    signal = Signal(
        symbol=symbol,
        signal_type=sig_type,
        regime=reg_type,
        is_brut_takas=is_brut_takas,
        confidence_score=committee_result["score"],
        reason=committee_result["reasons"]
    )
    
    log_event("SIGNAL_GEN", f"Resmi Sinyal Üretildi: {signal.symbol} -> {signal.signal_type.value} (Güven: {signal.confidence_score})")
    
    return signal
