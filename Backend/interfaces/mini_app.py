import json

import os

import asyncio

from aiohttp import web

from core.utils import log_event

from agents.gemini_analyst import analyze_stock_with_gemini

from simulator.virtual_broker import execute_virtual_buy

from core.database import get_recent_signals, get_portfolio, get_active_trades

import yfinance as yf



FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Frontend"))




MARKET_CACHE = {}
LAST_MARKET_UPDATE = 0

import asyncio
import time
signal_queue = asyncio.Queue()
COOLDOWN_CACHE = {}
DAILY_TRADES = {"date": "", "count": 0}
MAX_PNL_CACHE = {}



def advanced_signal_filter(symbol):
    try:
        import yfinance as yf
        import pandas as pd
        import math
        
        # BIST100 (Genel Piyasa) Verisi
        bist = yf.download("XU100.IS", period="5d", interval="1d", progress=False)
        bist_pct = 0.0
        if len(bist) >= 2:
            bist_close = float(bist['Close'].iloc[-1].iloc[0] if isinstance(bist['Close'].iloc[-1], pd.Series) else bist['Close'].iloc[-1])
            bist_prev = float(bist['Close'].iloc[-2].iloc[0] if isinstance(bist['Close'].iloc[-2], pd.Series) else bist['Close'].iloc[-2])
            bist_pct = ((bist_close - bist_prev) / bist_prev) * 100
            
        # Hisse Ozelinde Teknik Veriler
        df = yf.download(f"{symbol}.IS", period="3mo", interval="1d", progress=False)
        if len(df) < 15:
            return True, "Onay: Veri yetersiz ama TV sinyali gecerli (Puan hesabi yapilamadi)"
            
        closes = df['Close'][f"{symbol}.IS"] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        volumes = df['Volume'][f"{symbol}.IS"] if isinstance(df['Volume'], pd.DataFrame) else df['Volume']
        closes = closes.dropna()
        volumes = volumes.dropna()
        
        current_price = float(closes.iloc[-1])
        prev_price = float(closes.iloc[-2]) if len(closes) >=2 else current_price
        stock_pct = ((current_price - prev_price) / prev_price) * 100 if prev_price > 0 else 0.0
        
        current_vol = float(volumes.iloc[-1])
        avg_vol = float(volumes.rolling(window=10).mean().iloc[-2]) if len(volumes) >= 10 else current_vol
        rvol = current_vol / avg_vol if avg_vol > 0 else 1.0
        
        # RSI Hesaplama (14 gunluk)
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1])
        
        # SMA20 Hesaplama
        sma20 = float(closes.rolling(window=20).mean().iloc[-1])
        
        # ----------------------------------------------------
        # PUANLAMA ALGORITMASI (Max 100 Puan - Baraj 50 Puan)
        # ----------------------------------------------------
        score = 0
        details = []
        
        # 1. Endeks Puani (Max 20)
        if bist_pct > 0:
            score += 20
            details.append("Endeks Pozitif (+20)")
        elif bist_pct >= -0.5:
            score += 10
            details.append("Endeks Notr (+10)")
        else:
            details.append("Endeks Negatif (+0)")
            
        # 2. RSI Puani (Max 30)
        if 40 <= current_rsi <= 60:
            score += 30
            details.append(f"RSI Ideal {current_rsi:.0f} (+30)")
        elif 60 < current_rsi <= 70:
            score += 20
            details.append(f"RSI Sicak {current_rsi:.0f} (+20)")
        elif 70 < current_rsi <= 80:
            score += 5
            details.append(f"RSI Sismis {current_rsi:.0f} (+5)")
        else:
            details.append(f"RSI Tehlikeli {current_rsi:.0f} (+0)")
            
        # 3. Trend Puani (Max 25)
        if current_price > sma20:
            score += 25
            details.append("Fiyat>SMA20 (+25)")
        else:
            details.append("Fiyat<SMA20 (+0)")
            
        # 4. Hacim Puani (Max 25)
        if rvol > 1.5:
            score += 25
            details.append(f"Hacim Patlamasi {rvol:.1f}x (+25)")
        else:
            details.append(f"Hacim Zayif {rvol:.1f}x (+0)")
            
        # 5. Goreceli Guc Bonusu (Akilli Filtre - Max 12 Puan)
        if stock_pct > 0:
            if bist_pct < -2.0:
                if (stock_pct - bist_pct) >= 2.0 and rvol > 1.5 and current_rsi < 60:
                    score += 12
                    details.append("Guc (+12) Cokuste Lider")
            elif bist_pct > 0:
                if (stock_pct - bist_pct) >= 2.0 and rvol > 1.5 and current_rsi < 60:
                    score += 12
                    details.append("Guc (+12) Yukseliste Lider")
            else:
                if rvol > 1.5 and current_rsi < 60:
                    score += 6
                    details.append("Guc (+6) Hacimli Kirilim")
            
        # Sonuc Degerlendirmesi
        reason_str = ", ".join(details)
        if score >= 50:
             return True, f"✅ ONAY: Puan {score}/112. [{reason_str}]", score
        else:
             return False, f"❌ RED: Puan {score}/112. BARAJ GECILEMEDI. [{reason_str}]", score
             
    except Exception as e:
        return True, f"ONAY: TradingView Sinyali (Puanlama Hatasi: {str(e)})", 50.0


