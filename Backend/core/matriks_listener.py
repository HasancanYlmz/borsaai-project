import asyncio
import json
from core.database import log_event

_MARKET_MEMORY = {}

async def handle_matriks_client(reader, writer):
    addr = writer.get_extra_info('peername')
    log_event("MATRIKS", f"Matriks IQ Terminali baglandi: {addr}")
    
    try:
        while True:
            data = await reader.readline()
            if not data:
                break
                
            try:
                payload = json.loads(data.decode('utf-8'))
                symbol = payload.get("symbol")
                if symbol:
                    if symbol not in _MARKET_MEMORY:
                        _MARKET_MEMORY[symbol] = {}
                    _MARKET_MEMORY[symbol]["matriks_live"] = payload
            except json.JSONDecodeError:
                pass
    except Exception as e:
        log_event("MATRIKS_ERROR", f"Baglanti koptu: {e}", level="ERROR")
    finally:
        log_event("MATRIKS", f"Matriks IQ baglantisi kapatildi: {addr}")
        writer.close()
        await writer.wait_closed()

async def start_matriks_listener(global_memory_ref):
    global _MARKET_MEMORY
    _MARKET_MEMORY = global_memory_ref
    server = await asyncio.start_server(handle_matriks_client, '127.0.0.1', 9090)
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    log_event("MATRIKS_SERVER", f"Matriks Dinleme Istasyonu aktif. {addrs} uzerinden veri bekleniyor...")
    async with server:
        await server.serve_forever()
