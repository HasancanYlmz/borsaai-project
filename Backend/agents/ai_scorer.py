import os
import json
import asyncio
import urllib.request
import xml.etree.ElementTree as ET
import yfinance as yf
from google import genai
from dotenv import load_dotenv

load_dotenv()

TARGET_STOCKS = [
    "THYAO", "AKBNK", "ISCTR", "GARAN", "YKBNK",
    "KCHOL", "SAHOL", "TUPRS", "SISE", "ASELS"
]

SCORES_FILE = r'C:\Users\Hasancan\Desktop\BorsaAI_Proje\Backend\data\ai_scores.json'

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
            return "Son 24 saatte onemli bir haber bulunamadi."
        return "\n".join(news_items)
    except Exception as e:
        return f"Haberler cekilemedi: {e}"



def get_price_momentum(symbol):
    try:
        ticker = yf.Ticker(symbol + '.IS')
        hist = ticker.history(period='5d')
        if len(hist) < 2:
            return 'Veri yok.'
        change_5d = ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
        avg_vol = hist['Volume'].mean()
        last_vol = hist['Volume'].iloc[-1]
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1
        trend = 'YUKSELIS' if change_5d > 0 else 'DUSUS'
        vol_trend = 'ARTIYOR' if vol_ratio > 1.2 else ('AZALIYOR' if vol_ratio < 0.8 else 'NORMAL')
        return f'5G Degisim: {change_5d:.1f}% ({trend}) | Hacim: {vol_ratio:.1f}x ({vol_trend})'
    except Exception as e:
        return f'Momentum hesaplanamadi: {str(e)}'


def score_stock_with_gemini(symbol, client):
    news_text = fetch_turkish_news(symbol)
    momentum_text = get_price_momentum(symbol)

    prompt = (
        "Sen algoritmik ticaret sisteminin YZ analiztisinsin.\n"
        "Hisse: BIST:" + symbol + "\n"
        "Teknik Momentum: " + momentum_text + "\n"
        "Son Haberler: " + news_text + "\n\n"
        "Degerlendirme kriterleri:\n"
        "1. Fiyat momentumu YUKSELIS trendinde mi?\n"
        "2. Hacim artisi var mi?\n"
        "3. Haberlerde cok kotu bir gelisme var mi?\n\n"
        "Yaniti sadece su formatta ver:\n"
        "KARAR: APPROVE veya REJECT\n"
        "GUVEN: 0-100 arasi bir sayi\n"
        "NEDEN: 1 cumle (Momentum ve habere dayanarak)"
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        decision = "APPROVE"
        confidence = 50.0
        reason = "Analiz yapildi."
        for line in response.text.split('\n'):
            l = line.strip().upper()
            if l.startswith("KARAR:"):
                decision = l.replace("KARAR:", "").strip()
            elif l.startswith("GUVEN:"):
                try:
                    confidence = float(l.replace("GUVEN:", "").replace("%", "").strip())
                except Exception:
                    pass
            elif l.startswith("NEDEN:"):
                reason = l.replace("NEDEN:", "").strip()
        return {"decision": decision, "confidence": confidence, "reason": reason}
    except Exception as e:
        return {"decision": "APPROVE", "confidence": 50.0, "reason": "AI Hatasi: " + str(e)}


async def run_ai_scorer_loop():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "BURAYA_GEMINI_API_KEY_GELECEK":
        print("[AI SCORER] Gemini API Key eksik. AI Scorer calismayacak.")
        return
        
    client = genai.Client(api_key=api_key)
    
    while True:
        print("\n[AI SCORER] Hisse haberleri taranip skorlaniyor (Asenkron)...")
        scores = {}
        regime = await asyncio.to_thread(get_market_regime)
        scores["MARKET_REGIME"] = regime
        print(f"[MARKET] XU100 Piyasa Rejimi: {regime}")
        
        for sym in TARGET_STOCKS:
            result = await asyncio.to_thread(score_stock_with_gemini, sym, client)
            scores[sym] = result
            print(f"  -> {sym}: {result['decision']} (%{result['confidence']}) - {result['reason']}")
            await asyncio.sleep(2) # Rate limit onlemi
            
        with open(SCORES_FILE, 'w', encoding='utf-8') as f:
            json.dump(scores, f, indent=4, ensure_ascii=False)
            
        print("[AI SCORER] Tarama bitti. ai_scores.json guncellendi. 30 dakika bekleniyor...")
        await asyncio.sleep(1800) # 30 minutes

if __name__ == "__main__":
    asyncio.run(run_ai_scorer_loop())
