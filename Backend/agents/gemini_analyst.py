import asyncio
import os
import yfinance as yf
from google import genai
from core.utils import log_event
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------
# GEMINI AI ANALYST
# ---------------------------------------------------------

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
        
        prompt = f\"\"\"Sen Borsa Istanbul'da islem yapan kurumsal bir fon yoneticisisin.
Bir algoritma, {clean_symbol} hissesi icin 'Hacim Patlamasi' sinyali uretti.

Guncel YFinance Verileri:
- Son Fiyat: {last_price}
- Piyasa Degeri: {market_cap}

Lutfen bu sinyali hizlica degerlendir ve bana yalnizca su formatta yanit ver:
KARAR: APPROVE veya REJECT
GUVEN: 0-100 arasi bir sayi
NEDEN: 1 cumlelik kisa aciklama
\"\"\"
        
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
