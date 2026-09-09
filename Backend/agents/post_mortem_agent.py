import sqlite3
import os
import json
from google import genai
from google.genai import types

def run_post_mortem():
    print("[POST-MORTEM] Öz-Öğrenme modülü başlatıldı...")
    
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core', 'borsa_memory.db')
    if not os.path.exists(db_path):
        print(f"[POST-MORTEM] Veritabanı bulunamadı: {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Sadece zarar eden işlemleri çekiyoruz (pnl < 0)
        cursor.execute("SELECT symbol, buy_price, sell_price, pnl, reason, buy_time, sell_time FROM trade_history WHERE pnl < 0")
        losing_trades = cursor.fetchall()
    except Exception as e:
        print(f"[POST-MORTEM] Veritabanı okunurken hata: {e}")
        return
    finally:
        conn.close()
        
    if not losing_trades:
        print("[POST-MORTEM] Analiz edilecek zarar işlemi bulunamadı. Harika!")
        return
        
    prompt = "Aşağıda kuantitatif işlem botumun zarar ile kapattığı son işlemlerin bir listesi var. Bir finansal mühendis ve analist olarak bu işlemleri incele. Acaba bot hangi hisselerde, hangi saat dilimlerinde veya hangi sebeplerle hata yapıyor olabilir? Hangi sektörel eğilimlerden kaçınmalıyım? Gelecekte aynı hataları yapmamam için bana 3 net 'Alınan Ders' (Lesson Learned) çıkar.\n\nİşlemler:\n"
    for t in losing_trades:
        prompt += f"- Hisse: {t[0]}, Alış: {t[1]}, Satış: {t[2]}, Zarar: {t[3]}, Sebep: {t[4]}, Alış Zamanı: {t[5]}, Satış Zamanı: {t[6]}\n"
        
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("[POST-MORTEM] GEMINI_API_KEY bulunamadı.")
            return
            
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
        )
        
        analysis = response.text
        
        # Sonucu JSON olarak kaydet
        lessons_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'lessons_learned.json')
        data = {"last_analysis_time": t[6], "analysis": analysis, "total_losses_analyzed": len(losing_trades)}
        
        with open(lessons_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        print("[POST-MORTEM] Analiz tamamlandı ve lessons_learned.json dosyasına kaydedildi.")
        
    except Exception as e:
        print(f"[POST-MORTEM] Gemini API hatası: {e}")

if __name__ == "__main__":
    run_post_mortem()
