import random
import string
import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from sensors.yahoo_finance import get_market_context, calculate_dynamic_rvol
from agents.committee import evaluate_stock_committee
from agents.fundamental_agent import analyze_news_with_ai
from agents.risk_agent import evaluate_trade_risk
from agents.dominance import detect_spoofing_and_dominance
from core.signal_generator import generate_signal
from simulator.order_router import execute_virtual_order
from core.database import init_db, save_trade, get_active_symbols, update_portfolio_cash, get_portfolio

# Initialize DB (creates tables, seed cash)
init_db()

def random_symbol():
    return ''.join(random.choices(string.ascii_uppercase, k=4))

def random_volume():
    return random.uniform(1000, 5_000_000)

def random_price():
    return Decimal(str(random.uniform(1, 500)))

def random_akd():
    class AKD:
        def __init__(self, symbol):
            self.symbol = symbol
            self.top_buyer = 'BANK' + str(random.randint(1, 5))
            self.top_buyer_lot = random.randint(1000, 50000)
            self.top_seller = 'BANK' + str(random.randint(6, 9))
            self.top_seller_lot = random.randint(1000, 50000)
            self.net_difference = random.randint(-100000, 100000)
    return AKD(random_symbol())

def random_news():
    sentiments = ['POZİTİF', 'NEGATİF', 'NÖTR']
    # simple mock: empty list triggers NÖTR
    if random.random() < 0.3:
        return []
    else:
        # generate dummy strings containing some keywords
        positive = ['kar', 'büyüme', 'rekor']
        negative = ['zarar', 'dava', 'ceza']
        words = []
        for _ in range(random.randint(1, 3)):
            if random.random() < 0.5:
                words.append(random.choice(positive))
            else:
                words.append(random.choice(negative))
        return [' '.join(words)]

passed = 0
failed = 0
for i in range(200):
    try:
        symbol = random_symbol()
        # 1. market context (may be None if Yahoo fails, that's ok)
        context = get_market_context(symbol)
        if context:
            rvol_info = calculate_dynamic_rvol(symbol, random_volume())
        else:
            rvol_info = {'rvol_score': 0, 'regime': 'YATAY', 'is_buyable': False}
        akd = random_akd()
        akd_res = detect_spoofing_and_dominance(akd)
        news = random_news()
        news_res = analyze_news_with_ai(symbol, news)
        payload = {
            'tv_data': {'recommendation': random.choice(['BUY', 'BUY_STRONG', 'SELL', 'NEUTRAL'])},
            'rvol_data': rvol_info,
            'akd_data': akd_res,
            'news_data': news_res
        }
        committee = evaluate_stock_committee(symbol, payload)
        signal = generate_signal(committee, is_brut_takas=False)
        # portfolio handling
        cash, equity = get_portfolio()
        # simulate price
        price = random_price()
        # active symbols list from DB
        active = get_active_symbols()
        trade = execute_virtual_order(signal, type('Obj',(object,),{'cash_balance':cash,'slippage_percent':0.001,'commission_rate':0.0004})(), price, active)
        if trade:
            # store trade and update cash manually (the function already does cash update, but we simulate)
            save_trade(trade.symbol, trade.buy_price, trade.lot_amount)
            # update cash in DB (we don't have full Portfolio object here, skip)
        passed += 1
    except Exception as e:
        print(f"[FAIL] iteration {i}: {e}")
        failed += 1

print(f"Stress test completed: {passed} passed, {failed} failed.")
