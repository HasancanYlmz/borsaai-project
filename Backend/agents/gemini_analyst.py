import asyncio
import os
import urllib.request
import xml.etree.ElementTree as ET
import yfinance as yf
from google import genai
from core.utils import log_event
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------
# GEMINI AI ANALYST
# ---------------------------------------------------------

def fetch_turkish_news(symbol):
    try:
        url = f"https://news.google.com/rss/search?q={symbol}+hisse+kap&hl=tr&gl=TR&ceid=TR:tr"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            xml_data = response.read()
        root = ET.fromstring(xml_data)
        
        news_items = []
        for item in root.findall('.//item')[:3]:
            title = item.find('title').text
            news_items.append(f"- {title}")
            
        if not news_items:
            return "Son 24 saatte onemli bir KAP haberi bulunamadi."
        return "\n".join(news_items)
    except Exception as e:
        return f"Haberler cekilemedi: {e}"

async def analyze_stock_with_gemini(symbol: str) -> dict:
    """
    Analyzes the latest basic info/news and returns a decision.
    Returns: {"decision": "APPROVE"|"REJECT", "confidence": float, "reason": str}
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "BURAYA_GEMINI_API_KEY_GELECEK":
        log_event("AI_AGENT", "Gemini API Key eksik. Onay atlandi (MOCK APPROVE).", level="WARNING")
        return {"decision": "APPROVE", "confidence": 75.0, "reason": "API Key Yok - Otomatik Onay"}
        
    try:
        clean_symbol = symbol.replace('BIST:', '') + '.IS'
        ticker = yf.Ticker(clean_symbol)
        info = await asyncio.to_thread(lambda: ticker.fast_info)
        
        market_cap = info.get('marketCap', 'Bilinmiyor')
        last_price = info.get('lastPrice', 'Bilinmiyor')
        
        news_text = await asyncio.to_thread(fetch_turkish_news, symbol)
        
        prompt = f"""Sen Borsa Istanbul'da islem yapan kurumsal bir fon yoneticisisin.
TradingView algoritmasi, {symbol} hissesi icin 'Alim' sinyali uretti.

Google News & KAP (Son Haberler):
{news_text}

Lutfen bu sinyali hizlica degerlendir. Eger sirket hakkinda cok olumsuz bir haber varsa REJECT et. Eger notr veya olumluysa APPROVE et.
Bana yalnizca su formatta yanit ver:
KARAR: APPROVE veya REJECT
GUVEN: 0-100 arasi bir sayi
NEDEN: 1 cumlelik kisa aciklama (Haberlere dayanarak)
"""
        
        client = genai.Client(api_key=api_key)
        
        def call_ai():
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            return response.text

        ai_response = await asyncio.to_thread(call_ai)
        
        decision = "APPROVE"
        confidence = 50.0
        reason = "Analiz yapildi."
        
        lines = ai_response.split('\n')
        for line in lines:
            line = line.strip().upper()
            if line.startswith("KARAR:"):
                decision = line.replace("KARAR:", "").strip()
            elif line.startswith("GUVEN:"):
                try:
                    confidence = float(line.replace("GUVEN:", "").replace("%", "").strip())
                except:
                    pass
            elif line.startswith("NEDEN:"):
                reason = line.replace("NEDEN:", "").strip()
                
        return {"decision": decision, "confidence": confidence, "reason": reason}
        
    except Exception as e:
        log_event("AI_AGENT", f"Gemini Hatasi: {str(e)}", level="ERROR")
        return {"decision": "APPROVE", "confidence": 50.0, "reason": f"AI Hatasi: {str(e)}"}
