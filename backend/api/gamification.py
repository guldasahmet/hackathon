"""
Gamification API - Şoför Ödül/Puan Sistemi
"""

from flask import jsonify, request
import sqlite3
from datetime import datetime, timedelta
from backend.database.database import DB_PATH
from . import gamification_bp

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# =============================================================================
# PERFORMANS KAYIT VE GÜNCELLEME
# =============================================================================

@gamification_bp.route('/performance/record', methods=['POST'])
def record_performance():
    """
    Şoför günlük performans kaydı
    Body: {
        driver_id, date, planned_distance_km, actual_distance_km,
        planned_duration_hours, actual_duration_hours,
        expected_fuel_lt, actual_fuel_lt,
        target_tonnage, collected_tonnage
    }
    """
    data = request.json
    
    required_fields = ['driver_id', 'date']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Eksik veri'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Puanları hesapla
    scores = calculate_scores(data)
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO driver_performance (
                driver_id, date, route_score, time_score, fuel_score, tonnage_score, total_score,
                route_deviation_km, fuel_saved_lt,
                planned_distance_km, actual_distance_km,
                planned_duration_hours, actual_duration_hours,
                expected_fuel_lt, actual_fuel_lt,
                target_tonnage, collected_tonnage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['driver_id'], data['date'],
            scores['route_score'], scores['time_score'], scores['fuel_score'], scores['tonnage_score'],
            scores['total_score'], scores['route_deviation_km'], scores['fuel_saved_lt'],
            data.get('planned_distance_km'), data.get('actual_distance_km'),
            data.get('planned_duration_hours'), data.get('actual_duration_hours'),
            data.get('expected_fuel_lt'), data.get('actual_fuel_lt'),
            data.get('target_tonnage'), data.get('collected_tonnage')
        ))
        
        conn.commit()
        
        # Başarıları kontrol et ve ver
        check_and_award_achievements(data['driver_id'], data['date'], scores['total_score'])
        
        conn.close()
        
        return jsonify({
            'success': True,
            'scores': scores,
            'message': 'Performans kaydedildi'
        })
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

def calculate_scores(data):
    """Performans puanlarını hesapla (0-100)"""
    
    # 1. Rota Uyumu (0-30 puan)
    route_score = 0
    route_deviation_km = 0
    if data.get('planned_distance_km') and data.get('actual_distance_km'):
        planned = data['planned_distance_km']
        actual = data['actual_distance_km']
        deviation = abs(actual - planned)
        route_deviation_km = deviation
        
        # %5'den az sapma: 30 puan
        # %10'dan az sapma: 20 puan
        # %15'ten az sapma: 10 puan
        deviation_ratio = (deviation / planned) if planned > 0 else 1
        if deviation_ratio <= 0.05:
            route_score = 30
        elif deviation_ratio <= 0.10:
            route_score = 20
        elif deviation_ratio <= 0.15:
            route_score = 10
        else:
            route_score = max(0, 10 - (deviation_ratio - 0.15) * 50)
    
    # 2. Zamanında Tamamlama (0-25 puan)
    time_score = 0
    if data.get('planned_duration_hours') and data.get('actual_duration_hours'):
        planned = data['planned_duration_hours']
        actual = data['actual_duration_hours']
        
        # Planlanan sürede veya daha erken: 25 puan
        # %10 fazla: 15 puan
        # %20 fazla: 5 puan
        if actual <= planned:
            time_score = 25
        elif actual <= planned * 1.10:
            time_score = 15
        elif actual <= planned * 1.20:
            time_score = 5
        else:
            time_score = 0
    
    # 3. Yakıt Verimliliği (0-25 puan)
    fuel_score = 0
    fuel_saved_lt = 0
    if data.get('expected_fuel_lt') and data.get('actual_fuel_lt'):
        expected = data['expected_fuel_lt']
        actual = data['actual_fuel_lt']
        fuel_saved_lt = max(0, expected - actual)  # Negatif olmasın
        
        # Beklenen yakıttan az kullanım: bonus
        # Beklenen yakıttan fazla: ceza
        fuel_ratio = (actual / expected) if expected > 0 else 1
        if fuel_ratio <= 0.90:  # %10 tasarruf
            fuel_score = 25
        elif fuel_ratio <= 1.00:  # Normal tüketim
            fuel_score = 20
        elif fuel_ratio <= 1.10:  # %10 fazla
            fuel_score = 10
        else:
            fuel_score = 0
    
    # 4. Toplanan Tonaj (0-20 puan)
    tonnage_score = 0
    if data.get('target_tonnage') and data.get('collected_tonnage'):
        target = data['target_tonnage']
        collected = data['collected_tonnage']
        
        # Hedefin %95'i ve üzeri: 20 puan
        # %90-95: 15 puan
        # %85-90: 10 puan
        collection_ratio = (collected / target) if target > 0 else 0
        if collection_ratio >= 0.95:
            tonnage_score = 20
        elif collection_ratio >= 0.90:
            tonnage_score = 15
        elif collection_ratio >= 0.85:
            tonnage_score = 10
        else:
            tonnage_score = max(0, collection_ratio * 10)
    
    total_score = route_score + time_score + fuel_score + tonnage_score
    
    return {
        'route_score': round(route_score, 2),
        'time_score': round(time_score, 2),
        'fuel_score': round(fuel_score, 2),
        'tonnage_score': round(tonnage_score, 2),
        'total_score': round(total_score, 2),
        'route_deviation_km': round(route_deviation_km, 2),
        'fuel_saved_lt': round(fuel_saved_lt, 2)
    }