async def portfolio_monitor_bg():
    import asyncio
    from simulator.virtual_broker import execute_virtual_sell
    from core.database import get_active_trades
    
    while True:
        try:
            await asyncio.sleep(60) # Her 60 saniyede bir kontrol et
            
            # BIST100 Cokus Kontrolu (Acil Cikis)
            bist_data = MARKET_CACHE.get("BIST100", {})
            bist_pct = bist_data.get("percent", 0.0)
            
            is_panic = bist_pct < -2.0
            
            trades = get_active_trades()
            if not trades:
                continue
                
            for t in trades:
                sym = t[0]
                bp = float(t[1])
                cp = MARKET_CACHE.get(sym, {}).get("price", bp)
                
                if cp == 0 or bp == 0: continue
                
                pnl_pct = ((cp - bp) / bp) * 100
                
                # 1. Kural: Piyasa Cokusu (Panic Sell)
                if is_panic:
                    await execute_virtual_sell(sym, cp, f"ACIL CIKIS: BIST100 cokusu ({bist_pct:.2f}%)")
                    continue
                    
                # Max PnL takibi (Trailing Stop icin)
                current_max = MAX_PNL_CACHE.get(sym, -100.0)
                if pnl_pct > current_max:
                    MAX_PNL_CACHE[sym] = pnl_pct
                    current_max = pnl_pct

                # 2. Kural: Trailing Stop Loss & Kar Al
                if current_max >= 4.0 and pnl_pct <= current_max - 1.0:
                    # Zirveden %1 geri cekilmis -> SAT (Min %3 kar)
                    await execute_virtual_sell(sym, cp, f"TRAILING STOP: Zirveden dondu. Kar: %{pnl_pct:.2f}")
                    MAX_PNL_CACHE.pop(sym, None)
                elif current_max >= 3.0 and pnl_pct <= 1.0:
                    # %3'u gormus, %1'e dusmus -> SAT
                    await execute_virtual_sell(sym, cp, f"TRAILING STOP: %3'ten %1'e dondu. Kar: %{pnl_pct:.2f}")
                    MAX_PNL_CACHE.pop(sym, None)
                elif current_max >= 2.0 and pnl_pct <= 0.0:
                    # %2'yi gormus, basa basa dusmus -> SAT
                    await execute_virtual_sell(sym, cp, f"TRAILING STOP: Basa Bas Cikis. Karsiz Islem.")
                    MAX_PNL_CACHE.pop(sym, None)
                elif pnl_pct <= -3.0:
                    # Sabit Zarar Kes
                    await execute_virtual_sell(sym, cp, f"ZARAR KES (STOP-LOSS): %{pnl_pct:.2f}")
                    MAX_PNL_CACHE.pop(sym, None)
                    
        except Exception as e:
            print("Monitor Error:", e)

