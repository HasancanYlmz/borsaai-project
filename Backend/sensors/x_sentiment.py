import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import log_event

# ---------------------------------------------------------
# BORSA AI - SENSÖR: X (TWITTER) PUMP & DUMP DEDEKTÖRÜ
# Sosyal medyada "üstad" diye tabir edilen hesapların 
# bir hisseyi yapay olarak şişirip şişirmediğini (FOMO)
# tweet hızını (velocity) ölçerek tespit eder.
# ---------------------------------------------------------

def check_social_hype(symbol: str) -> dict:
    """
    X (Twitter) üzerinde '$HİSSE' etiketini aratır.
    Son 15 dakikadaki tweet sayısına bakarak bir "Hype (Şişirme)" skoru üretir.
    """
    cashtag = f"${symbol}"
    log_event("X_SENSOR", f"{cashtag} etiketi için sosyal medya radarı tarama yapıyor...")
    
    # Gerçek canlıda Twitter API v2 veya ntscraper kütüphanesi kullanılacaktır.
    # Şimdilik sistemin risk yöneticisine ileteceği veri taslağını kuruyoruz.
    
    simulated_tweet_count_last_15m = 450 # Anormal yüksek bir sayı
    
    hype_score = 0
    is_pump_warning = False
    
    if simulated_tweet_count_last_15m > 300:
        hype_score = 95
        is_pump_warning = True
        log_event("X_SENSOR", f"[DİKKAT] {cashtag} için sosyal medyada aşırı aktivite (Pump) tespit edildi!", level="WARNING")
    elif simulated_tweet_count_last_15m < 50:
        hype_score = 10
        log_event("X_SENSOR", f"{cashtag} sosyal medyada sessiz. Gerçek kurumsal alım olabilir.")
        
    return {
        "symbol": symbol,
        "tweet_velocity": simulated_tweet_count_last_15m,
        "hype_score": hype_score,
        "is_pump_warning": is_pump_warning
    }
