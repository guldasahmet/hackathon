"""
Routes API Endpoints
Rota optimizasyonu ve takip API'leri
"""
from flask import jsonify, request
from datetime import datetime
from . import routes_bp
import pandas as pd
import os
import glob


def get_arac_listesi():
    """Mevcut araç dosyalarını listele"""
    dosyalar = glob.glob('araclarin_durdugu_noktalar/arac_*_duragan.csv')
    araclar = []
    for dosya in dosyalar:
        # Dosya adından araç ID'sini çıkar
        dosya_adi = os.path.basename(dosya)
        arac_id = int(dosya_adi.split('_')[1])
        araclar.append(arac_id)
    return sorted(araclar)


def get_arac_gercek_rota(arac_id, tarih=None):
    """
    Araç durağan noktalarından gerçek rotayı çıkar
    
    Args:
        arac_id: Araç numarası
        tarih: Tarih (örn: '19.12.2025'). None ise ilk tarih
    
    Returns:
        dict: Rota bilgileri
    """
    dosya = f'araclarin_durdugu_noktalar/arac_{arac_id}_duragan.csv'
    
    if not os.path.exists(dosya):
        return None
    
    df = pd.read_csv(dosya)
    
    # Mevcut tarihleri al
    tarihler = df['Tarih'].unique().tolist()
    
    if tarih is None:
        tarih = tarihler[0]
    elif tarih not in tarihler:
        return {'hata': f'Tarih bulunamadı. Mevcut tarihler: {tarihler}'}
    
    # O güne ait verileri filtrele
    gun_df = df[df['Tarih'] == tarih].copy()
    
    if gun_df.empty:
        return None
    
    # Saate göre sırala
    gun_df['saat_dt'] = pd.to_datetime(gun_df['Saat'], format='%H:%M:%S')
    gun_df = gun_df.sort_values('saat_dt')
    
    # Araç tipi ve konteyner bilgisi
    arac_tipi = gun_df['vehicle_type'].iloc[0] if 'vehicle_type' in gun_df.columns else 'Bilinmiyor'
    konteyner_tipi = gun_df['konteyner_tip'].iloc[0] if 'konteyner_tip' in gun_df.columns else 'Bilinmiyor'
    
    # Benzersiz durak noktalarını çıkar (yakın koordinatları birleştir)
    # Koordinat toleransı: ~10 metre
    tolerans = 0.0001
    
    duraklar = []
    onceki_lat, onceki_lon = None, None
    
    for _, row in gun_df.iterrows():
        lat, lon = row['Enlem'], row['Boylam']
        saat = row['Saat']
        
        # İlk nokta veya yeterince uzak mı?
        if onceki_lat is None or (abs(lat - onceki_lat) > tolerans or abs(lon - onceki_lon) > tolerans):
            duraklar.append({
                'sira': len(duraklar) + 1,
                'lat': round(lat, 6),
                'lon': round(lon, 6),
                'saat': saat
            })
            onceki_lat, onceki_lon = lat, lon
    
    # Toplam mesafeyi hesapla (haversine)
    toplam_mesafe = 0
    for i in range(1, len(duraklar)):
        lat1, lon1 = duraklar[i-1]['lat'], duraklar[i-1]['lon']
        lat2, lon2 = duraklar[i]['lat'], duraklar[i]['lon']
        
        from math import radians, cos, sin, sqrt, atan2
        R = 6371  # km
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        mesafe = R * c
        toplam_mesafe += mesafe
    
    return {
        'arac_id': arac_id,
        'tarih': tarih,
        'arac_tipi': arac_tipi,
        'konteyner_tipi': konteyner_tipi,
        'duraklar': duraklar,
        'durak_sayisi': len(duraklar),
        'toplam_mesafe_km': round(toplam_mesafe, 2),
        'mevcut_tarihler': tarihler
    }


@routes_bp.route('/araclar')
def api_arac_listesi():
    """Durağan nokta verisi olan araçları listele"""
    araclar = get_arac_listesi()
    return jsonify({
        'araclar': araclar,
        'toplam': len(araclar)
    })


@routes_bp.route('/arac/<int:arac_id>/rota')
def api_arac_rota(arac_id):
    """
    Belirli bir aracın gerçek rotası (GPS verilerinden)
    
    Query params:
        tarih: Tarih (örn: 19.12.2025)
    """
    tarih = request.args.get('tarih')
    
    rota = get_arac_gercek_rota(arac_id, tarih)
    
    if rota is None:
        return jsonify({'hata': f'Araç {arac_id} için veri bulunamadı'}), 404
    
    if 'hata' in rota:
        return jsonify(rota), 400
    
    return jsonify(rota)


@routes_bp.route('/arac/<int:arac_id>/tarihler')
def api_arac_tarihler(arac_id):
    """Araç için mevcut tarihleri listele"""
    dosya = f'araclarin_durdugu_noktalar/arac_{arac_id}_duragan.csv'
    
    if not os.path.exists(dosya):
        return jsonify({'hata': f'Araç {arac_id} için veri bulunamadı'}), 404
    
    df = pd.read_csv(dosya)
    tarihler = df['Tarih'].unique().tolist()
    
    return jsonify({
        'arac_id': arac_id,
        'tarihler': tarihler
    })


