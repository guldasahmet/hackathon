"""
Gamification Yardımcı Modülü
Performans hesaplama ve rozet yönetimi
"""

import sqlite3
from datetime import datetime, timedelta
from backend.database.database import DB_PATH

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# =============================================================================
# PERFORMANS HESAPLAMA FONKSİYONLARI
# =============================================================================

def calculate_route_score(planned_km, actual_km, max_score=30):
    """
    Rota uyumu puanı hesapla
    
    Kriterler:
    - %5'den az sapma: 30 puan
    - %10'dan az sapma: 20 puan
    - %15'ten az sapma: 10 puan
    - %15'ten fazla: Azalan puan
    """
    if not planned_km or not actual_km or planned_km <= 0:
        return 0, 0
    
    deviation_km = abs(actual_km - planned_km)
    deviation_ratio = deviation_km / planned_km
    
    if deviation_ratio <= 0.05:
        score = max_score
    elif deviation_ratio <= 0.10:
        score = max_score * 0.67  # 20 puan
    elif deviation_ratio <= 0.15:
        score = max_score * 0.33  # 10 puan
    else:
        # Her %1 fazla sapma için 0.5 puan kaybı
        penalty = (deviation_ratio - 0.15) * 50
        score = max(0, (max_score * 0.33) - penalty)
    
    return round(score, 2), round(deviation_km, 2)

def calculate_time_score(planned_hours, actual_hours, max_score=25):
    """
    Zamanında tamamlama puanı
    
    Kriterler:
    - Planlanan sürede veya daha erken: 25 puan
    - %10'a kadar geç: 15 puan
    - %20'ye kadar geç: 5 puan
    - %20'den fazla: 0 puan
    """
    if not planned_hours or not actual_hours or planned_hours <= 0:
        return 0
    
    if actual_hours <= planned_hours:
        score = max_score
    elif actual_hours <= planned_hours * 1.10:
        score = max_score * 0.60  # 15 puan
    elif actual_hours <= planned_hours * 1.20:
        score = max_score * 0.20  # 5 puan
    else:
        score = 0
    
    return round(score, 2)

def calculate_fuel_score(expected_lt, actual_lt, max_score=25):
    """
    Yakıt verimliliği puanı
    
    Kriterler:
    - %10+ tasarruf: 25 puan
    - Normal tüketim (0-10% fazla): 20 puan
    - %10-20 fazla: 10 puan
    - %20'den fazla: 0 puan
    """
    if not expected_lt or not actual_lt or expected_lt <= 0:
        return 0, 0
    
    fuel_saved_lt = expected_lt - actual_lt
    fuel_ratio = actual_lt / expected_lt
    
    if fuel_ratio <= 0.90:  # %10+ tasarruf
        score = max_score
    elif fuel_ratio <= 1.00:  # Normal
        score = max_score * 0.80  # 20 puan
    elif fuel_ratio <= 1.10:  # %10 fazla
        score = max_score * 0.40  # 10 puan
    else:
        score = 0
    
    return round(score, 2), round(fuel_saved_lt, 2)

def calculate_tonnage_score(target_ton, collected_ton, max_score=20):
    """
    Toplanan tonaj puanı
    
    Kriterler:
    - %95+ hedef: 20 puan
    - %90-95: 15 puan
    - %85-90: 10 puan
    - %85'in altı: Oransal puan
    """
    if not target_ton or not collected_ton or target_ton <= 0:
        return 0
    
    collection_ratio = collected_ton / target_ton
    
    if collection_ratio >= 0.95:
        score = max_score
    elif collection_ratio >= 0.90:
        score = max_score * 0.75  # 15 puan
    elif collection_ratio >= 0.85:
        score = max_score * 0.50  # 10 puan
    else:
        score = max(0, collection_ratio * max_score * 0.50)
    
    return round(score, 2)

def calculate_total_performance(data):
    """
    Tüm performans metriklerini hesapla
    
    Args:
        data: {
            planned_distance_km, actual_distance_km,
            planned_duration_hours, actual_duration_hours,
            expected_fuel_lt, actual_fuel_lt,
            target_tonnage, collected_tonnage
        }
    
    Returns:
        scores: {
            route_score, time_score, fuel_score, tonnage_score,
            total_score, route_deviation_km, fuel_saved_lt
        }
    """
    route_score, route_deviation_km = calculate_route_score(
        data.get('planned_distance_km'),
        data.get('actual_distance_km')
    )
    
    time_score = calculate_time_score(
        data.get('planned_duration_hours'),
        data.get('actual_duration_hours')
    )
    
    fuel_score, fuel_saved_lt = calculate_fuel_score(
        data.get('expected_fuel_lt'),
        data.get('actual_fuel_lt')
    )
    
    tonnage_score = calculate_tonnage_score(
        data.get('target_tonnage'),
        data.get('collected_tonnage')
    )
    
    total_score = route_score + time_score + fuel_score + tonnage_score
    
    return {
        'route_score': route_score,
        'time_score': time_score,
        'fuel_score': fuel_score,
        'tonnage_score': tonnage_score,
        'total_score': round(total_score, 2),
        'route_deviation_km': route_deviation_km,
        'fuel_saved_lt': fuel_saved_lt
    }

