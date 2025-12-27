"""
Mock başarılar ekle
"""

import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.database.database import DB_PATH
import sqlite3
from datetime import datetime, timedelta
import random

def add_mock_achievements():
    """Örnek başarı rozetleri ekle"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Şoförleri al
    cursor.execute('SELECT id, full_name FROM users WHERE role = "surucu"')
    drivers = cursor.fetchall()
    
    achievements = [
        ('gold', '🥇 Altın Şoför', 'Mükemmel performans - 95+ puan'),
        ('silver', '🥈 Gümüş Şoför', 'Harika performans - 85+ puan'),
        ('bronze', '🥉 Bronz Şoför', 'İyi performans - 75+ puan'),
        ('streak', '🔥 Seri Başarı', '5 gün üst üste 85+ puan'),
        ('eco_hero', '🌿 Eko Kahraman', 'En düşük yakıt tüketimi'),
        ('route_master', '🎯 Rota Ustası', 'Rotaya %98+ uyum')
    ]
    
    for driver_id, driver_name in drivers:
        # Her şoföre rastgele 3-6 rozet
        num_achievements = random.randint(3, min(6, len(achievements)))
        selected = random.sample(achievements, num_achievements)
        
        for ach_type, ach_name, ach_desc in selected:
            # Son 14 gün içinde rastgele tarih
            days_ago = random.randint(0, 14)
            earned_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT INTO driver_achievements 
                (driver_id, achievement_type, achievement_name, description, icon, earned_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (driver_id, ach_type, ach_name, ach_desc, ach_name.split()[0], earned_date))
    
    conn.commit()
    
    # Özet
    cursor.execute('SELECT COUNT(*) FROM driver_achievements')
    total = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"✅ {total} adet rozet eklendi!")
    print(f"✅ Her şoför için 3-7 arası rozet oluşturuldu")

if __name__ == '__main__':
    add_mock_achievements()
