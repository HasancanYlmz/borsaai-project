from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from enum import Enum

# ---------------------------------------------------------
# BORSA AI - ÇEKİRDEK VERİ MODELLERİ (PYDANTIC ZIRHI)
# ---------------------------------------------------------

class SignalType(str, Enum):
    BUY = "AL"
    SELL = "SAT"
    HOLD = "TUT"
    WARNING = "ALARM"

class RegimeType(str, Enum):
    RALLY = "RALLİ"
    RANGE = "YATAY"
    CRASH = "ÇÖKÜŞ"

class MarketTick(BaseModel):
    symbol: str
    price: Decimal
    volume: float
    is_tavan: bool = False
    is_taban: bool = False
    is_halted: bool = False  # Devre Kesici (İşlem Sırası Durduruldu)
    timestamp: datetime = Field(default_factory=datetime.now)

class AKDData(BaseModel):
    symbol: str
    top_buyer: str
    top_buyer_lot: int
    top_seller: str
    top_seller_lot: int
    net_difference: int
    timestamp: datetime = Field(default_factory=datetime.now)

class MacroData(BaseModel):
    usd_try_price: float
    vix_index: float
    is_blackout_time: bool

class Signal(BaseModel):
    symbol: str
    signal_type: SignalType   # Sadece AL, SAT, TUT, ALARM olabilir (Troll Koruması)
    regime: RegimeType        # Sadece RALLİ, YATAY, ÇÖKÜŞ olabilir
    is_brut_takas: bool = False
    confidence_score: float
    reason: str
    timestamp: datetime = Field(default_factory=datetime.now)

# --- SİMÜLATÖR MODELLERİ ---

class Trade(BaseModel):
    """Robotun aldığı bir hissenin cüzdandaki kalıbı"""
    symbol: str
    buy_price: Decimal
    lot_amount: int
    buy_time: datetime = Field(default_factory=datetime.now)

class Portfolio(BaseModel):
    """Sanal Cüzdanımızın güncel durum kalıbı"""
    id: int = 1
    cash_balance: Decimal
    total_equity: Decimal
    commission_rate: float = 0.0004     # Aracı kurum komisyonu (Örn: Midas / İnfo)
    slippage_percent: float = 0.001     # Emir kayma payı (Sığ tahta koruması)