async def process_signal_queue():
    import asyncio
    while True:
        try:
            data = await signal_queue.get()
            action = data.get("action", "").upper()
            symbol = data.get("symbol", "")
            price = data.get("price", 0.0)
            
            try: price = float(price)
            except: price = 0.0
            
            from simulator.virtual_broker import execute_virtual_buy, execute_virtual_sell
            
            if action in ["AL", "BUY"]:
                # --- Gun Sonu ve Seans Filtresi ---
                now = time.localtime()
                if now.tm_hour >= 17 and now.tm_min >= 30:
                    # Saat 17:30 sonrasi sinyalleri yoksay
                    signal_queue.task_done()
                    continue
                
                # --- Gunluk Limit Kontrolu ---
                today_str = time.strftime("%Y-%m-%d", now)
                if DAILY_TRADES["date"] != today_str:
                    DAILY_TRADES["date"] = today_str
                    DAILY_TRADES["count"] = 0
                
                # --- Cooldown (30 Dk) Kontrolu ---
                last_time = COOLDOWN_CACHE.get(symbol, 0)
                if time.time() - last_time < 1800:
                    signal_queue.task_done()
                    continue # 30 dk gecmeden ayni hisseyi isleme alma
                COOLDOWN_CACHE[symbol] = time.time()

                is_valid, reason, score = await asyncio.to_thread(advanced_signal_filter, symbol)
                
                # --- DINAMIK GUNLUK LIMIT (Boga Piyasasinda Esneme) ---
                bist_info = MARKET_CACHE.get("XU100", {})
                bist_pct = bist_info.get("change_pct", 0.0)
                dynamic_limit = 12 if bist_pct > 1.0 else 8
                
                # --- GEMINI YZ HABER FILTRESI (Sadece Teknik Onay Alanlar Icin) ---
                if is_valid and DAILY_TRADES["count"] < dynamic_limit:
                    from agents.gemini_analyst import analyze_stock_with_gemini
                    ai_result = await analyze_stock_with_gemini(symbol)
                    
                    if ai_result["decision"] == "REJECT":
                        is_valid = False
                        reason = f"GEMINI HABER VETOSU: {ai_result['reason']} (Teknik Puan: {score})"
                    else:
                        reason = f"{reason} | Gemini Haber Onayi: {ai_result['reason']}"
                
                # Radar sekmesi icin loglama
                from core.database import save_signal
                sig_type = "AL" if is_valid else "RED"
                
                # Eger limit dolduysa ama sinyal onay aldiysa, alimi iptal et
                if is_valid and DAILY_TRADES["count"] >= dynamic_limit:
                    is_valid = False
                    reason = f"GUNLUK LIMIT ({dynamic_limit}/{dynamic_limit}) DOLDU. " + reason
                    sig_type = "RED"
                
                await asyncio.to_thread(save_signal, symbol, sig_type, "BULL", float(score), reason)
                
                if is_valid:
                    DAILY_TRADES["count"] += 1
                    await execute_virtual_buy(symbol, price, reason, float(score))
                else:
                    from simulator.virtual_broker import send_telegram_message
                    msg = "⛔ ALIM REDDEDİLDİ\n\nHisse: " + symbol + "\nNeden: " + reason
                    await asyncio.to_thread(send_telegram_message, msg)
                    
            elif action in ["SAT", "SELL"]:
                await execute_virtual_sell(symbol, price, "TradingView Trailing Stop")
                
            signal_queue.task_done()
        except Exception as e:
            print("Queue processing error:", e)

async def handle_tradingview_webhook(request):
    try:
        data = await request.json()
        secret = data.get("secret", "")
        if secret != "BorsaAI_Gizli_Anahtar_2026":
            from aiohttp import web
            return web.json_response({"status": "error", "message": "Yetkisiz islem."}, status=403)
            
        await signal_queue.put(data)
        from aiohttp import web
        return web.json_response({"status": "success", "message": "Sinyal kuyruga alindi."})
    except Exception as e:
        from aiohttp import web
        return web.json_response({"status": "error", "message": str(e)}, status=400)