# =============================================================================
# SEVİYE VE PUAN HESAPLAMA
# =============================================================================

def get_tier_from_score(avg_score):
    """
    Puana göre seviye belirle
    
    Returns:
        {
            'tier': 'gold'|'silver'|'bronze'|'rookie',
            'tier_name': '🥇 Altın Şoför',
            'bonus_percentage': 15,
            'color': '#FFD700'
        }
    """
    if avg_score >= 95:
        return {
            'tier': 'gold',
            'tier_name': '🥇 Altın Şoför',
            'bonus_percentage': 15,
            'color': '#FFD700',
            'icon': '🥇'
        }
    elif avg_score >= 85:
        return {
            'tier': 'silver',
            'tier_name': '🥈 Gümüş Şoför',
            'bonus_percentage': 10,
            'color': '#C0C0C0',
            'icon': '🥈'
        }
    elif avg_score >= 75:
        return {
            'tier': 'bronze',
            'tier_name': '🥉 Bronz Şoför',
            'bonus_percentage': 5,
            'color': '#CD7F32',
            'icon': '🥉'
        }
    else:
        return {
            'tier': 'rookie',
            'tier_name': '🚛 Çaylak',
            'bonus_percentage': 0,
            'color': '#808080',
            'icon': '🚛'
        }

def calculate_bonus_amount(avg_score, base_salary=20000):
    """
    Puana göre prim miktarını hesapla
    
    Args:
        avg_score: Ortalama puan (0-100)
        base_salary: Maaş (TL)
    
    Returns:
        bonus_amount: Prim (TL)
    """
    tier_info = get_tier_from_score(avg_score)
    bonus_percentage = tier_info['bonus_percentage']
    bonus_amount = (base_salary * bonus_percentage) / 100
    
    return round(bonus_amount, 2)

# =============================================================================
# BAŞARI KONTROLÜ
# =============================================================================

def check_streak_achievement(driver_id, current_date, min_score=85, streak_days=5):
    """
    Seri başarı kontrolü (ardışık gün)
    
    Returns:
        bool: Başarı kazanıldı mı?
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # Son N gün kontrolü
    cursor.execute('''
        SELECT COUNT(*) as streak_count
        FROM driver_performance
        WHERE driver_id = ?
        AND date >= date(?, '-{} days')
        AND date <= ?
        AND total_score >= ?
    '''.format(streak_days - 1), (driver_id, current_date, current_date, min_score))
    
    result = cursor.fetchone()
    conn.close()
    
    return result['streak_count'] >= streak_days

def check_weekly_star(driver_id, week_start_date):
    """
    Haftalık yıldız kontrolü (haftanın en yüksek puanı)
    
    Returns:
        bool: Bu şoför haftanın birincisi mi?
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.id, AVG(dp.total_score) as avg_score
        FROM users u
        JOIN driver_performance dp ON u.id = dp.driver_id
        WHERE u.role = 'surucu'
        AND dp.date >= ?
        AND dp.date < date(?, '+7 days')
        GROUP BY u.id
        ORDER BY avg_score DESC
        LIMIT 1
    ''', (week_start_date, week_start_date))
    
    winner = cursor.fetchone()
    conn.close()
    
    return winner and winner['id'] == driver_id

def check_eco_hero(driver_id, period_days=7):
    """
    Eko Kahraman kontrolü (en düşük yakıt tüketimi)
    
    Returns:
        bool: En düşük yakıt tüketimi mi?
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.id, SUM(dp.fuel_saved_lt) as total_saved
        FROM users u
        JOIN driver_performance dp ON u.id = dp.driver_id
        WHERE u.role = 'surucu'
        AND dp.date >= date('now', '-{} days')
        GROUP BY u.id
        ORDER BY total_saved DESC
        LIMIT 1
    '''.format(period_days), ())
    
    winner = cursor.fetchone()
    conn.close()
    
    return winner and winner['id'] == driver_id

