import asyncio
import sys
import os
import signal
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.database import init_db
from core.utils import log_event
from interfaces.telegram_bot import telegram_bot_listener
from interfaces.mini_app import start_mini_app_server
from simulator.risk_manager import run_risk_manager

IS_RUNNING = True

def handle_exit(sig, frame):
    global IS_RUNNING
    log_event("SYSTEM", "Shutdown signal received. Terminating processes safely.", level="WARNING")
    IS_RUNNING = False

def is_running():
    return IS_RUNNING

async def main():
    init_db()
    log_event("SYSTEM", "System initialized. Starting background processes.")
    
    # 3 gorevi paralel calistir: Telegram, Webhook(TV), Risk Yoneticisi
    await asyncio.gather(
        telegram_bot_listener(),
        start_mini_app_server(),
        run_risk_manager(is_running)
    )

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    
    # Python asyncio motorunu baslat
    asyncio.run(main())