# =============================================================================
# BAŞARILAR (ACHIEVEMENTS)
# =============================================================================

def check_and_award_achievements(driver_id, date, total_score):
    """Başarıları kontrol et ve ödüllendir"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Seviye rozetleri (Günlük)
    achievement_type = None
    achievement_name = None
    description = None
    icon = None
    
    if total_score >= 95:
        achievement_type = 'gold'
        achievement_name = '🥇 Altın Şoför'
        description = f'95+ puan ile mükemmel performans ({total_score:.1f})'
        icon = '🥇'
    elif total_score >= 85:
        achievement_type = 'silver'
        achievement_name = '🥈 Gümüş Şoför'
        description = f'85+ puan ile harika performans ({total_score:.1f})'
        icon = '🥈'
    elif total_score >= 75:
        achievement_type = 'bronze'
        achievement_name = '🥉 Bronz Şoför'
        description = f'75+ puan ile iyi performans ({total_score:.1f})'
        icon = '🥉'
    
    if achievement_type:
        cursor.execute('''
            INSERT INTO driver_achievements (driver_id, achievement_type, achievement_name, description, icon)
            VALUES (?, ?, ?, ?, ?)
        ''', (driver_id, achievement_type, achievement_name, description, icon))
    
    # 2. Seri başarı (5 gün üst üste 85+ puan)
    cursor.execute('''
        SELECT COUNT(*) as streak
        FROM driver_performance
        WHERE driver_id = ?
        AND date >= date(?, '-4 days')
        AND date <= ?
        AND total_score >= 85
    ''', (driver_id, date, date))
    
    streak = cursor.fetchone()['streak']
    if streak >= 5:
        # Bu başarıyı daha önce kazanmış mı kontrol et (son 5 gün içinde)
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM driver_achievements
            WHERE driver_id = ?
            AND achievement_type = 'streak'
            AND earned_at >= date(?, '-5 days')
        ''', (driver_id, date))
        
        if cursor.fetchone()['count'] == 0:
            cursor.execute('''
                INSERT INTO driver_achievements (driver_id, achievement_type, achievement_name, description, icon)
                VALUES (?, 'streak', '🔥 Seri Başarı', '5 gün üst üste 85+ puan', '🔥')
            ''', (driver_id,))
    
    # 3. Rota Ustası (%98+ rota uyumu)
    cursor.execute('''
        SELECT route_score FROM driver_performance
        WHERE driver_id = ? AND date = ?
    ''', (driver_id, date))
    
    result = cursor.fetchone()
    if result and result['route_score'] >= 29.4:  # %98 of 30
        cursor.execute('''
            INSERT INTO driver_achievements (driver_id, achievement_type, achievement_name, description, icon)
            VALUES (?, 'route_master', '🎯 Rota Ustası', 'Rotaya %98+ uyum', '🎯')
        ''', (driver_id,))
    
    conn.commit()
    conn.close()

@gamification_bp.route('/achievements/<int:driver_id>', methods=['GET'])
def get_driver_achievements(driver_id):
    """Şoförün tüm rozetlerini getir"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Son 30 gün
    cursor.execute('''
        SELECT * FROM driver_achievements
        WHERE driver_id = ?
        ORDER BY earned_at DESC
        LIMIT 50
    ''', (driver_id,))
    
    achievements = [dict(row) for row in cursor.fetchall()]
    
    # Özet istatistikler
    cursor.execute('''
        SELECT 
            achievement_type,
            COUNT(*) as count
        FROM driver_achievements
        WHERE driver_id = ?
        GROUP BY achievement_type
    ''', (driver_id,))
    
    stats = {row['achievement_type']: row['count'] for row in cursor.fetchall()}
    
    conn.close()
    
    return jsonify({
        'achievements': achievements,
        'stats': stats
    })

