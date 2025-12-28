"""
CSV dosyasından routes_api.json formatında JSON dosyası oluşturur.
güncel_v6_fullvehicle.py ile tam uyumlu çalışır.

Ana kod (güncel_v6_fullvehicle.py) çıktıları:
  - rota_fullvehicle_YYYYMMDD.csv
  - routes_api_YYYYMMDD.json

Bu script CSV'yi JSON'a dönüştürür veya mevcut JSON'u günceller.
"""

import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import sys
import os

# Script'in bulunduğu klasör
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "full_dataset"
PATH_START_POSITIONS = DATA_DIR / "vehicle_start_positions.json"


def load_start_positions():
    """Araç başlangıç konumlarını yükle"""
    if PATH_START_POSITIONS.exists():
        with open(PATH_START_POSITIONS, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {v['vehicle_id']: v['start_position'] for v in data['vehicles']}
    return {}


def csv_to_routes_api(csv_path, output_path=None, date_str=None):
    """
    Ana kodun ürettiği CSV dosyasını routes_api.json formatına dönüştürür.
    
    Args:
        csv_path: Giriş CSV dosyasının yolu
        output_path: Çıkış JSON dosyasının yolu (None ise otomatik oluşturulur)
        date_str: Tarih string'i (None ise dosya adından çıkarılır)
    
    Returns:
        dict: Oluşturulan JSON verisi
    """
    csv_path = Path(csv_path)
    
    # Tarihi dosya adından çıkar (rota_fullvehicle_20251219.csv -> 2025-12-19)
    if date_str is None:
        filename = csv_path.stem  # rota_fullvehicle_20251219
        date_part = filename.split('_')[-1]  # 20251219
        if len(date_part) == 8 and date_part.isdigit():
            date_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Output path - her zaman aynı dosya adı (arayüz entegrasyonu için)
    if output_path is None:
        output_path = csv_path.parent / "routes_api.json"
    
    # CSV dosyasını oku
    df = pd.read_csv(csv_path)
    
    # Tarih bilgilerini oluştur
    base_date = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = base_date.strftime("%A").upper()
    
    # Başlangıç konumlarını yükle
    start_positions = load_start_positions()
    
    # Araç türü mapping
    vehicle_type_mapping = {
        'CRANE VEHICLE': 'Crane Vehicle',
        'LARGE GARBAGE TRUCK': 'Large Garbage Truck',
        'SMALL GARBAGE TRUCK': 'Small Garbage Truck'
    }
    
    vehicles = []
    
    # Her bir araç için grupla
    for vehicle_id in df['vehicle_id'].unique():
        vehicle_df = df[df['vehicle_id'] == vehicle_id].copy()
        vehicle_df = vehicle_df.sort_values('step')
        
        # Araç bilgilerini al
        first_row = vehicle_df.iloc[0]
        vehicle_name = first_row['vehicle_name']
        vehicle_type = str(first_row['vehicle_type']).upper()
        vehicle_category = first_row.get('vehicle_category', 'LARGE')
        vehicle_capacity = first_row.get('vehicle_capacity', 8.0)
        is_crane = first_row.get('is_crane', False)
        
        # Araç türünü dönüştür
        mapped_type = vehicle_type_mapping.get(vehicle_type, vehicle_type)
        
        # Başlangıç konumu
        if vehicle_id in start_positions:
            start_pos = start_positions[vehicle_id]
        else:
            # İlk satırdan al (BASLANGIC kaydı)
            start_row = vehicle_df[vehicle_df['container_idx'] == -2]
            if len(start_row) > 0:
                start_pos = {
                    'lat': float(start_row.iloc[0]['lat']),
                    'lon': float(start_row.iloc[0]['lon']),
                    'mahalle': start_row.iloc[0]['mahalle']
                }
            else:
                start_pos = {
                    'lat': float(first_row['lat']),
                    'lon': float(first_row['lon']),
                    'mahalle': first_row['mahalle']
                }
        
        # Rota noktalarını oluştur
        route = []
        total_distance = 0.0
        collected_tonnage = 0.0
        unloads = 0
        prev_lat, prev_lon = None, None
        
        for idx, row in vehicle_df.iterrows():
            container_idx = int(row['container_idx'])
            
            # Mesafe hesapla
            if prev_lat is not None:
                dist = ((row['lat'] - prev_lat)**2 + (row['lon'] - prev_lon)**2)**0.5 * 111 * 1.3
                total_distance += dist
            
            prev_lat, prev_lon = row['lat'], row['lon']
            
            # Toplanan tonaj
            if container_idx >= 0:
                collected_tonnage += row['demand_ton']
            
            # Boşaltma sayısı
            if container_idx == -1:
                unloads += 1
            
            stop = {
                "step": int(row['step']),
                "container_idx": container_idx,
                "lat": float(row['lat']),
                "lon": float(row['lon']),
                "mahalle": row['mahalle'],
                "tip": row.get('tip', 'UNKNOWN'),
                "demand_ton": round(float(row['demand_ton']), 4),
                "hour": int(row['hour']),
                "load_ton": round(float(row['load_ton']), 2),
                "street_width": float(row.get('street_width', 10.0)),
                "arrival_time": base_date.replace(hour=int(row['hour'])).strftime("%Y-%m-%dT%H:%M:%S")
            }
            route.append(stop)
        
        # Gerçek durak sayısı (başlangıç ve boşaltma hariç)
        actual_stops = len([r for r in route if r['container_idx'] >= 0])
        
        # Başlangıç ve bitiş saatleri
        min_hour = vehicle_df['hour'].min()
        max_hour = vehicle_df['hour'].max()
        
        # Araç objesini oluştur
        vehicle_obj = {
            "vehicle_id": int(vehicle_id),
            "vehicle_name": vehicle_name,
            "vehicle_type": mapped_type,
            "vehicle_category": vehicle_category,
            "capacity_ton": float(vehicle_capacity),
            "is_crane": bool(is_crane),
            "start_position": start_pos,
            "total_stops": actual_stops,
            "collected_tonnage": round(collected_tonnage, 2),
            "total_distance_km": round(total_distance, 2),
            "unloads": unloads,
            "start_time": base_date.replace(hour=int(min_hour)).strftime("%Y-%m-%dT%H:%M:%S"),
            "end_time": base_date.replace(hour=int(max_hour)).strftime("%Y-%m-%dT%H:%M:%S"),
            "route": route
        }
        
        vehicles.append(vehicle_obj)
    
    # Toplam durak sayısı (gerçek konteyner durakları)
    total_stops_all = sum(v['total_stops'] for v in vehicles)
    total_tonnage = sum(v['collected_tonnage'] for v in vehicles)
    total_distance = sum(v['total_distance_km'] for v in vehicles)
    
    # Ana JSON yapısı
    result = {
        "date": date_str,
        "day": day_name,
        "total_vehicles": len(vehicles),
        "total_stops": total_stops_all,
        "total_tonnage": round(total_tonnage, 2),
        "total_distance_km": round(total_distance, 2),
        "vehicles": vehicles
    }
    
    # JSON dosyasına yaz
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # Ana kodun bir üst dizinindeki full_dataset klasörüne de kopyala
    parent_full_dataset = SCRIPT_DIR.parent / "full_dataset"
    if not parent_full_dataset.exists():
        parent_full_dataset.mkdir(parents=True, exist_ok=True)
    
    copy_path = parent_full_dataset / "routes_api.json"
    with open(copy_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"✅ JSON dosyası oluşturuldu: {output_path}")
    print(f"📋 Kopya oluşturuldu: {copy_path}")
    print(f"📅 Tarih: {date_str} ({day_name})")
    print(f"🚛 Toplam {len(vehicles)} araç")
    print(f"📍 Toplam {total_stops_all} durak")
    print(f"📦 Toplam {total_tonnage:.1f} ton")
    print(f"📏 Toplam {total_distance:.1f} km")
    
    return result


def convert_latest():
    """En son oluşturulan CSV dosyasını dönüştür"""
    csv_files = list(DATA_DIR.glob("rota_fullvehicle_*.csv"))
    if not csv_files:
        print("❌ Dönüştürülecek CSV dosyası bulunamadı!")
        return None
    
    # En yeni dosyayı bul
    latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)
    print(f"📂 Dönüştürülüyor: {latest_csv.name}")
    
    return csv_to_routes_api(latest_csv)