def award_achievement(driver_id, achievement_type, achievement_name, description, icon):
    """
    Başarı ödülü ver
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO driver_achievements (
            driver_id, achievement_type, achievement_name, description, icon
        ) VALUES (?, ?, ?, ?, ?)
    ''', (driver_id, achievement_type, achievement_name, description, icon))
    
    conn.commit()
    conn.close()

# =============================================================================
# HAFTALIK ÖZET HESAPLAMA
# =============================================================================

def calculate_weekly_stats(driver_id, week_start_date):
    """
    Haftalık performans özeti hesapla
    
    Returns:
        {
            days_worked, avg_score, total_score, rank, bonus_amount, bonus_percentage
        }
    """
    conn = get_db()
    cursor = conn.cursor()
    
    week_end_date = (datetime.strptime(week_start_date, '%Y-%m-%d') + timedelta(days=6)).strftime('%Y-%m-%d')
    
    # Bu şoförün haftalık performansı
    cursor.execute('''
        SELECT 
            COUNT(*) as days_worked,
            AVG(total_score) as avg_score,
            SUM(total_score) as total_score
        FROM driver_performance
        WHERE driver_id = ?
        AND date >= ?
        AND date <= ?
    ''', (driver_id, week_start_date, week_end_date))
    
    stats = dict(cursor.fetchone())
    
    # Tüm şoförlerin sıralaması
    cursor.execute('''
        SELECT u.id, AVG(dp.total_score) as avg_score
        FROM users u
        JOIN driver_performance dp ON u.id = dp.driver_id
        WHERE u.role = 'surucu'
        AND dp.date >= ?
        AND dp.date <= ?
        GROUP BY u.id
        ORDER BY avg_score DESC
    ''', (week_start_date, week_end_date))
    
    all_drivers = cursor.fetchall()
    rank = 1
    for driver in all_drivers:
        if driver['id'] == driver_id:
            stats['rank'] = rank
            break
        rank += 1
    
    # Prim hesapla
    avg_score = stats['avg_score'] or 0
    tier_info = get_tier_from_score(avg_score)
    stats['bonus_percentage'] = tier_info['bonus_percentage']
    stats['bonus_amount'] = calculate_bonus_amount(avg_score)
    stats['tier'] = tier_info['tier']
    stats['tier_name'] = tier_info['tier_name']
    
    conn.close()
    
    return stats

# =============================================================================
# VERİ OLUŞTURMA (TEST/DEMO)
# =============================================================================

def generate_sample_performance_data(driver_id, days=7):
    """
    Test için örnek performans verisi oluştur
    """
    import random
    
    conn = get_db()
    cursor = conn.cursor()
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        
        # Rastgele ama gerçekçi değerler
        planned_distance = 50 + random.uniform(-10, 20)
        actual_distance = planned_distance + random.uniform(-5, 8)
        
        planned_duration = 4 + random.uniform(-0.5, 1)
        actual_duration = planned_duration + random.uniform(-0.3, 0.8)
        
        expected_fuel = planned_distance * 0.35  # ~35L/100km
        actual_fuel = expected_fuel + random.uniform(-5, 8)
        
        target_tonnage = 8 + random.uniform(-1, 2)
        collected_tonnage = target_tonnage * random.uniform(0.85, 1.05)
        
        data = {
            'planned_distance_km': planned_distance,
            'actual_distance_km': actual_distance,
            'planned_duration_hours': planned_duration,
            'actual_duration_hours': actual_duration,
            'expected_fuel_lt': expected_fuel,
            'actual_fuel_lt': actual_fuel,
            'target_tonnage': target_tonnage,
            'collected_tonnage': collected_tonnage
        }
        
        scores = calculate_total_performance(data)
        
        cursor.execute('''
            INSERT OR REPLACE INTO driver_performance (
                driver_id, date, route_score, time_score, fuel_score, tonnage_score,
                total_score, route_deviation_km, fuel_saved_lt,
                planned_distance_km, actual_distance_km,
                planned_duration_hours, actual_duration_hours,
                expected_fuel_lt, actual_fuel_lt,
                target_tonnage, collected_tonnage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            driver_id, date,
            scores['route_score'], scores['time_score'], scores['fuel_score'], scores['tonnage_score'],
            scores['total_score'], scores['route_deviation_km'], scores['fuel_saved_lt'],
            data['planned_distance_km'], data['actual_distance_km'],
            data['planned_duration_hours'], data['actual_duration_hours'],
            data['expected_fuel_lt'], data['actual_fuel_lt'],
            data['target_tonnage'], data['collected_tonnage']
        ))
    
    conn.commit()
    conn.close()
    
    print(f"✅ {driver_id} için {days} günlük örnek veri oluşturuldu")