async def fetch_market_data_bg():


    global MARKET_CACHE, LAST_MARKET_UPDATE

    import yfinance as yf

    import asyncio

    import time

    import json

    import os

    symbols = ["AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKSA.IS", "AKSEN.IS", "ALARK.IS", "ALBRK.IS", "ASGYO.IS", "ASELS.IS", "ASTOR.IS", "AYDEM.IS", "BAGFS.IS", "BERA.IS", "BIMAS.IS", "BIOEN.IS", "BRISA.IS", "BRSAN.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS", "CEMTS.IS", "CIMSA.IS", "CWENE.IS", "DOAS.IS", "DOHOL.IS", "ECILC.IS", "EGEEN.IS", "EKGYO.IS", "ENJSA.IS", "ENKAI.IS", "EREGL.IS", "EUREN.IS", "FROTO.IS", "GARAN.IS", "GESAN.IS", "GOLTS.IS", "GOZDE.IS", "GSDHO.IS", "GUBRF.IS", "GWIND.IS", "HALKB.IS", "HEKTS.IS", "IPEKE.IS", "ISCTR.IS", "ISFIN.IS", "ISGYO.IS", "ISMEN.IS", "IZENR.IS", "KARSN.IS", "KCAER.IS", "KCHOL.IS", "KMPUR.IS", "KONTR.IS", "KORDS.IS", "KOZAA.IS", "KOZAL.IS", "KRDMD.IS", "LOGO.IS", "MAVI.IS", "MGROS.IS", "MIATK.IS", "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PARSN.IS", "PETKM.IS", "PGSUS.IS", "PSGYO.IS", "QUAGR.IS", "SAHOL.IS", "SASA.IS", "SISE.IS", "SMRTG.IS", "SOKM.IS", "TATGD.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TTRAK.IS", "TUKAS.IS", "TUPRS.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YKBNK.IS", "YYLGD.IS", "ZOREN.IS", "XU100.IS"]

    try:

        df = yf.download(symbols, period="5d", interval="1d", progress=False)

        if not df.empty:

            cache = {}

            for sym in symbols:

                clean_sym = sym.replace(".IS", "")

                if clean_sym == "XU100": clean_sym = "BIST100"

                try:
                    import math
                    close_today = float(df['Close'][sym].iloc[-1])
                    
                    if len(df['Close'][sym]) >= 2:
                        close_yest = float(df['Close'][sym].iloc[-2])
                    else:
                        close_yest = close_today
                        
                    if math.isnan(close_today): close_today = 0.0
                    if math.isnan(close_yest) or close_yest == 0:
                        pct = 0.0
                    else:
                        pct = ((close_today - close_yest) / close_yest) * 100
                        if math.isnan(pct): pct = 0.0
                    cache[clean_sym] = {"price": close_today, "percent": pct, "rvol": 1.0}
                except Exception as e:
                    cache[clean_sym] = {"price": 0.0, "percent": 0.0, "rvol": 1.0}

            # Read market regime

            scores_file = r'C:\Users\Hasancan\Desktop\BorsaAI_Proje\Backend\data\ai_scores.json'

            regime = "BILINMIYOR"

            if os.path.exists(scores_file):

                try:

                    with open(scores_file, 'r', encoding='utf-8') as sf:

                        sc = json.load(sf)

                        regime = sc.get("MARKET_REGIME", "BILINMIYOR")

                except: pass

            if "BIST100" in cache:

                cache["BIST100"]["regime"] = regime

            MARKET_CACHE = cache

            LAST_MARKET_UPDATE = time.time()

    except:

        pass




async def api_data(request):
    try:
        from core.database import get_recent_signals
        rows = get_recent_signals(10)
        sigs = []
        for r in rows:
            sigs.append({
                "timestamp": r[0],
                "symbol": r[1],
                "type": r[2],
                "confidence": r[4],
                "reason": r[5]
            })
        from aiohttp import web
        return web.json_response({"status": "success", "data": sigs})
    except Exception as e:
        from aiohttp import web
        return web.json_response({"status": "error", "message": str(e)})

async def api_market(request):

    import time

    if time.time() - LAST_MARKET_UPDATE > 120:

        import asyncio

        asyncio.create_task(fetch_market_data_bg())

    return web.json_response(MARKET_CACHE)



async def api_performance(request):
    try:
        from core.database import get_portfolio, get_active_trades
        port = get_portfolio()
        cash = port[0] if port else 12000.0
        trades = get_active_trades()
        positions = []
        total_eq = cash
        for t in trades:
            sym = t[0]
            bp = float(t[1])
            lots = int(t[3])
            cp = MARKET_CACHE.get(sym, {}).get("price", bp)
            if cp == 0: cp = bp
            pnl = (cp - bp) * lots
            pnl_pct = ((cp - bp) / bp * 100) if bp > 0 else 0
            total_eq += (cp * lots)
            positions.append({
                "symbol": sym, "type": "LONG", "lot_amount": lots,
                "buy_price": bp, "current_price": cp, "pnl": pnl, "pnl_pct": pnl_pct
            })
            
        return web.json_response({
            "status": "success",
            "total_cash": cash,
            "total_portfolio_value": total_eq,
            "total_pnl": total_eq - 12000.0,
            "positions": positions
        })
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)})