@routes_bp.route('/routes')
def api_routes():
    """Optimize edilmiş rotalar"""
    
    # Örnek rota verisi (gerçekte optimize_rotalar() fonksiyonundan gelir)
    rotalar = [
        {
            'vehicle_id': 2824,
            'vehicle_tip': 'Vinçli',
            'surucu': 'Mehmet Yılmaz',
            'duraklar': [
                {'sira': 1, 'mahalle': 'Görükle', 'talep': 24.5, 'durum': 'tamamlandi', 'saat': '08:15'},
                {'sira': 2, 'mahalle': 'İhsaniye', 'talep': 18.2, 'durum': 'tamamlandi', 'saat': '09:42'},
                {'sira': 3, 'mahalle': 'Dumlupınar', 'talep': 22.1, 'durum': 'devam', 'saat': None},
                {'sira': 4, 'mahalle': 'Konak', 'talep': 15.8, 'durum': 'bekliyor', 'saat': None},
                {'sira': 5, 'mahalle': 'Beşevler', 'talep': 12.4, 'durum': 'bekliyor', 'saat': None},
            ],
            'toplam_mesafe': 34,
            'toplam_yuk': 93.0,
            'ilerleme': 66
        },
        {
            'vehicle_id': 1409,
            'vehicle_tip': 'Büyük',
            'surucu': 'Ali Demir',
            'duraklar': [
                {'sira': 1, 'mahalle': 'Balat', 'talep': 28.8, 'durum': 'tamamlandi', 'saat': '07:30'},
                {'sira': 2, 'mahalle': 'Fethiye', 'talep': 28.5, 'durum': 'devam', 'saat': None},
                {'sira': 3, 'mahalle': 'Ataevler', 'talep': 26.7, 'durum': 'bekliyor', 'saat': None},
            ],
            'toplam_mesafe': 28,
            'toplam_yuk': 84.0,
            'ilerleme': 45
        }
    ]
    
    return jsonify(rotalar)


@routes_bp.route('/route/<int:vehicle_id>')
def api_vehicle_route(vehicle_id):
    """Belirli bir aracın rotası"""
    
    # Örnek - gerçekte veritabanından çekilir
    rota = {
        'vehicle_id': vehicle_id,
        'tarih': datetime.now().strftime('%d Aralık %Y'),
        'duraklar': [
            {'sira': 1, 'mahalle': 'Görükle', 'talep': 24.5, 'durum': 'tamamlandi', 'saat': '08:15', 'lat': 40.2230, 'lon': 28.8720},
            {'sira': 2, 'mahalle': 'İhsaniye', 'talep': 18.2, 'durum': 'tamamlandi', 'saat': '09:42', 'lat': 40.2180, 'lon': 28.8650},
            {'sira': 3, 'mahalle': 'Dumlupınar', 'talep': 22.1, 'durum': 'devam', 'saat': None, 'lat': 40.2250, 'lon': 28.8800},
            {'sira': 4, 'mahalle': 'Konak', 'talep': 15.8, 'durum': 'bekliyor', 'saat': None, 'lat': 40.2100, 'lon': 28.8800},
            {'sira': 5, 'mahalle': 'Beşevler', 'talep': 12.4, 'durum': 'bekliyor', 'saat': None, 'lat': 40.2050, 'lon': 28.8900},
        ],
        'ozet': {
            'toplam_mesafe': 34,
            'toplam_yuk': 93.0,
            'kapasite_kullanim': 78,
            'ilerleme': 66,
            'kalan_durak': 3,
            'tahmini_bitis': '14:30'
        }
    }
    
    return jsonify(rota)


@routes_bp.route('/ai-optimized-routes')
def get_ai_optimized_routes():
    """
    AI optimize edilmiş rotaları döndür
    routes_api.json dosyasındaki VRP çözümünü sunar
    """
    try:
        # routes_api.json dosyasını oku
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        routes_file = os.path.join(project_root, 'full_dataset', 'routes_api.json')
        
        if not os.path.exists(routes_file):
            return jsonify({
                'success': False,
                'error': 'routes_api.json dosyası bulunamadı'
            }), 404
        
        import json
        with open(routes_file, 'r', encoding='utf-8-sig') as f:
            routes_data = json.load(f)
        
        return jsonify({
            'success': True,
            'data': routes_data
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@routes_bp.route('/ai-optimized-routes/stats')
def get_ai_routes_stats():
    """AI rotaları istatistiklerini döndür"""
    try:
        # routes_api.json dosyasını oku
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        routes_file = os.path.join(project_root, 'full_dataset', 'routes_api.json')
        
        if not os.path.exists(routes_file):
            return jsonify({
                'success': False,
                'error': 'routes_api.json dosyası bulunamadı'
            }), 404
        
        import json
        with open(routes_file, 'r', encoding='utf-8-sig') as f:
            routes_data = json.load(f)
        
        # İstatistikleri hesapla
        total_vehicles = routes_data.get('total_vehicles', 0)
        total_stops = routes_data.get('total_stops', 0)
        vehicles = routes_data.get('vehicles', [])
        
        # Araç başına ortalama durak
        avg_stops = total_stops // total_vehicles if total_vehicles > 0 else 0
        
        # Toplam tonaj hesapla
        total_tonnage = 0
        vehicles_with_routes = 0
        for vehicle in vehicles:
            route = vehicle.get('route', [])
            if route:
                vehicles_with_routes += 1
                # Son noktadaki yük = toplam toplanan atık
                last_point = route[-1]
                total_tonnage += last_point.get('current_load_ton', 0)
        
        # Mahalle sayısını hesapla
        all_neighborhoods = set()
        for vehicle in vehicles:
            route = vehicle.get('route', [])
            for point in route:
                mahalle = point.get('mahalle')
                if mahalle:
                    all_neighborhoods.add(mahalle)
        
        return jsonify({
            'success': True,
            'stats': {
                'total_vehicles': total_vehicles,
                'total_stops': total_stops,
                'avg_stops_per_vehicle': avg_stops,
                'total_tonnage': round(total_tonnage, 2),
                'neighborhoods_covered': len(all_neighborhoods),
                'vehicles_with_routes': vehicles_with_routes,
                'date': routes_data.get('date'),
                'day': routes_data.get('day')
            }
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
