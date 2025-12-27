"""
Gamification Sistemi için Veritabanı Test ve Demo Verisi
"""

import sys
import os

# Proje kök dizinini path'e ekle
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.database.database import init_database, get_all_drivers, DB_PATH
from ai.gamification_helper import generate_sample_performance_data
import sqlite3

def setup_gamification():
    """Gamification sistemi için veritabanını hazırla"""
    print("=" * 60)
    print("🎮 GAMIFICATION SİSTEMİ KURULUMU")
    print("=" * 60)
    
    # Tabloları oluştur/güncelle
    print("\n1️⃣ Veritabanı tabloları oluşturuluyor...")
    init_database()
    
    # Şoförleri getir
    print("\n2️⃣ Şoförler alınıyor...")
    drivers = get_all_drivers()
    
    if not drivers:
        print("❌ Henüz şoför yok! Önce şoför oluşturun.")
        return
    
    print(f"✅ {len(drivers)} şoför bulundu")
    
    # Her şoför için örnek performans verisi oluştur
    print("\n3️⃣ Örnek performans verisi oluşturuluyor...")
    for driver in drivers:
        print(f"   📊 {driver['full_name']} (ID: {driver['id']}) için veri oluşturuluyor...")
        generate_sample_performance_data(driver['id'], days=14)
    
    print("\n" + "=" * 60)
    print("✅ GAMIFICATION SİSTEMİ BAŞARIYLA KURULDU!")
    print("=" * 60)
    
    # Özet bilgi
    print("\n📋 ÖZET:")
    print("-" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Toplam performans kaydı
    cursor.execute('SELECT COUNT(*) as count FROM driver_performance')
    perf_count = cursor.fetchone()['count']
    print(f"• Toplam performans kaydı: {perf_count}")
    
    # Toplam başarı
    cursor.execute('SELECT COUNT(*) as count FROM driver_achievements')
    ach_count = cursor.fetchone()['count']
    print(f"• Toplam rozet/başarı: {ach_count}")
    
    # En yüksek puanlı şoför
    cursor.execute('''
        SELECT u.full_name, AVG(dp.total_score) as avg_score
        FROM users u
        JOIN driver_performance dp ON u.id = dp.driver_id
        WHERE u.role = 'surucu'
        GROUP BY u.id
        ORDER BY avg_score DESC
        LIMIT 1
    ''')
    top_driver = cursor.fetchone()
    if top_driver:
        print(f"• En yüksek puan: {top_driver['full_name']} - {top_driver['avg_score']:.1f}")
    
    conn.close()
    
    print("\n🚀 Sistem kullanıma hazır!")
    print("📍 URL: http://localhost:5000/driver/performance")
    print("-" * 60)

if __name__ == '__main__':
    setup_gamification()
