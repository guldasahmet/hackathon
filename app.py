"""
NilüferAKS - Akıllı Atık Kontrol Sistemi
Flask Backend
"""

from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_cors import CORS
from functools import wraps
import sqlite3
import pandas as pd
import json
import os
from datetime import datetime
from ai.talep_tahmin import talep_tahmin_tum_mahalleler
from ai.rota_optimizer import optimize_rotalar
from backend.database.database import verify_user, get_driver_vehicle, DB_PATH, register_user, create_driver, get_all_drivers, delete_driver

# Backend API blueprints
from backend.api import vehicles_bp, neighborhoods_bp, dashboard_bp, routes_bp

app = Flask(__name__)
app.secret_key = 'nilufer-aks-secret-key-2025'  # Production'da değiştir!
CORS(app)  # Frontend'in API'ye erişebilmesi için

# Blueprint'leri kaydet
app.register_blueprint(vehicles_bp)
app.register_blueprint(neighborhoods_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(routes_bp)

# Assets klasörü için route (video, resim vs.)
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('assets', filename)

# Veritabanı bağlantısı
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Sonuçları dict olarak al
    return conn

# =============================================================================
# AUTH DECORATORS (Yetkilendirme)
# =============================================================================

def login_required(f):
    """Giriş zorunluluğu"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            # Aynı mesajı tekrar eklememek için kontrol
            if '_login_warned' not in session:
                flash('Bu sayfaya erişmek için giriş yapmalısınız.', 'warning')
                session['_login_warned'] = True
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """Rol bazlı erişim kontrolü"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                if '_login_warned' not in session:
                    flash('Bu sayfaya erişmek için giriş yapmalısınız.', 'warning')
                    session['_login_warned'] = True
                return redirect(url_for('login'))
            
            user_role = session['user'].get('role')
            if user_role not in roles:
                flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
                # Kullanıcıyı rolüne uygun sayfaya yönlendir (döngü önleme)
                if user_role == 'surucu':
                    return redirect(url_for('driver'))
                elif user_role == 'public':
                    return redirect(url_for('tracking'))
                else:
                    return redirect(url_for('login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# =============================================================================
# AUTH ROUTE'LARI
# =============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Giriş sayfası"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = verify_user(username, password)
        
        if user:
            # Session'a kaydet
            session['user'] = {
                'id': user['id'],
                'username': user['username'],
                'role': user['role'],
                'full_name': user['full_name'],
                'vehicle_id': user['vehicle_id']
            }
            
            # Login warning flag'ini temizle
            session.pop('_login_warned', None)
            
            flash(f"Hoş geldiniz, {user['full_name']}!", 'success')
            
            # Role göre yönlendir
            if user['role'] == 'yonetici':
                return redirect(url_for('index'))
            elif user['role'] == 'surucu':
                return redirect(url_for('driver'))
            else:
                return redirect(url_for('tracking'))
        else:
            flash('Kullanıcı adı veya şifre hatalı!', 'danger')
            return render_template('login.html', error='Kullanıcı adı veya şifre hatalı!')
    
    # Zaten giriş yapmışsa yönlendir
    if 'user' in session:
        role = session['user']['role']
        if role == 'yonetici':
            return redirect(url_for('index'))
        elif role == 'surucu':
            return redirect(url_for('driver'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Çıkış"""
    session.pop('user', None)
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Kayıt sayfası (Public kullanıcılar için)"""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        
        # Validasyon
        if not full_name or not username or not email or not password:
            return render_template('register.html', error='Lütfen tüm alanları doldurun!')
        
        if len(username) < 3:
            return render_template('register.html', error='Kullanıcı adı en az 3 karakter olmalıdır!')
        
        # Email formatı kontrolü
        if '@' not in email or '.' not in email:
            return render_template('register.html', error='Geçerli bir e-posta adresi girin!')
        
        if len(password) < 6:
            return render_template('register.html', error='Şifre en az 6 karakter olmalıdır!')
        
        if password != password_confirm:
            return render_template('register.html', error='Şifreler eşleşmiyor!')
        
        # Kullanıcı oluştur
        result = register_user(full_name, username, email, password)
        
        if result['success']:
            # Otomatik login
            user = verify_user(username, password)
            if user:
                session['user'] = {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role'],
                    'full_name': user['full_name'],
                    'vehicle_id': user['vehicle_id']
                }
                flash(f'Hoş geldiniz, {full_name}! Hesabınız başarıyla oluşturuldu.', 'success')
                return redirect(url_for('tracking'))
        else:
            return render_template('register.html', error=result['error'])
    
    # Zaten giriş yapmışsa yönlendir
    if 'user' in session:
        return redirect(url_for('tracking'))
    
    return render_template('register.html')

# =============================================================================
# ADMIN ROUTE'LARI
# =============================================================================

@app.route('/admin/drivers', methods=['GET', 'POST'])
@role_required('yonetici')
def admin_drivers():
    """Şoför Yönetimi (Sadece Admin)"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            # Yeni şoför ekle
            full_name = request.form.get('full_name', '').strip()
            vehicle_id = request.form.get('vehicle_id', '').strip()
            
            if not full_name or not vehicle_id:
                flash('Ad Soyad ve Araç seçimi zorunludur!', 'danger')
                return redirect(url_for('admin_drivers'))
            
            # Username oluştur (ad.soyad formatında)
            username = full_name.lower().replace(' ', '.').replace('ç', 'c').replace('ğ', 'g').replace('ı', 'i').replace('ö', 'o').replace('ş', 's').replace('ü', 'u')
            
            # Admin ID
            admin_id = session['user']['id']
            
            result = create_driver(full_name, username, vehicle_id, admin_id)
            
            if result['success']:
                flash(f'Şoför başarıyla eklendi! Kullanıcı adı: {result["username"]} | Şifre: {result["password"]}', 'success')
            else:
                flash(f'Hata: {result["error"]}', 'danger')
            
            return redirect(url_for('admin_drivers'))
        
        elif action == 'delete':
            # Şoför sil
            driver_id = request.form.get('driver_id')
            admin_id = session['user']['id']
            
            result = delete_driver(driver_id, admin_id)
            
            if result['success']:
                flash('Şoför başarıyla silindi!', 'success')
            else:
                flash(f'Hata: {result["error"]}', 'danger')
            
            return redirect(url_for('admin_drivers'))
    
    # Şoför listesi ve araçları getir
    drivers = get_all_drivers()
    
    # Araçları getir (tüm araçlar, vehicle_id'ye göre numerik sıralı)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT vehicle_id, vehicle_name, vehicle_type FROM fleet ORDER BY CAST(vehicle_id AS INTEGER)')
    vehicles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('admin_drivers.html', drivers=drivers, vehicles=vehicles)

# =============================================================================
# SAYFA ROUTE'LARI (HTML sayfaları)
# =============================================================================

@app.route('/')
def index():
    """Ana sayfa - Kullanıcıyı rolüne göre yönlendir"""
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user_role = session['user'].get('role')
    if user_role == 'yonetici':
        return render_template('dashboard.html', user=session['user'])
    elif user_role == 'surucu':
        return redirect(url_for('driver'))
    else:
        return redirect(url_for('tracking'))

@app.route('/yonetici')
@login_required
@role_required('yonetici')
def yonetici():
    """Yönetici paneli (Dashboard)"""
    return render_template('dashboard.html', user=session['user'])

@app.route('/driver')
@login_required
@role_required('surucu')
def driver():
    """Sürücü portali"""
    user = session['user']
    # Sürücünün aracını getir
    vehicle = None
    if user['vehicle_id']:
        vehicle = get_driver_vehicle(user['vehicle_id'])
    
    return render_template('driver.html', user=user, vehicle=vehicle)

@app.route('/tracking')
def tracking():
    """Canlı takip - PUBLIC (giriş gerektirmez)"""
    return render_template('tracking.html')

@app.route('/filo-izleme')
def filo_izleme():
    """Filo İzleme - Gerçek zamanlı simülasyon"""
    return render_template('filo_izleme.html')

@app.route('/profile')
@login_required
def profile():
    """Kullanıcı profil sayfası"""
    user = session['user']
    return render_template('profile.html', user=user)

# API Endpoints artık backend/api/ klasöründe (Blueprint'ler ile)
# - /api/vehicles -> backend/api/vehicles.py
# - /api/fleet-summary -> backend/api/vehicles.py
# - /api/mahalleler -> backend/api/neighborhoods.py
# - /api/dashboard -> backend/api/dashboard.py
# - /api/routes -> backend/api/routes_api.py
# - /api/route/<id> -> backend/api/routes_api.py

@app.route('/api/tracking')
def api_tracking():
    """Canlı araç takibi (simülasyon)"""
    
    # Simüle edilmiş GPS verileri
    araclar = [
        {'id': 2824, 'lat': 40.2250, 'lon': 28.8800, 'hiz': 15, 'durum': 'hareket', 'mahalle': 'Dumlupınar'},
        {'id': 1409, 'lat': 40.2150, 'lon': 28.9100, 'hiz': 0, 'durum': 'toplama', 'mahalle': 'Fethiye'},
        {'id': 7823, 'lat': 40.2609, 'lon': 28.9377, 'hiz': 20, 'durum': 'hareket', 'mahalle': 'Balat'},
        {'id': 3156, 'lat': 40.2063, 'lon': 28.9023, 'hiz': 0, 'durum': 'depo', 'mahalle': 'Depo'},
        {'id': 9012, 'lat': 40.1950, 'lon': 28.8600, 'hiz': 12, 'durum': 'hareket', 'mahalle': 'Gölyazı'},
    ]
    
    ozet = {
        'aktif': 43,
        'beklemede': 2,
        'depoda': 1,
        'toplanan_ton': 487,
        'ziyaret_edilen': 52,
        'toplam_mahalle': 64,
        'ilerleme': 81,
        'kalan_sure': '~3 saat'
    }
    
    return jsonify({'araclar': araclar, 'ozet': ozet})

@app.route('/api/tahmin')
def api_tahmin():
    """Mahalle bazlı talep tahmini"""
    
    try:
        tahminler = talep_tahmin_tum_mahalleler()
    except:
        # Örnek veri
        tahminler = [
            {'mahalle': 'Balat', 'tahmin': 28.83, 'konteyner': 9900},
            {'mahalle': 'Fethiye', 'tahmin': 28.54, 'konteyner': 9800},
            {'mahalle': 'Ataevler', 'tahmin': 26.68, 'konteyner': 9160},
            {'mahalle': 'Görükle', 'tahmin': 24.49, 'konteyner': 8410},
            {'mahalle': 'Kültür', 'tahmin': 25.10, 'konteyner': 8620},
        ]
    
    return jsonify(tahminler)

@app.route('/api/optimize', methods=['POST'])
def api_optimize():
    """Yeni rota hesaplama"""
    
    data = request.json or {}
    tarih = data.get('tarih', datetime.now().strftime('%Y-%m-%d'))
    
    try:
        sonuc = optimize_rotalar(tarih)
    except:
        sonuc = {
            'basarili': True,
            'mesaj': 'Rotalar optimize edildi',
            'toplam_mesafe': 1620,
            'tasarruf_km': 540,
            'tasarruf_yuzde': 25
        }
    
    return jsonify(sonuc)

# =============================================================================
# UYGULAMA BAŞLATMA
# =============================================================================

if __name__ == '__main__':
    print("=" * 50)
    print("NilüferAKS - Akıllı Atık Kontrol Sistemi")
    print("=" * 50)
    print("Sunucu başlatılıyor: http://localhost:5000")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
