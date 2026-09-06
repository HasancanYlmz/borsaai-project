"""
BORSA AI - GERCEK ENTEGRASYON VE STRES TESTI
200 Varyasyonlu kapsamli sistem testi.
Calistirmak icin: py Backend/tests/integration_test.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from decimal import Decimal
import random

errors = []
passed = 0

def ok(msg):
    global passed
    passed += 1
    print(f"  [GECTI] {msg}")

def fail(module, msg):
    errors.append(f"{module}: {msg}")
    print(f"  [HATA]  {module}: {msg}")

print("=" * 55)
print("  BORSA AI - TAM ENTEGRASYON + 200 VARYASYON TESTI")
print("=" * 55)

# ----------------------------------------------------------------
# 1. MODELS
# ----------------------------------------------------------------
print("\n[1] CORE MODELS")
try:
    from core.models import Signal, SignalType, RegimeType, AKDData, Portfolio, Trade
    p = Portfolio(id=1, cash_balance=Decimal("10000"), total_equity=Decimal("10000"))
    assert p.id == 1
    assert p.commission_rate == 0.0004
    assert p.slippage_percent == 0.001
    ok("Portfolio - id, komisyon, slippage alanlari tamam")
except Exception as e:
    fail("models.py", str(e))

# ----------------------------------------------------------------
# 2. DATABASE FONKSIYONLARI
# ----------------------------------------------------------------
print("\n[2] DATABASE")
try:
    from core.database import (init_db, get_portfolio, get_active_symbols,
                                get_active_trades, remove_trade, save_trade,
                                save_signal, update_portfolio_cash)
    ok("Tum database fonksiyonlari import edildi")
except Exception as e:
    fail("database.py", str(e))

# ----------------------------------------------------------------
# 3. UTILS + SAAT KONTROLU
# ----------------------------------------------------------------
print("\n[3] UTILS & PIYASA SAATI")
try:
    from core.utils import log_event, get_ist_time
    from datetime import time as dt_time
    now = get_ist_time()
    is_weekend = now.weekday() >= 5
    is_open = not is_weekend and (dt_time(9, 55) <= now.time() <= dt_time(18, 10))
    gun = ["Pzt","Sal","Car","Per","Cum","Cmt","Paz"][now.weekday()]
    durum = "ACIK" if is_open else "KAPALI"
    ok(f"get_ist_time() -> {gun} {now.strftime('%H:%M')} | Borsa: {durum}")
except Exception as e:
    fail("utils.py", str(e))

# ----------------------------------------------------------------
# 4. SIGNAL GENERATOR - 3 SENARYO
# ----------------------------------------------------------------
print("\n[4] SIGNAL GENERATOR")
try:
    from core.signal_generator import generate_signal
    for karar, beklenen in [("AL", "AL"), ("SAT", "SAT"), ("TUT", "TUT")]:
        sig = generate_signal({"symbol": "TEST", "score": 80, "decision": karar,
                               "reasons": "test", "regime": "YATAY"})
        assert sig.signal_type.value == beklenen, f"{karar} -> {sig.signal_type.value}"
    ok("AL / SAT / TUT uclu senaryo basarili")
except Exception as e:
    fail("signal_generator.py", str(e))

# ----------------------------------------------------------------
# 5. DOMINANCE - 4 SENARYO
# ----------------------------------------------------------------
print("\n[5] DOMINANCE (AKD & SPOOFING)")
try:
    from quant.dominance import detect_spoofing_and_dominance

    # 5a. Kurumsal Alim
    akd = AKDData(symbol="X", top_buyer="BOFA", top_buyer_lot=300000,
                  top_seller="YF", top_seller_lot=50000, net_difference=250000)
    r = detect_spoofing_and_dominance(akd)
    assert "ALIM" in r["verdict"].upper() or r["buyer_dominance_pct"] > 40
    ok("Kurumsal ALIM senaryosu")

    # 5b. Kurumsal Satis
    akd2 = AKDData(symbol="X", top_buyer="A", top_buyer_lot=20000,
                   top_seller="BOFA", top_seller_lot=300000, net_difference=-280000)
    r2 = detect_spoofing_and_dominance(akd2)
    assert "SATIS" in r2["verdict"].upper() or "SPOOFING" in r2["verdict"].upper() or r2["seller_dominance_pct"] > 40
    ok("Kurumsal SATIS senaryosu")

    # 5c. Hacimsiz tahta - verdict ne olursa olsun dominance_pct 0 olmali
    akd3 = AKDData(symbol="X", top_buyer="A", top_buyer_lot=0,
                   top_seller="B", top_seller_lot=0, net_difference=0)
    r3 = detect_spoofing_and_dominance(akd3)
    assert r3["dominance_pct"] == 0 and not r3["is_spoofing_suspected"]
    ok("Hacimsiz tahta senaryosu")

    # 5d. Notr tahta
    akd4 = AKDData(symbol="X", top_buyer="A", top_buyer_lot=100000,
                   top_seller="B", top_seller_lot=80000, net_difference=20000)
    r4 = detect_spoofing_and_dominance(akd4)
    assert not r4["is_spoofing_suspected"]
    ok("Notr tahta senaryosu")
except Exception as e:
    fail("dominance.py", str(e))

# ----------------------------------------------------------------
# 6. COMMITTEE - 3 TEMEL SENARYO
# ----------------------------------------------------------------
print("\n[6] COMMITTEE (KARAR BEYNİ)")
try:
    from agents.committee import evaluate_stock_committee

    al_payload = {
        "tv_data": {"recommendation": "STRONG_BUY", "volume": 5000000, "close": 100},
        "rvol_data": {"momentum_score": 90, "regime": "RALLİ", "rvol_score": 3},
        "akd_data": {"verdict": "KURUMSAL_ALIM", "is_spoofing_suspected": False},
        "news_data": {"sentiment": "POZİTİF", "score": 80}
    }
    r_al = evaluate_stock_committee("TST", al_payload)
    assert r_al["decision"] == "AL", f"Beklenen AL, gelen: {r_al['decision']} (skor:{r_al['score']})"
    ok(f"AL senaryosu - Skor: {r_al['score']}")

    sat_payload = {
        "tv_data": {"recommendation": "SELL", "volume": 100000, "close": 50},
        "rvol_data": {"momentum_score": 0, "regime": "ÇÖKÜŞ", "rvol_score": 0.1},
        "akd_data": {"verdict": "NOTR", "is_spoofing_suspected": True},
        "news_data": {"sentiment": "NEGATİF", "score": 10}
    }
    r_sat = evaluate_stock_committee("TST", sat_payload)
    assert r_sat["decision"] == "SAT", f"Beklenen SAT, gelen: {r_sat['decision']} (skor:{r_sat['score']})"
    ok(f"SAT senaryosu - Skor: {r_sat['score']}")

    tut_payload = {
        "tv_data": {"recommendation": "BUY", "volume": 500000, "close": 75},
        "rvol_data": {"momentum_score": 0, "regime": "YATAY", "rvol_score": 1.0},
        "akd_data": {"verdict": "KURUMSAL_ALIM", "is_spoofing_suspected": False},
        "news_data": {"sentiment": "negatif", "score": 50}
    }
    # BUY=+10, KURUMSAL ALIM=+20, NEGATIF=-20 => skor=10 => SAT
    # Duzgun TUT icin: BUY=+10, KURUMSAL_ALIM=+20, haber=NÖTR => toplam=30+1 (yuvarlamadan 31=TUT)
    tut_payload2 = {
        "tv_data": {"recommendation": "BUY", "volume": 500000, "close": 75},
        "rvol_data": {"momentum_score": 3, "regime": "YATAY", "rvol_score": 1.0},
        "akd_data": {"verdict": "KURUMSAL_ALIM", "is_spoofing_suspected": False},
        "news_data": {"sentiment": "notr", "score": 50}
    }
    # BUY=+10, KURUMSAL_ALIM=+20, momentum=3*0.4=1.2 => ~31 => TUT
    r_tut = evaluate_stock_committee("TST", tut_payload2)
    assert r_tut["decision"] == "TUT", f"Beklenen TUT, gelen: {r_tut['decision']} (skor:{r_tut['score']})"
    ok(f"TUT senaryosu - Skor: {r_tut['score']}")
except Exception as e:
    fail("committee.py", str(e))

# ----------------------------------------------------------------
# 7. ORDER ROUTER - ALIS + SATIS + SPAM KORUMASI
# ----------------------------------------------------------------
print("\n[7] ORDER ROUTER (SIMULATOR)")
try:
    from simulator.order_router import execute_virtual_order, execute_virtual_sell

    buy_sig = generate_signal({"symbol": "THYAO", "score": 80, "decision": "AL",
                               "reasons": "test", "regime": "YATAY"})
    port = Portfolio(id=1, cash_balance=Decimal("10000"), total_equity=Decimal("10000"))

    # Normal alis
    trade = execute_virtual_order(buy_sig, port, Decimal("150.00"), [])
    assert trade is not None and trade.symbol == "THYAO"
    ok(f"Normal ALIS: {trade.lot_amount} lot @ {trade.buy_price} TL")

    # Spam koruması - ayni hisseyi tekrar alma
    spam = execute_virtual_order(buy_sig, port, Decimal("150.00"), ["THYAO"])
    assert spam is None
    ok("Spam (Cifte ALIS) korumasi calisiyor")

    # Yetersiz bakiye
    poor_port = Portfolio(id=1, cash_balance=Decimal("10"), total_equity=Decimal("10"))
    no_trade = execute_virtual_order(buy_sig, poor_port, Decimal("150.00"), [])
    assert no_trade is None
    ok("Yetersiz bakiye koruması calisiyor")

    # Satis - kar
    sell_sig = generate_signal({"symbol": "THYAO", "score": 10, "decision": "SAT",
                                "reasons": "test", "regime": "YATAY"})
    port2 = Portfolio(id=1, cash_balance=Decimal("8500"), total_equity=Decimal("10000"))
    result = execute_virtual_sell(sell_sig, port2, Decimal("165.00"), [("THYAO", 150.0, 10, "2024-01-01")])
    assert result is not None and result["pnl"] > 0
    ok(f"SATIS ile KAR: {float(result['pnl']):.2f} TL")

    # Satis - zarar
    result2 = execute_virtual_sell(sell_sig, port2, Decimal("130.00"), [("THYAO", 150.0, 10, "2024-01-01")])
    assert result2 is not None and result2["pnl"] < 0
    ok(f"SATIS ile ZARAR: {float(result2['pnl']):.2f} TL")

    # Elimizde olmayan hisseyi satma (Aciga satis yasak)
    no_sell = execute_virtual_sell(sell_sig, port2, Decimal("165.00"), [])
    assert no_sell is None
    ok("Aciga satis korumasi calisiyor")

except Exception as e:
    fail("order_router.py", str(e))

# ----------------------------------------------------------------
# 8. 200 RASTGELE VARYASYON STRES TESTI
# ----------------------------------------------------------------
print("\n[8] 200 VARYASYON STRES TESTI")
try:
    recs = ["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
    sentiments = ["POZİTİF", "NÖTR", "NEGATİF"]
    verdicts = ["KURUMSAL_ALIM", "NÖTR", "KURUMSAL_SATIŞ"]
    semboller = ["THYAO", "EREGL", "GARAN", "AKBNK", "TUPRS", "ASELS", "BIMAS", "ISCTR"]

    stres_hata = 0
    for i in range(200):
        try:
            payload = {
                "tv_data": {
                    "recommendation": random.choice(recs),
                    "volume": random.randint(0, 10_000_000),
                    "close": round(random.uniform(1.0, 1000.0), 2)
                },
                "rvol_data": {
                    "momentum_score": random.uniform(0, 100),
                    "regime": random.choice(["RALLİ", "YATAY", "ÇÖKÜŞ"]),
                    "rvol_score": random.uniform(0, 5)
                },
                "akd_data": {
                    "verdict": random.choice(verdicts),
                    "is_spoofing_suspected": random.choice([True, False])
                },
                "news_data": {
                    "sentiment": random.choice(sentiments),
                    "score": random.randint(0, 100)
                }
            }
            symbol = random.choice(semboller)
            res = evaluate_stock_committee(symbol, payload)

            # Skor 0-100 araliginda olmali
            assert 0 <= res["score"] <= 100, f"Skor sinir disi: {res['score']}"
            # Karar sadece AL/SAT/TUT olmali
            assert res["decision"] in ["AL", "SAT", "TUT"], f"Gecersiz karar: {res['decision']}"
            # Sembol kaybolmamali
            assert res["symbol"] == symbol

            # Sinyal + emir testi
            sig = generate_signal(res)
            cash = Decimal(str(round(random.uniform(500, 50000), 2)))
            price = Decimal(str(round(random.uniform(1.0, 1000.0), 2)))
            port = Portfolio(id=1, cash_balance=cash, total_equity=cash)
            execute_virtual_order(sig, port, price, [])

        except Exception as e:
            stres_hata += 1
            print(f"    Varyasyon {i+1} HATA: {e}")

    if stres_hata == 0:
        ok("200/200 varyasyon hatasiz tamamlandi!")
    else:
        fail("stres_testi", f"{stres_hata}/200 varyasyon hatali!")

except Exception as e:
    fail("stres_testi", str(e))

# ----------------------------------------------------------------
# 9. MAIN.PY SYNTAX KONTROLU
# ----------------------------------------------------------------
print("\n[9] MAIN.PY SYNTAX")
try:
    import ast
    with open("Backend/main.py", "r", encoding="utf-8") as f:
        ast.parse(f.read())
    ok("main.py syntax hatasi yok")
except Exception as e:
    fail("main.py", str(e))

# ----------------------------------------------------------------
# SONUC
# ----------------------------------------------------------------
print()
print("=" * 55)
if errors:
    print(f"SONUC: {len(errors)} KRITIK HATA BULUNDU!")
    for e in errors:
        print(f"  -> {e}")
    sys.exit(1)
else:
    print(f"SONUC: {passed} TEST GECTI | 200 VARYASYON HATASIZ!")
    print("SISTEM KALKISA HAZIR. Yarin 09:55'te motoru calistirin.")
print("=" * 55)
