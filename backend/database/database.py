"""
SQLite Veritabanı Yönetimi
3 Rol: yonetici, surucu, public
"""

import sqlite3
import hashlib
from datetime import datetime
import os

# Dosya yolu - aynı klasörde (backend/database/)
DB_PATH = os.path.join(os.path.dirname(__file__), 'nilufer.db')

def hash_password(password):
    """Şifre hash'leme"""
    return hashlib.sha256(password.encode()).hexdigest()

def init_database():
    """Veritabanı tablolarını oluştur"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. KULLANICILAR TABLOSU
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('yonetici', 'surucu', 'public')),
            full_name TEXT,
            vehicle_id TEXT,
            email TEXT UNIQUE,
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # 2. ARAÇLAR TABLOSU (fleet.csv'den)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fleet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT UNIQUE NOT NULL,
            vehicle_name TEXT,
            vehicle_type TEXT,
            capacity_m3 REAL,
            capacity_ton REAL,
            status TEXT DEFAULT 'available',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 3. MAHALLELER TABLOSU
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS neighborhoods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            population INTEGER,
            total_containers INTEGER,
            underground_containers INTEGER,
            latitude REAL,
            longitude REAL,
            collection_days TEXT,
            requires_crane BOOLEAN DEFAULT 0,
            priority_score REAL DEFAULT 0,
            last_collection TIMESTAMP
        )
    ''')
    
    # 4. ROTALAR TABLOSU
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id TEXT,
            route_date DATE,
            route_sequence TEXT,
            total_distance_km REAL,
            estimated_duration_hours REAL,
            status TEXT DEFAULT 'planned',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES fleet(vehicle_id)
        )
    ''')
    
    # 5. BİLDİRİMLER TABLOSU (Vatandaş bildirimleri)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            neighborhood_id INTEGER,
            type TEXT,
            message TEXT,
            priority TEXT DEFAULT 'normal',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            FOREIGN KEY (neighborhood_id) REFERENCES neighborhoods(id)
        )
    ''')
    
    # 6. TAHMİNLER TABLOSU (ML tahmin cache)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_date DATE UNIQUE,
            predicted_tonnage REAL,
            actual_tonnage REAL,
            model_version TEXT DEFAULT 'v1.0',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 7. METRİKLER TABLOSU (Günlük istatistikler)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE UNIQUE,
            total_distance_km REAL,
            total_tonnage REAL,
            active_vehicles INTEGER,
            fuel_consumption_liters REAL,
            co2_emissions_kg REAL,
            optimization_savings_km REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 8. ŞOFÖR PERFORMANSI TABLOSU (Gamification)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS driver_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER NOT NULL,
            date DATE NOT NULL,
            route_score REAL DEFAULT 0,          -- Rota uyumu puanı (0-30)
            time_score REAL DEFAULT 0,           -- Zaman puanı (0-25)
            fuel_score REAL DEFAULT 0,           -- Yakıt puanı (0-25)
            tonnage_score REAL DEFAULT 0,        -- Tonaj puanı (0-20)
            total_score REAL DEFAULT 0,          -- Toplam (0-100)
            route_deviation_km REAL DEFAULT 0,   -- Rotadan sapma (km)
            fuel_saved_lt REAL DEFAULT 0,        -- Tasarruf edilen yakıt (lt)
            planned_distance_km REAL,
            actual_distance_km REAL,
            planned_duration_hours REAL,
            actual_duration_hours REAL,
            expected_fuel_lt REAL,
            actual_fuel_lt REAL,
            target_tonnage REAL,
            collected_tonnage REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (driver_id) REFERENCES users(id),
            UNIQUE(driver_id, date)
        )
    ''')
    
    # 9. ŞOFÖR BAŞARILARI/ROZETLER TABLOSU
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS driver_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER NOT NULL,
            achievement_type TEXT NOT NULL,      -- 'gold', 'silver', 'bronze', 'streak', 'weekly_star', 'eco_hero', 'route_master'
            achievement_name TEXT,
            description TEXT,
            icon TEXT,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (driver_id) REFERENCES users(id)
        )
    ''')
    
    # 10. HAFTALIK PUAN ÖZET TABLOSU
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS driver_weekly_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            driver_id INTEGER NOT NULL,
            week_start_date DATE NOT NULL,
            week_end_date DATE NOT NULL,
            total_score REAL DEFAULT 0,
            avg_score REAL DEFAULT 0,
            days_worked INTEGER DEFAULT 0,
            rank INTEGER,
            bonus_amount REAL DEFAULT 0,
            bonus_percentage REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (driver_id) REFERENCES users(id),
            UNIQUE(driver_id, week_start_date)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Veritabanı tabloları oluşturuldu (Gamification dahil)")

def create_default_users():
    """Varsayılan kullanıcıları oluştur"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    default_users = [
        # Yöneticiler
        ('admin', hash_password('admin123'), 'yonetici', 'Sistem Yöneticisi', None),
        ('yonetici1', hash_password('yonetici123'), 'yonetici', 'Ahmet Yılmaz', None),
        
        # Sürücüler
        ('mehmet.yilmaz', hash_password('surucu123'), 'surucu', 'Mehmet Yılmaz', '2824'),
        ('ali.demir', hash_password('surucu123'), 'surucu', 'Ali Demir', '1409'),
        ('hasan.celik', hash_password('surucu123'), 'surucu', 'Hasan Çelik', '9012'),
        
        # Public (opsiyonel - giriş gerektirmez ama test için)
        ('public', hash_password('public123'), 'public', 'Misafir Kullanıcı', None),
    ]
    
    try:
        cursor.executemany('''
            INSERT OR IGNORE INTO users (username, password, role, full_name, vehicle_id)
            VALUES (?, ?, ?, ?, ?)
        ''', default_users)
        
        conn.commit()
        print(f"✅ {cursor.rowcount} kullanıcı eklendi")
    except Exception as e:
        print(f"❌ Kullanıcı ekleme hatası: {e}")
    finally:
        conn.close()