# =============================================================================
# PERFORMANS VE LİDERBOARD
# =============================================================================

@gamification_bp.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    """Liderlik tablosu (haftalık)"""
    period = request.args.get('period', 'week')  # week, month
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Tarih aralığı
    if period == 'week':
        days = 7
    elif period == 'month':
        days = 30
    else:
        days = 7
    
    cursor.execute(f'''
        SELECT 
            u.id,
            u.full_name,
            u.vehicle_id,
            COUNT(dp.id) as days_worked,
            AVG(dp.total_score) as avg_score,
            SUM(dp.total_score) as total_score,
            SUM(dp.fuel_saved_lt) as total_fuel_saved
        FROM users u
        LEFT JOIN driver_performance dp ON u.id = dp.driver_id
        WHERE u.role = 'surucu'
        AND dp.date >= date('now', '-{days} days')
        GROUP BY u.id
        ORDER BY avg_score DESC
    ''')
    
    leaderboard = []
    rank = 1
    for row in cursor.fetchall():
        driver = dict(row)
        driver['rank'] = rank
        # Yakıt tasarrufunu pozitif yap
        if driver.get('total_fuel_saved'):
            driver['total_fuel_saved'] = abs(driver['total_fuel_saved'])
        
        # Prim hesapla
        avg_score = driver['avg_score'] or 0
        if avg_score >= 95:
            driver['tier'] = 'gold'
            driver['bonus_percentage'] = 15
        elif avg_score >= 85:
            driver['tier'] = 'silver'
            driver['bonus_percentage'] = 10
        elif avg_score >= 75:
            driver['tier'] = 'bronze'
            driver['bonus_percentage'] = 5
        else:
            driver['tier'] = 'rookie'
            driver['bonus_percentage'] = 0
        
        leaderboard.append(driver)
        rank += 1
    
    conn.close()
    
    return jsonify({
        'period': period,
        'leaderboard': leaderboard
    })