def convert_all():
    """Tüm CSV dosyalarını dönüştür"""
    csv_files = list(DATA_DIR.glob("rota_fullvehicle_*.csv"))
    if not csv_files:
        print("❌ Dönüştürülecek CSV dosyası bulunamadı!")
        return []
    
    results = []
    for csv_path in sorted(csv_files):
        print(f"\n{'='*50}")
        result = csv_to_routes_api(csv_path)
        results.append(result)
    
    return results


def watch_and_convert():
    """Ana kod çalıştığında otomatik dönüştür (basit polling)"""
    import time
    
    print("👀 CSV dosyaları izleniyor... (Ctrl+C ile çık)")
    last_files = set()
    
    while True:
        current_files = set(DATA_DIR.glob("rota_fullvehicle_*.csv"))
        new_files = current_files - last_files
        
        for csv_path in new_files:
            print(f"\n🆕 Yeni dosya bulundu: {csv_path.name}")
            csv_to_routes_api(csv_path)
        
        last_files = current_files
        time.sleep(2)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "--latest":
            # En son CSV'yi dönüştür
            convert_latest()
        
        elif arg == "--all":
            # Tüm CSV'leri dönüştür
            convert_all()
        
        elif arg == "--watch":
            # İzle ve otomatik dönüştür
            watch_and_convert()
        
        elif arg.endswith('.csv'):
            # Belirtilen CSV'yi dönüştür
            csv_path = Path(arg)
            if not csv_path.exists():
                csv_path = DATA_DIR / arg
            
            if csv_path.exists():
                csv_to_routes_api(csv_path)
            else:
                print(f"❌ Dosya bulunamadı: {arg}")
        
        else:
            print("Kullanım:")
            print("  python csv_to_routes_api.py --latest     # En son CSV'yi dönüştür")
            print("  python csv_to_routes_api.py --all        # Tüm CSV'leri dönüştür")
            print("  python csv_to_routes_api.py --watch      # Otomatik izle ve dönüştür")
            print("  python csv_to_routes_api.py dosya.csv    # Belirli CSV'yi dönüştür")
    
    else:
        # Varsayılan: en son CSV'yi dönüştür
        convert_latest()
