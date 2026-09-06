import sys
import os
from typing import Dict

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.models import AKDData
from core.utils import log_event

def detect_spoofing_and_dominance(akd: AKDData) -> Dict:
    """Telegram'dan gelen AKD verisine göre tahtanın kalitesini ölçer."""
    log_event("QUANT_AKD", f"{akd.symbol} tahta analizine başlandı...")
    
    total_transaction_lot = akd.top_buyer_lot + akd.top_seller_lot
    if total_transaction_lot == 0:
        return {"dominance_pct": 0, "is_spoofing_suspected": False, "verdict": "HACİMSİZ"}
        
    buyer_dominance_pct = (akd.top_buyer_lot / total_transaction_lot) * 100
    seller_dominance_pct = (akd.top_seller_lot / total_transaction_lot) * 100
    
    # Net lot farkının toplam işleme oranı (Dinamik Spoofing Kalkanı)
    net_diff_pct = (akd.net_difference / total_transaction_lot) * 100
    
    is_spoofing = False
    verdict = "NÖTR"
    
    if buyer_dominance_pct >= 40.0:
        verdict = f"KURUMSAL_ALIM ({akd.top_buyer} süpürüyor)"
        
    elif seller_dominance_pct >= 40.0:
        verdict = f"KURUMSAL_SATIŞ ({akd.top_seller} mal boşaltıyor)"
        
    # KURAL 3: DİNAMİK SPOOFING (SAHTE EMİR TUZAĞI)
    # Net fark toplam işlemin %15'inden fazla eksideyse ve satıcı baskınsa
    elif net_diff_pct < -15.0 and seller_dominance_pct > 35.0 and buyer_dominance_pct < 20.0:
        is_spoofing = True
        verdict = "SPOOFING_TEHLİKESİ (KY Tuzağı)"
        log_event("QUANT_AKD", f"{akd.symbol} tahtasında SPOOFING tespit edildi! Uzak durulmalı.", level="WARNING")

    return {
        "buyer_dominance_pct": round(buyer_dominance_pct, 2),
        "seller_dominance_pct": round(seller_dominance_pct, 2),
        "is_spoofing_suspected": is_spoofing,
        "verdict": verdict
    }
