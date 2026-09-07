import requests
import time
from typing import List
import sys
import os
import xml.etree.ElementTree as ET

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.utils import log_event

# ---------------------------------------------------------
# BORSA AI - SENSÖR: KAP CANLI VERİ KAZIYICI
# KAP'ın açık API'sine bağlanıp şirketin son 24 saatteki
# resmi bildirimlerini çeker. IP Ban yememek için 30 dk Cache kullanır.
# ---------------------------------------------------------

_KAP_CACHE = {}
KAP_CACHE_TTL = 1800 # Haberler çok sık düşmez, 30 dakika hafızada tut

def get_kap_news(symbol: str) -> List[str]:
    """Hisseye ait güncel KAP haberlerinin başlıklarını liste olarak döndürür."""
    current_time = time.time()
    
    if symbol in _KAP_CACHE:
        cached_data, timestamp = _KAP_CACHE[symbol]
        if current_time - timestamp < KAP_CACHE_TTL:
            return cached_data
            
    try:
        news_list = []
        # 1. KAP Genel Bildirimler API'si
        try:
            url = "https://www.kap.org.tr/tr/api/disclosures"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for item in data:
                    codes = item.get("stockCodes", "")
                    if codes and symbol in codes:
                        title = item.get("disclosureClass", "BİLDİRİM") + " - " + item.get("disclosureName", "")
                        news_list.append(title)
        except Exception as e:
            log_event("WARNING", f"KAP API Yanıt Vermedi ({symbol}): {e}", level="WARNING")
        
        # 2. Eğer KAP'ta o gün haber yoksa, YFinance'in global/günlük haber ağını kontrol et
        if not news_list:
            import yfinance as yf
            try:
                yf_news = yf.Ticker(f"{symbol}.IS").news
                for n in yf_news[:2]: # Son 2 haber
                    title = n.get("title", "")
                    if title:
                        news_list.append(f"HABER - {title}")
            except:
                pass
        
        # 3. Bloomberg HT Entegrasyonu (Saf Finans İstihbaratı)
        try:
            b_url = "https://www.bloomberght.com/rss"
            b_resp = requests.get(b_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            if b_resp.status_code == 200:
                root = ET.fromstring(b_resp.content)
                for item in root.findall('.//item'):
                    title = item.find('title').text if item.find('title') is not None else ""
                    desc = item.find('description').text if item.find('description') is not None else ""
                    # Haberin başlığında veya özetinde hisse kodu geçiyorsa (örn: AKBNK) hemen yakala
                    if symbol in title or symbol in desc:
                        news_list.append(f"BLOOMBERG HT (KRİTİK) - {title}")
        except Exception:
            pass

        # 4. Google Haberler Entegrasyonu (Piyasa Dedikodusu ve Sondakika)
        try:
            gnews_url = f"https://news.google.com/rss/search?q={symbol}+hisse&hl=tr&gl=TR&ceid=TR:tr"
            g_resp = requests.get(gnews_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            if g_resp.status_code == 200:
                root = ET.fromstring(g_resp.content)
                g_count = 0
                for item in root.findall('.//item'):
                    if g_count >= 2: # Bloomberg eklendiği için Google'ı 2'ye düşürdük
                        break
                    title = item.find('title').text
                    if title:
                        news_list.append(f"PİYASA SÖYLENTİSİ - {title}")
                        g_count += 1
        except Exception as e:
            pass
        
        log_event("KAP_SENSOR", f"{symbol} için {len(news_list)} adet (KAP+Bloomberg+Google) haber bulundu.")
        
        # Sonucu hafızaya (Cache) mühürle
        _KAP_CACHE[symbol] = (news_list, current_time)
        return news_list
        
    except Exception as e:
        log_event("ERROR", f"Genel Haber Veri Hatasi ({symbol}): {e}", level="ERROR")
        return []