def get_user_by_username(username):
    """Kullanıcıyı kullanıcı adına göre getir"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    
    conn.close()
    return dict(user) if user else None

def verify_user(username, password):
    """Kullanıcı doğrulama"""
    user = get_user_by_username(username)
    if user and user['password'] == hash_password(password):
        # Son giriş zamanını güncelle
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET last_login = ? WHERE username = ?', 
                      (datetime.now(), username))
        conn.commit()
        conn.close()
        return user
    return None

def get_driver_vehicle(vehicle_id):
    """Sürücünün aracını getir"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM fleet WHERE vehicle_id = ?', (vehicle_id,))
    vehicle = cursor.fetchone()
    
    conn.close()
    return dict(vehicle) if vehicle else None

def update_database_schema():
    """Mevcut veritabanına yeni kolonları ekle (migration)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Mevcut kolonları kontrol et
    cursor.execute('PRAGMA table_info(users)')
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    try:
        # Email kolonu ekle (UNIQUE kaldır - sonra eklenebilir)
        if 'email' not in existing_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN email TEXT')
            print("✅ email kolonu eklendi")
        else:
            print("ℹ️  email kolonu zaten var")
    except sqlite3.OperationalError as e:
        print(f"⚠️  email kolonu hatası: {e}")
    
    try:
        # is_active kolonu ekle
        if 'is_active' not in existing_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1')
            print("✅ is_active kolonu eklendi")
        else:
            print("ℹ️  is_active kolonu zaten var")
    except sqlite3.OperationalError as e:
        print(f"⚠️  is_active kolonu hatası: {e}")
    
    try:
        # created_by kolonu ekle
        if 'created_by' not in existing_columns:
            cursor.execute('ALTER TABLE users ADD COLUMN created_by INTEGER')
            print("✅ created_by kolonu eklendi")
        else:
            print("ℹ️  created_by kolonu zaten var")
    except sqlite3.OperationalError as e:
        print(f"⚠️  created_by kolonu hatası: {e}")
    
    conn.commit()
    conn.close()
    print("✅ Database şeması güncellendi")

def register_user(full_name, username, email, password):
    """Public kullanıcı kaydı (vatandaş)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Username kontrolü
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return {'success': False, 'error': 'Bu kullanıcı adı zaten kullanılıyor'}
        
        # Email kontrolü
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return {'success': False, 'error': 'Bu e-posta adresi zaten kullanılıyor'}
        
        # Kullanıcı oluştur
        cursor.execute('''
            INSERT INTO users (username, password, role, full_name, email, is_active)
            VALUES (?, ?, 'public', ?, ?, 1)
        ''', (username, hash_password(password), full_name, email))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'user_id': user_id,
            'username': username
        }
    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}

def create_driver(full_name, username, vehicle_id, admin_id, password='nilufer2025'):
    """Şoför oluştur (sadece admin)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Username kontrolü
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return {'success': False, 'error': 'Bu kullanıcı adı zaten kullanılıyor'}
        
        # Araç kontrolü
        cursor.execute('SELECT vehicle_id FROM fleet WHERE vehicle_id = ?', (vehicle_id,))
        if not cursor.fetchone():
            conn.close()
            return {'success': False, 'error': 'Geçersiz araç ID'}
        
        # Şoför oluştur
        cursor.execute('''
            INSERT INTO users (username, password, role, full_name, vehicle_id, created_by, is_active)
            VALUES (?, ?, 'surucu', ?, ?, ?, 1)
        ''', (username, hash_password(password), full_name, vehicle_id, admin_id))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'user_id': user_id,
            'username': username,
            'password': password
        }
    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}

def get_all_drivers():
    """Tüm şoförleri getir"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.*, f.vehicle_name, f.vehicle_type
        FROM users u
        LEFT JOIN fleet f ON u.vehicle_id = f.vehicle_id
        WHERE u.role = 'surucu'
        ORDER BY u.full_name
    ''')
    drivers = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in drivers]

def delete_driver(driver_id, admin_id):
    """Şoför sil (sadece admin)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Admin kontrolü ve şoför olduğunu doğrula
        cursor.execute('SELECT role FROM users WHERE id = ?', (driver_id,))
        user = cursor.fetchone()
        
        if not user or user[0] != 'surucu':
            conn.close()
            return {'success': False, 'error': 'Geçersiz şoför'}
        
        cursor.execute('DELETE FROM users WHERE id = ?', (driver_id,))
        conn.commit()
        conn.close()
        
        return {'success': True}
    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}

# Test
if __name__ == '__main__':
    print("Veritabanı Başlatma")
    print("=" * 50)
    
    init_database()
    create_default_users()
    
    print("\n📋 Oluşturulan Kullanıcılar:")
    print("-" * 50)
    print("Yönetici:")
    print("  - Kullanıcı: admin / Şifre: admin123")
    print("  - Kullanıcı: yonetici1 / Şifre: yonetici123")
    print("\nSürücü:")
    print("  - Kullanıcı: mehmet.yilmaz / Şifre: surucu123")
    print("  - Kullanıcı: ali.demir / Şifre: surucu123")
    print("  - Kullanıcı: hasan.celik / Şifre: surucu123")
    print("\nPublic (Canlı Takip - Giriş Gerektirmez)")
    print("  - Direkt erişilebilir")
    print("=" * 50)