@gamification_bp.route('/performance/<int:driver_id>', methods=['GET'])
def get_driver_performance(driver_id):
    """Şoförün performans detayları"""
    period = request.args.get('period', 'week')  # week, month
    
    if period == 'week':
        days = 7
    elif period == 'month':
        days = 30
    else:
        days = 7
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Günlük performans
    cursor.execute('''
        SELECT * FROM driver_performance
        WHERE driver_id = ?
        AND date >= date('now', '-{} days')
        ORDER BY date DESC
    '''.format(days), (driver_id,))
    
    daily_performance = [dict(row) for row in cursor.fetchall()]
    
    # Özet istatistikler
    cursor.execute('''
        SELECT 
            COUNT(*) as days_worked,
            AVG(total_score) as avg_score,
            MAX(total_score) as max_score,
            MIN(total_score) as min_score,
            SUM(fuel_saved_lt) as total_fuel_saved,
            SUM(route_deviation_km) as total_deviation
        FROM driver_performance
        WHERE driver_id = ?
        AND date >= date('now', '-{} days')
    '''.format(days), (driver_id,))
    
    summary = dict(cursor.fetchone())
    # Yakıt tasarrufunu pozitif yap
    if summary.get('total_fuel_saved'):
        summary['total_fuel_saved'] = abs(summary['total_fuel_saved'])
    
    # Mevcut seviye
    avg_score = summary['avg_score'] or 0
    if avg_score >= 95:
        summary['current_tier'] = 'gold'
        summary['tier_name'] = '🥇 Altın Şoför'
        summary['bonus_percentage'] = 15
    elif avg_score >= 85:
        summary['current_tier'] = 'silver'
        summary['tier_name'] = '🥈 Gümüş Şoför'
        summary['bonus_percentage'] = 10
    elif avg_score >= 75:
        summary['current_tier'] = 'bronze'
        summary['tier_name'] = '🥉 Bronz Şoför'
        summary['bonus_percentage'] = 5
    else:
        summary['current_tier'] = 'rookie'
        summary['tier_name'] = '🚛 Çaylak'
        summary['bonus_percentage'] = 0
    
    conn.close()
    
    return jsonify({
        'driver_id': driver_id,
        'period': period,
        'summary': summary,
        'daily_performance': daily_performance
    })

@gamification_bp.route('/dashboard/<int:driver_id>', methods=['GET'])
def get_driver_dashboard(driver_id):
    """Şoför ana dashboard verisi (özet)"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Bugünkü performans
    cursor.execute('''
        SELECT * FROM driver_performance
        WHERE driver_id = ? AND date = date('now')
    ''', (driver_id,))
    
    today = cursor.fetchone()
    today_data = dict(today) if today else None
    
    # Haftalık özet
    cursor.execute('''
        SELECT 
            COUNT(*) as days_worked,
            AVG(total_score) as avg_score,
            SUM(fuel_saved_lt) as fuel_saved
        FROM driver_performance
        WHERE driver_id = ?
        AND date >= date('now', '-7 days')
    ''', (driver_id,))
    
    week_summary = dict(cursor.fetchone())
    # Yakıt tasarrufunu pozitif yap
    if week_summary.get('fuel_saved'):
        week_summary['fuel_saved'] = abs(week_summary['fuel_saved'])
    
    # Sıralama
    cursor.execute('''
        SELECT 
            u.id,
            AVG(dp.total_score) as avg_score
        FROM users u
        LEFT JOIN driver_performance dp ON u.id = dp.driver_id
        WHERE u.role = 'surucu'
        AND dp.date >= date('now', '-7 days')
        GROUP BY u.id
        ORDER BY avg_score DESC
    ''')
    
    all_drivers = cursor.fetchall()
    rank = 1
    for driver in all_drivers:
        if driver['id'] == driver_id:
            week_summary['rank'] = rank
            break
        rank += 1
    
    # Son rozetler
    cursor.execute('''
        SELECT * FROM driver_achievements
        WHERE driver_id = ?
        ORDER BY earned_at DESC
        LIMIT 5
    ''', (driver_id,))
    
    recent_achievements = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'today': today_data,
        'week_summary': week_summary,
        'recent_achievements': recent_achievements
    })
