import logging
from typing import Dict, Any

logger = logging.getLogger("matriks_engine")

class MatriksEngine:
    """
    Bu modül, Matriks IQ'dan gelecek olan (Düzey 2/Derinlik ve AKD) verileri işleyip
    BorsaAI karar mekanizmasına kurumsal sinyaller üretmek için tasarlanmıştır.
    (Canlı Matriks soketleri bağlanana kadar mantıksal şablon olarak çalışır).
    """

    @staticmethod
    def analyze_order_book_imbalance(depth_data: Dict[str, Any]) -> str:
        """
        Madde 2: Tahta Baskısı (Order Book Imbalance)
        10 Kademelik derinlik verisini okur. Toplam Alış lotları ile Satış lotlarını kıyaslar.
        Eğer satışta devasa bir yığılma varsa "Satış Baskısı" sinyali üretir.
        """
        try:
            total_bid_vol = sum(level['lot'] for level in depth_data.get('bids', []))
            total_ask_vol = sum(level['lot'] for level in depth_data.get('asks', []))
            
            if total_bid_vol == 0 and total_ask_vol == 0:
                return "NEUTRAL"
                
            imbalance_ratio = total_bid_vol / (total_bid_vol + total_ask_vol)
            
            if imbalance_ratio > 0.75:
                return "ALIS_BASKISI"  # %75'ten fazla alıcı var, kopabilir
            elif imbalance_ratio < 0.25:
                return "SATIS_BASKISI" # %75'ten fazla satıcı baraj kurmuş
            else:
                return "NEUTRAL"
        except Exception as e:
            logger.error(f"Derinlik analiz hatası: {e}")
            return "NEUTRAL"

    @staticmethod
    def analyze_akd_anomaly(akd_data: Dict[str, Any]) -> str:
        """
        Madde 3: Aracı Kurum (AKD) Anomali Avcısı
        İlk 5 Net Alıcı ve Satıcıyı kıyaslar. Yabancı kurumların (BOFA, Yatırım Finansman, TERA vb.)
        tek başına tahtanın %50'sinden fazlasını süpürdüğü durumları tespit eder.
        """
        try:
            top_buyers = akd_data.get("top_buyers", [])
            total_net_buy = sum(b['net_lot'] for b in top_buyers)
            
            if total_net_buy == 0:
                return "NEUTRAL"

            # Check if BOFA is hoarding
            for buyer in top_buyers:
                if buyer['broker'] in ['BOFA', 'YATIRIM_FIN', 'TERA']:
                    dominance = buyer['net_lot'] / total_net_buy
                    if dominance > 0.50:
                        return f"YABANCI_TOPLUYOR_({buyer['broker']})"
                        
            return "NEUTRAL"
        except Exception as e:
            logger.error(f"AKD analiz hatası: {e}")
            return "NEUTRAL"

    @staticmethod
    def check_circuit_breaker_opportunity(theoretical_data: Dict[str, Any]) -> str:
        """
        Madde 4: Devre Kesici (Teorik Eşleşme) Fırsatları
        Hisse devre kesicideyken (Tahta kapalıyken) teorik eşleşme miktarını ve yönünü okur.
        Taban olan hissenin tabanında bekleyen lot eriyorsa "Taban Çözülüyor" uyarısı verir.
        """
        try:
            status = theoretical_data.get("status")
            if status != "HALTED":
                return "NORMAL"
                
            theo_price = theoretical_data.get("theoretical_price")
            base_price = theoretical_data.get("base_price") # taban fiyatı
            unmatched_sell_lots = theoretical_data.get("unmatched_sell", 0)
            
            if theo_price > base_price and unmatched_sell_lots == 0:
                return "TABAN_BOZULUYOR_FIRSAT"
                
            return "DEVRE_KESICI_AKTIF"
        except Exception as e:
            logger.error(f"Devre kesici analiz hatası: {e}")
            return "NORMAL"

    @staticmethod
    def detect_scalp_opportunity(tick_data: Dict[str, Any]) -> bool:
        """
        Madde 5: Oynaklık (Spread) Avcısı (Gerçek Zamanlı Scalping)
        Alış ve satış arasındaki fiyat makası anlık olarak açıldığında,
        aradaki likidite boşluğunu sömürmek (scalp) için True döner.
        """
        try:
            best_bid = tick_data.get("best_bid", 0)
            best_ask = tick_data.get("best_ask", 0)
            
            if best_bid == 0 or best_ask == 0:
                return False
                
            spread_pct = ((best_ask - best_bid) / best_bid) * 100
            
            if spread_pct >= 0.5:
                return True
                
            return False
        except Exception as e:
            logger.error(f"Scalp analiz hatası: {e}")
            return False
