import sys
import os
from decimal import Decimal, ROUND_DOWN
from typing import Optional, List

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from core.models import Signal, SignalType, Portfolio, Trade
from core.utils import log_event

# ---------------------------------------------------------
# SYSTEM: ORDER ROUTER
# Processes trading signals and calculates execution parameters
# including slippage and commissions.
# ---------------------------------------------------------

def execute_virtual_order(signal: Signal, portfolio: Portfolio, current_price: Decimal, active_symbols: List[str]) -> Optional[Trade]:
    """Executes a virtual BUY order based on the given signal and portfolio constraints."""
    
    if signal.signal_type != SignalType.BUY:
        return None
        
    if current_price <= 0:
        return None
        
    # GUARD: Prevent duplicate positions for the same symbol
    if signal.symbol in active_symbols:
        log_event("ORDER_ROUTER", f"Duplicate buy order rejected for {signal.symbol}.")
        return None
        
    log_event("ORDER_ROUTER", f"Initiating buy order for {signal.symbol} at {current_price} TRY.")
    
    # 1. Apply Slippage
    slippage_price = current_price * Decimal(str(1 + portfolio.slippage_percent))
    
    # 2. Risk Management: Cap allocation per trade
    max_trade_amount = portfolio.cash_balance * Decimal('0.25')
    
    # 3. Lot Calculation (Round down)
    lot_amount = int((max_trade_amount / slippage_price).to_integral_value(rounding=ROUND_DOWN))
    
    if lot_amount <= 0:
        log_event("ORDER_ROUTER", f"Insufficient funds for {signal.symbol} (calculated 0 lots).")
        return None
        
    # 4. Cost and Commission Calculation
    brut_maliyet = slippage_price * Decimal(str(lot_amount))
    komisyon = brut_maliyet * Decimal(str(portfolio.commission_rate))
    net_maliyet = brut_maliyet + komisyon
    
    if net_maliyet > portfolio.cash_balance:
        log_event("ORDER_ROUTER", f"Insufficient funds for {signal.symbol} after commission calculation.")
        return None
        
    # 5. Update Portfolio and Record Trade
    portfolio.cash_balance -= net_maliyet
    
    yeni_islem = Trade(
        symbol=signal.symbol,
        buy_price=slippage_price,
        lot_amount=lot_amount
    )
    
    log_event("ORDER_ROUTER", f"Buy order executed: {lot_amount} lots of {signal.symbol}. Total cost: {net_maliyet:.2f} TRY.")
    
    return yeni_islem

def execute_virtual_sell(signal: Signal, portfolio: Portfolio, current_price: Decimal, full_active_trades: list) -> dict:
    """Executes a virtual SELL order for an existing position and calculates PnL."""
    if signal.signal_type != SignalType.SELL:
        return None
        
    if current_price <= 0:
        return None
        
    # GUARD: Ensure position exists (no short selling)
    target_trade = next((t for t in full_active_trades if t[0] == signal.symbol), None)
    if not target_trade:
        return None
        
    symbol, buy_price, lot_amount, buy_time = target_trade
    buy_price = Decimal(str(buy_price))
    
    log_event("ORDER_ROUTER", f"Initiating sell order for {symbol} at {current_price} TRY.")
    
    # 1. Apply Slippage
    slippage_price = current_price * Decimal(str(1 - portfolio.slippage_percent))
    
    # 2. Revenue and Commission Calculation
    brut_gelir = slippage_price * Decimal(str(lot_amount))
    komisyon = brut_gelir * Decimal(str(portfolio.commission_rate))
    net_gelir = brut_gelir - komisyon
    
    # 3. PnL Calculation
    maliyet = buy_price * Decimal(str(lot_amount))
    pnl = net_gelir - maliyet
    pnl_percent = (pnl / maliyet) * 100
    
    # 4. Update Portfolio Balance
    portfolio.cash_balance += net_gelir
    
    durum = "PROFIT" if pnl > 0 else "LOSS"
    log_event("ORDER_ROUTER", f"Sell order executed: {lot_amount} lots of {symbol}.")
    log_event("ORDER_ROUTER", f"Trade result: {pnl:.2f} TRY {durum} ({pnl_percent:.2f}%).")
    
    return {"symbol": symbol, "net_gelir": net_gelir, "pnl": pnl, "sell_price": float(slippage_price)}