async def api_history(request):
    try:
        symbol = request.query.get("symbol")
        p = request.query.get("period", "3A")
        
        if p == "1G":
            yf_period = "1d"
            yf_interval = "5m"
        elif p == "1H":
            yf_period = "5d"
            yf_interval = "15m"
        elif p == "1A":
            yf_period = "1mo"
            yf_interval = "1d"
        elif p == "1Y":
            yf_period = "1y"
            yf_interval = "1d"
        else:
            yf_period = "3mo"
            yf_interval = "1d"
            
        import yfinance as yf
        import asyncio
        import pandas as pd
        import math
        ticker = f"{symbol}.IS"
        def fetch_data():
            df = yf.download(ticker, period=yf_period, interval=yf_interval, progress=False)
            if df.empty: return []
            data = []
            for date, row in df.iterrows():
                try:
                    o = float(row["Open"].iloc[0] if isinstance(row["Open"], pd.Series) else row["Open"])
                    h = float(row["High"].iloc[0] if isinstance(row["High"], pd.Series) else row["High"])
                    l = float(row["Low"].iloc[0] if isinstance(row["Low"], pd.Series) else row["Low"])
                    c = float(row["Close"].iloc[0] if isinstance(row["Close"], pd.Series) else row["Close"])
                    v = float(row["Volume"].iloc[0] if isinstance(row["Volume"], pd.Series) else row["Volume"])
                    if math.isnan(o) or math.isnan(c): continue
                    
                    if yf_interval == "1d":
                        t = date.strftime("%Y-%m-%d")
                    else:
                        t = int(date.timestamp()) + 10800
                    
                    data.append({
                        "time": t,
                        "open": o, "high": h, "low": l, "close": c,
                        "value": v
                    })
                except:
                    continue
            return data
        data = await asyncio.to_thread(fetch_data)
        return web.json_response({"status": "success", "data": data})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)})




async def api_sell(request):
    try:
        symbol = request.query.get("symbol")
        if not symbol:
            return web.json_response({"status": "error", "message": "Sembol gerekli."})
        from simulator.virtual_broker import execute_virtual_sell
        from core.database import get_active_trades
        trades = get_active_trades()
        for t in trades:
            if t[0] == symbol:
                cp = MARKET_CACHE.get(symbol, {}).get("price", t[1])
                import asyncio
                asyncio.create_task(execute_virtual_sell(symbol, cp, "Arayuz Manuel Satis"))
                return web.json_response({"status": "success", "message": f"{symbol} LONG pozisyonu kapatiliyor..."})
        return web.json_response({"status": "error", "message": "Acik pozisyon bulunamadi."})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)})

async def index_handler(request):

    return web.FileResponse(os.path.join(FRONTEND_DIR, 'index.html'))



async def daily_summary_reporter_bg():
    import asyncio
    import time
    from interfaces.telegram_bot import send_telegram_message
    from core.database import get_portfolio, get_active_trades
    
    last_report_date = ""
    while True:
        try:
            now = time.localtime()
            today_str = time.strftime("%Y-%m-%d", now)
            
            # Saat 18:15'i gecmisse ve bugun rapor atilmadiysa
            if now.tm_hour == 18 and now.tm_min >= 15 and last_report_date != today_str:
                cash, _ = get_portfolio()
                trades = get_active_trades()
                
                total_equity = float(cash)
                active_count = len(trades)
                
                # Toplam portfoy degeri hesabi
                for t in trades:
                    sym = t[0]
                    bp = float(t[1])
                    lots = int(t[3])
                    cp = MARKET_CACHE.get(sym, {}).get("price", bp)
                    if cp == 0: cp = bp
                    total_equity += (cp * lots)
                
                daily_profit = total_equity - 12000.0  # Baslangic sermayesine gore
                profit_pct = (daily_profit / 12000.0) * 100
                
                msg = (
                    "📊 <b>BorsaAI Gün Sonu Raporu</b>\n"
                    f"Tarih: {today_str}\n\n"
                    f"Açık Pozisyon Sayısı: {active_count}\n"
                    f"Kasa Nakit: {cash:.2f} TL\n"
                    f"Toplam Varlık: {total_equity:.2f} TL\n\n"
                    f"💰 Kümülatif K/Z: {daily_profit:.2f} TL (%{profit_pct:.2f})"
                )
                
                await asyncio.to_thread(send_telegram_message, msg)
                last_report_date = today_str
                
            await asyncio.sleep(60) # Her dakika kontrol et
        except Exception as e:
            print("Daily Report Error:", e)
            await asyncio.sleep(60)

async def start_mini_app_server():

    app = web.Application()

    app.router.add_post('/api/webhook/tv', handle_tradingview_webhook)

    app.router.add_get('/api/data', api_data)

    app.router.add_get('/api/performance', api_performance)

    app.router.add_get('/api/market', api_market)

    app.router.add_get('/api/history', api_history)

    app.router.add_post('/api/sell', api_sell)

    app.router.add_get('/', index_handler)

    if os.path.exists(FRONTEND_DIR):

        app.router.add_static('/', FRONTEND_DIR)

    port = int(os.environ.get("PORT", 8080))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    asyncio.create_task(process_signal_queue())
    asyncio.create_task(portfolio_monitor_bg())
    asyncio.create_task(daily_summary_reporter_bg())
    log_event("MINI_APP", f"Telegram Mini App sunucusu {port} portunda basladi.")

    while True:

        await asyncio.sleep(3600)