# ============================================================
# ML TABANLİ ROTA OPTİMİZASYONU v6 - TAM ARAÇ YÖNETİMİ
# - Crane: Sadece yeraltı konteynerlerini alabilir
# - Large: Dar sokaklara (< 5m) giremez
# - Small: Her yere girebilir
# - Kapasite dolunca boşaltma
# - Sokak genişliği kontrolü
# - tonnages.csv entegrasyonu
# ============================================================

import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.spatial import cKDTree
from datetime import datetime, timedelta
from collections import defaultdict
import pickle
import os
import time

# ============================================================
# PATHS & CONFIG
# ============================================================
# Script'in bulunduğu klasörü baz alarak Database klasörünü otomatik bul
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "full_dataset"
PATH_CONTAINERS_DETAIL = DATA_DIR / "container" / "konteyner_tipli.csv"
PATH_ROAD = DATA_DIR / "Yol-2025-12-16_13-38-47.json"
PATH_ROT = DATA_DIR / "neighbor_days_rotations.csv"
PATH_TONNAGES = DATA_DIR / "tonnages.csv"
PATH_POP = DATA_DIR / "mahalle_nufus.csv"
PATH_FLEET = DATA_DIR / "fleet.csv"
PATH_START_POSITIONS = DATA_DIR / "vehicle_start_positions.json"
PATH_MODEL = DATA_DIR / "route_ml_model_v6.pkl"
PATH_DISTANCE_CACHE = DATA_DIR / "distance_matrix_cache_v6.pkl"
PATH_STREET_WIDTH_CACHE = DATA_DIR / "street_width_cache.pkl"

# Config
START_MAH = "ALAADDINBEY"
UNLOAD_MAH = "YENIKENT"
UNLOAD_WAIT_MIN = 10
AVG_SPEED_KMH = 25.0
CONTAINER_SERVICE_SEC = 30
DAY_START_HOUR = 6
DAY_END_HOUR = 23
PEAK_MORNING = (7, 10)
PEAK_EVENING = (17, 20)
POP_THRESHOLD = 15

# Araç tipi kısıtlamaları (gerçekçi değerler)
VEHICLE_MIN_STREET_WIDTH = {
    "LARGE": 4.0,    # Large kamyon minimum 4m genişlik (dar ama girebilir)
    "CRANE": 5.0,    # Crane araç minimum 5m genişlik (vinç kolu için)
    "SMALL": 2.5,    # Small her yere girebilir
}

# Ay isimleri
AY_MAP = {
    "OCAK": 1, "ŞUBAT": 2, "MART": 3, "NİSAN": 4, "MAYIS": 5, "HAZİRAN": 6,
    "TEMMUZ": 7, "AĞUSTOS": 8, "EYLÜL": 9, "EKİM": 10, "KASIM": 11, "ARALIK": 12
}

# ============================================================
# HELPERS
# ============================================================
TR_MAP = str.maketrans({
    "Ç":"C","Ğ":"G","İ":"I","Ö":"O","Ş":"S","Ü":"U",
    "ç":"C","ğ":"G","i":"I","ı":"I","ö":"O","ş":"S","ü":"U",
})

def normalize_text_tr(s):
    if pd.isna(s): return ""
    s = str(s).strip().translate(TR_MAP).upper()
    for suffix in [" MAHALLESI", " MAHALLESİ", " MH.", " MH"]:
        s = s.replace(suffix, "")
    import re
    s = re.sub(r"[^0-9A-Z\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def haversine_km_vectorized(lon1, lat1, lon2, lat2):
    R = 6371.0088
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def is_peak_hour(hour):
    return (PEAK_MORNING[0] <= hour < PEAK_MORNING[1]) or (PEAK_EVENING[0] <= hour < PEAK_EVENING[1])

# ============================================================
# STREET WIDTH MANAGER - Sokak Genişliği Yönetimi
# ============================================================
class StreetWidthManager:
    """
    Yol JSON'dan sokak genişliklerini okur.
    Her konteyner için en yakın sokağın genişliğini bulur.
    """
    
    def __init__(self):
        self.street_segments = []  # [(lat1, lon1, lat2, lon2, width_m, mahalle), ...]
        self.container_widths = {}  # {container_idx: width_m}
        self.kdtree = None
        self.segment_coords = None
        
    def load_from_geojson(self, path):
        """GeoJSON'dan sokak genişliklerini yükle"""
        print("🛣️ Sokak genişlikleri yükleniyor...")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        centroids = []  # Segment ortaları için KDTree
        
        for feat in data['features']:
            props = feat.get('properties', {})
            geom = feat['geometry']
            
            # Genişlik - 0 veya çok büyük değerleri düzelt
            width_str = props.get('Genişlik(m)', '6')
            try:
                width = float(str(width_str).replace(',', '.'))
                # Veri temizleme: 0 veya aşırı değerleri düzelt
                if width <= 0 or width > 50:
                    width = 6.0  # Varsayılan normal sokak
            except:
                width = 6.0  # Varsayılan
            
            mahalle = normalize_text_tr(props.get('İdari Mahalle Adı', ''))
            
            if geom['type'] == 'LineString':
                coords = geom['coordinates']
            elif geom['type'] == 'MultiLineString':
                coords = [c for line in geom['coordinates'] for c in line]
            else:
                continue
            
            # Segment ortasını kaydet
            if len(coords) >= 2:
                mid_idx = len(coords) // 2
                mid_lon, mid_lat = coords[mid_idx]
                centroids.append((mid_lat, mid_lon))
                self.street_segments.append({
                    'lat': mid_lat,
                    'lon': mid_lon,
                    'width': width,
                    'mahalle': mahalle
                })
        
        # KDTree oluştur
        self.segment_coords = np.array(centroids)
        self.kdtree = cKDTree(self.segment_coords)
        
        print(f"✅ {len(self.street_segments)} sokak segmenti yüklendi")
        
        # İstatistikler
        widths = [s['width'] for s in self.street_segments]
        print(f"   Genişlik: min={min(widths):.1f}m, max={max(widths):.1f}m, ort={np.mean(widths):.1f}m")
        narrow = sum(1 for w in widths if w < 5)
        print(f"   Dar sokak (<5m): {narrow} ({100*narrow/len(widths):.1f}%)")
    
    def get_street_width(self, lat, lon):
        """Verilen koordinata en yakın sokağın genişliğini döndür"""
        if self.kdtree is None:
            return 10.0  # Varsayılan
        
        _, idx = self.kdtree.query([lat, lon])
        return self.street_segments[idx]['width']
    
    def map_containers_to_streets(self, containers_df):
        """Her konteyner için en yakın sokak genişliğini bul"""
        print("📍 Konteynerler sokaklara eşleniyor...")
        
        lats = containers_df['lat'].values
        lons = containers_df['lon'].values
        coords = np.column_stack([lats, lons])
        
        # Toplu KDTree sorgusu
        _, indices = self.kdtree.query(coords)
        
        widths = []
        for idx in indices:
            widths.append(self.street_segments[idx]['width'])
        
        containers_df['street_width'] = widths
        
        # İstatistik
        narrow_containers = (containers_df['street_width'] < 5).sum()
        print(f"✅ {len(containers_df)} konteyner eşlendi")
        print(f"   Dar sokaktaki konteyner (<5m): {narrow_containers} ({100*narrow_containers/len(containers_df):.1f}%)")
        
        return containers_df
    
    def save(self, path):
        with open(path, 'wb') as f:
            pickle.dump({
                'street_segments': self.street_segments,
                'segment_coords': self.segment_coords
            }, f)
    
    def load(self, path):
        if os.path.exists(path):
            with open(path, 'rb') as f:
                data = pickle.load(f)
                self.street_segments = data['street_segments']
                self.segment_coords = data['segment_coords']
                self.kdtree = cKDTree(self.segment_coords)
            return True
        return False

# ============================================================
# VEHICLE TYPE MANAGER - Araç Tipi Yönetimi
# ============================================================
class VehicleTypeManager:
    """
    Araç tiplerinin kısıtlamalarını yönetir:
    - CRANE: Yeraltı konteynerlerini alabilir, geniş sokak gerekir
    - LARGE: Yüksek kapasite, dar sokaklara giremez
    - SMALL: Düşük kapasite, her yere girebilir
    """
    
    def __init__(self, fleet_df):
        self.fleet = fleet_df.copy()
        self.categorize_vehicles()
        
    def categorize_vehicles(self):
        """Araçları tipine göre kategorize et"""
        self.fleet['vehicle_category'] = 'LARGE'  # Varsayılan
        
        # Crane araçlar
        crane_mask = self.fleet['vehicle_type_norm'].str.contains('CRANE', case=False, na=False)
        self.fleet.loc[crane_mask, 'vehicle_category'] = 'CRANE'
        
        # Small araçlar (kapasite < 6 ton)
        small_mask = (~crane_mask) & (self.fleet['capacity_ton'] < 6)
        self.fleet.loc[small_mask, 'vehicle_category'] = 'SMALL'
        
        # Large araçlar (kapasite >= 6 ton, crane değil)
        large_mask = (~crane_mask) & (self.fleet['capacity_ton'] >= 6)
        self.fleet.loc[large_mask, 'vehicle_category'] = 'LARGE'
        
        # Minimum sokak genişliği
        self.fleet['min_street_width'] = self.fleet['vehicle_category'].map(VEHICLE_MIN_STREET_WIDTH)
        
        # Özet
        print(f"\n🚛 ARAÇ KATEGORİLERİ:")
        for cat in ['CRANE', 'LARGE', 'SMALL']:
            count = (self.fleet['vehicle_category'] == cat).sum()
            if count > 0:
                cap_range = self.fleet[self.fleet['vehicle_category'] == cat]['capacity_ton']
                min_width = VEHICLE_MIN_STREET_WIDTH[cat]
                print(f"   {cat}: {count} araç, kapasite {cap_range.min():.1f}-{cap_range.max():.1f} ton, min sokak {min_width}m")
    
    def can_access_container(self, vehicle_row, container_row):
        """
        Araç bu konteynere erişebilir mi?
        Returns: (erişebilir, sebep)
        """
        vehicle_cat = vehicle_row['vehicle_category']
        is_underground = container_row.get('is_underground', False)
        street_width = container_row.get('street_width', 10.0)
        min_width = vehicle_row['min_street_width']
        
        # Kural 1: Yeraltı konteyner sadece CRANE alabilir
        if is_underground and vehicle_cat != 'CRANE':
            return False, "YERALTI_CRANE_ONLY"
        
        # Kural 2: CRANE sadece yeraltı alabilir (verimlilik için)
        # NOT: Bu kuralı esnetelim - crane boşta kalmasın
        # if not is_underground and vehicle_cat == 'CRANE':
        #     return False, "CRANE_UNDERGROUND_ONLY"
        
        # Kural 3: Sokak genişliği kontrolü
        if street_width < min_width:
            return False, f"SOKAK_DAR_{street_width:.1f}m<{min_width}m"
        
        return True, "OK"
    
    def get_accessible_mask(self, vehicle_row, containers_df):
        """
        Aracın erişebileceği konteynerlerin mask'ini döndür (vectorized)
        """
        vehicle_cat = vehicle_row['vehicle_category']
        min_width = vehicle_row['min_street_width']
        
        # Başlangıçta hepsi erişilebilir
        mask = np.ones(len(containers_df), dtype=bool)
        
        # Yeraltı kontrolü - sadece CRANE
        if vehicle_cat != 'CRANE':
            mask &= ~containers_df['is_underground'].values
        
        # Sokak genişliği kontrolü
        if 'street_width' in containers_df.columns:
            mask &= containers_df['street_width'].values >= min_width
        
        return mask

# ============================================================
# TONNAGE MANAGER (v4'ten)
# ============================================================
class TonnageManager:
    def __init__(self):
        self.monthly_data = {}
        
    def load_tonnages(self, path):
        print("📊 Tonaj verileri yükleniyor...")
        df = pd.read_csv(path, sep=",", engine="python", on_bad_lines="skip")
        
        for _, row in df.iterrows():
            ay_str = str(row["AY"]).strip().upper()
            yil = int(row["YIL"])
            ay = AY_MAP.get(ay_str, 1)
            
            daily_avg_col = [c for c in df.columns if "Ortalama" in c and "Günlük" in c]
            if daily_avg_col:
                daily_avg = float(str(row[daily_avg_col[0]]).replace(",", "."))
            else:
                daily_avg = 550
            
            self.monthly_data[(ay, yil)] = {"daily_avg": daily_avg}
        
        print(f"✅ Tonaj verisi: {len(self.monthly_data)} ay")
    
    def get_daily_tonnage(self, target_date):
        ay, yil = target_date.month, target_date.year
        if (ay, yil) in self.monthly_data:
            return self.monthly_data[(ay, yil)]["daily_avg"]
        if (ay, yil - 1) in self.monthly_data:
            return self.monthly_data[(ay, yil - 1)]["daily_avg"] * 1.03
        return 550
    
    def get_seasonal_factor(self, month):
        if month in [6, 7, 8]: return 1.15
        elif month in [12, 1, 2]: return 0.90
        return 1.0
    
    def get_weekday_factor(self, weekday):
        if weekday == 0: return 1.20
        elif weekday in [5, 6]: return 0.85
        return 1.0
    
    def distribute_to_neighborhoods(self, daily_tonnage, pop_df, day_neighborhoods):
        relevant_pop = pop_df[pop_df["mahalle_norm"].isin(day_neighborhoods)].copy()
        if len(relevant_pop) == 0:
            per_mah = daily_tonnage / max(len(day_neighborhoods), 1)
            return {m: per_mah for m in day_neighborhoods}
        
        total_pop = relevant_pop["nufus"].sum()
        if total_pop <= 0:
            per_mah = daily_tonnage / len(day_neighborhoods)
            return {m: per_mah for m in day_neighborhoods}
        
        mah_tonnage = {}
        for _, row in relevant_pop.iterrows():
            mah = row["mahalle_norm"]
            ratio = row["nufus"] / total_pop
            mah_tonnage[mah] = daily_tonnage * ratio
        
        min_tonnage = daily_tonnage / (len(day_neighborhoods) * 2)
        for mah in day_neighborhoods:
            if mah not in mah_tonnage:
                mah_tonnage[mah] = min_tonnage
        
        return mah_tonnage
    
    def distribute_to_containers(self, containers_df, mah_tonnage):
        containers_df = containers_df.copy()
        
        def get_capacity_vectorized(tips):
            caps = np.zeros(len(tips))
            tip_arr = tips.astype(str).str.upper()
            caps[tip_arr.str.contains("YERALTI", na=False)] = 3.0
            mask_770 = tip_arr.str.contains("770", na=False) & ~tip_arr.str.contains("YERALTI", na=False)
            caps[mask_770] = 0.77 * 0.25
            mask_400 = tip_arr.str.contains("400", na=False) & ~tip_arr.str.contains("YERALTI", na=False)
            caps[mask_400] = 0.40 * 0.25
            caps[caps == 0] = 0.5 * 0.25
            return caps
        
        containers_df["container_capacity"] = get_capacity_vectorized(containers_df["tip_norm"])
        mah_total_cap = containers_df.groupby("mahalle_norm")["container_capacity"].transform("sum")
        containers_df["mah_tonnage"] = containers_df["mahalle_norm"].map(mah_tonnage).fillna(0)
        containers_df["ratio"] = containers_df["container_capacity"] / mah_total_cap.replace(0, 1)
        containers_df["demand_ton"] = containers_df["mah_tonnage"] * containers_df["ratio"]
        containers_df["demand_ton"] = np.minimum(containers_df["demand_ton"], containers_df["container_capacity"] * 0.8)
        containers_df["demand_ton"] = np.maximum(containers_df["demand_ton"], containers_df["container_capacity"] * 0.3)
        
        return containers_df

# ============================================================
# FAST DISTANCE MATRIX
# ============================================================
class FastDistanceMatrix:
    def __init__(self):
        self.matrix = {}
        self.centroids = {}
        
    def build(self, containers_df):
        print("📐 Mesafe matrisi oluşturuluyor...")
        centroids = containers_df.groupby("mahalle_norm").agg({
            "lat": "mean", "lon": "mean"
        }).to_dict('index')
        
        self.centroids = {m: (v["lat"], v["lon"]) for m, v in centroids.items()}
        mahalles = list(self.centroids.keys())
        
        for i, m1 in enumerate(mahalles):
            for j, m2 in enumerate(mahalles):
                if i <= j:
                    lat1, lon1 = self.centroids[m1]
                    lat2, lon2 = self.centroids[m2]
                    dist = haversine_km_vectorized(lon1, lat1, lon2, lat2) * 1.3
                    self.matrix[(m1, m2)] = dist
                    self.matrix[(m2, m1)] = dist
        
        print(f"✅ Mesafe matrisi: {len(mahalles)} mahalle")
        
    def save(self, path):
        with open(path, 'wb') as f:
            pickle.dump({'matrix': self.matrix, 'centroids': self.centroids}, f)
            
    def load(self, path):
        if os.path.exists(path):
            with open(path, 'rb') as f:
                data = pickle.load(f)
                self.matrix = data['matrix']
                self.centroids = data['centroids']
            return True
        return False

# ============================================================
# ML ROUTE OPTIMIZER
# ============================================================
class MLRouteOptimizer:
    def __init__(self):
        self.weights = None
        self.trained = False
        
    def initialize_weights(self):
        self.weights = np.array([
            -2.0,    # 0: mesafe (yakın tercih)
            2.5,     # 1: talep (yüksek talep tercih)
            -0.5,    # 2: doluluk oranı
            -100.0,  # 3: peak penalty
            -0.3,    # 4: boşaltma uzaklığı
            3.0,     # 5: yakınlık bonusu
            1.5,     # 6: kapasite uyumu bonusu
            2.0,     # 7: sokak uyumu bonusu (YENİ)
        ])
        self.trained = True
        
    def train(self):
        print("🧠 ML Model eğitiliyor...")
        self.initialize_weights()
        noise = np.random.normal(0, 0.05, len(self.weights))
        self.weights += noise
        print(f"✅ Model ağırlıkları: {self.weights.round(2)}")
        return self
    
    def predict_scores_batch(self, features):
        if not self.trained:
            self.initialize_weights()
        return np.dot(features, self.weights)
    
    def save(self, path):
        with open(path, 'wb') as f:
            pickle.dump({'weights': self.weights, 'trained': self.trained}, f)
            
    def load(self, path):
        if os.path.exists(path):
            with open(path, 'rb') as f:
                data = pickle.load(f)
                self.weights = data['weights']
                self.trained = data['trained']
            # Eski model 7 ağırlık, yeni 8 ağırlık
            if len(self.weights) < 8:
                self.weights = np.append(self.weights, 2.0)
            return True
        return False

# ============================================================
# VERİ YÜKLEMELERİ
# ============================================================
print("="*60)
print("📦 VERİLER YÜKLENİYOR - TAM ARAÇ YÖNETİMİ")
print("="*60)
start_load = time.time()

# Konteynerler
containers_df = pd.read_csv(PATH_CONTAINERS_DETAIL)
containers_df.columns = [c.strip().lower() for c in containers_df.columns]
lat_col = next((c for c in containers_df.columns if 'lat' in c or 'enlem' in c), None)
lon_col = next((c for c in containers_df.columns if 'lon' in c or 'boylam' in c), None)
mah_col = next((c for c in containers_df.columns if 'mahalle' in c), None)
tip_col = next((c for c in containers_df.columns if 'tip' in c or 'type' in c), None)

containers_df = containers_df.dropna(subset=[lat_col, lon_col])
containers_df["lat"] = pd.to_numeric(containers_df[lat_col], errors="coerce")
containers_df["lon"] = pd.to_numeric(containers_df[lon_col], errors="coerce")
containers_df = containers_df.dropna(subset=["lat", "lon"])
containers_df["mahalle_norm"] = containers_df[mah_col].apply(normalize_text_tr) if mah_col else "UNKNOWN"
containers_df["tip_norm"] = containers_df[tip_col].apply(lambda x: str(x).upper().strip() if pd.notna(x) else "UNKNOWN") if tip_col else "UNKNOWN"
containers_df["is_collectible"] = ~containers_df["tip_norm"].str.contains("BILINMIYOR|UNKNOWN", case=False, na=True)
containers_df["is_underground"] = containers_df["tip_norm"].str.contains("YERALTI", case=False, na=False)

print(f"✅ Konteyner: {len(containers_df)} (toplanabilir: {containers_df['is_collectible'].sum()}, yeraltı: {containers_df['is_underground'].sum()})")

# Nüfus
pop_df = pd.read_csv(PATH_POP, sep=";")
pop_df["mahalle_norm"] = pop_df["mahalle"].apply(normalize_text_tr)
pop_map = pop_df.set_index("mahalle_norm")["nufus"].to_dict()
containers_df["nufus"] = containers_df["mahalle_norm"].map(pop_map).fillna(0)
containers_df["is_high_pop"] = containers_df["nufus"] >= POP_THRESHOLD

# Filo
fleet_df = pd.read_csv(PATH_FLEET)
fleet_df["vehicle_type_norm"] = fleet_df["vehicle_type"].apply(lambda x: str(x).upper().strip())
fleet_df["is_crane"] = fleet_df["vehicle_type_norm"].str.contains("CRANE", case=False)
print(f"✅ Filo: {len(fleet_df)} araç (Crane: {fleet_df['is_crane'].sum()})")

# Araç Başlangıç Konumları
VEHICLE_START_POSITIONS = {}
if PATH_START_POSITIONS.exists():
    with open(PATH_START_POSITIONS, 'r', encoding='utf-8') as f:
        start_data = json.load(f)
    for v in start_data['vehicles']:
        VEHICLE_START_POSITIONS[v['vehicle_id']] = {
            'lat': v['start_position']['lat'],
            'lon': v['start_position']['lon'],
            'mahalle': v['start_position']['mahalle']
        }
    print(f"✅ Başlangıç konumları: {len(VEHICLE_START_POSITIONS)} araç (Referans: {start_data['reference_date']} {start_data['reference_time']})")
    # Sadece start positions'da olan araçları filtrele
    fleet_df = fleet_df[fleet_df['vehicle_id'].isin(VEHICLE_START_POSITIONS.keys())].reset_index(drop=True)
    print(f"   Aktif araç sayısı: {len(fleet_df)}")
else:
    print("⚠️ Başlangıç konumları bulunamadı, varsayılan kullanılacak")

# Sokak genişliği
street_mgr = StreetWidthManager()
if not street_mgr.load(PATH_STREET_WIDTH_CACHE):
    street_mgr.load_from_geojson(PATH_ROAD)
    street_mgr.save(PATH_STREET_WIDTH_CACHE)
else:
    print(f"✅ Sokak genişlikleri önbellekten yüklendi ({len(street_mgr.street_segments)} segment)")

# Konteynerlere sokak genişliği ekle
containers_df = street_mgr.map_containers_to_streets(containers_df)

# Araç tipi yöneticisi
vehicle_mgr = VehicleTypeManager(fleet_df)

# Gün rotasyonu
rot_df = pd.read_csv(PATH_ROT, sep=";")
rot_df["mahalle_norm"] = rot_df["MAHALLE ADI"].apply(normalize_text_tr)
DOW_MAP = {"MONDAY": 0, "TUESDAY": 1, "WEDNESDAY": 2, "THURSDAY": 3, "FRIDAY": 4, "SATURDAY": 5, "SUNDAY": 6}

def parse_days(freq_text):
    if pd.isna(freq_text): return []
    s = str(freq_text).upper().strip()
    if not s or s == "0": return []
    if "NIGHT" in s: return list(range(7))
    return [idx for name, idx in DOW_MAP.items() if name in s]

freq_col = next((c for c in rot_df.columns if "frequency" in c.lower()), None)
rot_df["days_list"] = rot_df[freq_col].apply(parse_days) if freq_col else [[]] * len(rot_df)
rot_days = rot_df.groupby("mahalle_norm")["days_list"].apply(lambda x: sorted(set(d for lst in x for d in lst))).to_dict()

# Tonnage Manager
tonnage_mgr = TonnageManager()
tonnage_mgr.load_tonnages(PATH_TONNAGES)

# Mesafe matrisi
dist_matrix = FastDistanceMatrix()
if not dist_matrix.load(PATH_DISTANCE_CACHE):
    dist_matrix.build(containers_df)
    dist_matrix.save(PATH_DISTANCE_CACHE)

# ML Model
ml_model = MLRouteOptimizer()
if not ml_model.load(PATH_MODEL):
    ml_model.train()
    ml_model.save(PATH_MODEL)

# Mahalle kategorileri
mah_stats = containers_df.groupby("mahalle_norm").agg({
    "nufus": "first", "is_high_pop": "first"
}).to_dict('index')
high_pop_mahs = [m for m, v in mah_stats.items() if v.get("is_high_pop", False)]
low_pop_mahs = [m for m, v in mah_stats.items() if not v.get("is_high_pop", False)]

print(f"\n⏱️ Veri yükleme: {time.time() - start_load:.2f} saniye")

# ============================================================
# TAM ARAÇ YÖNETİMLİ ROTA PLANLAMA
# ============================================================
def plan_full_vehicle_routes(dow: int, target_date: datetime):
    """
    Tam araç yönetimli rota planlama:
    - Crane → yeraltı
    - Large → geniş sokaklar
    - Small → dar sokaklar dahil her yer
    - Kapasite dolunca boşaltma
    """
    global containers_df
    
    print(f"\n{'='*60}")
    print(f"🚛 TAM ARAÇ YÖNETİMLİ ROTA - {target_date.strftime('%Y-%m-%d %A')}")
    print(f"{'='*60}")
    
    # 1. Günlük tonaj hedefi
    daily_target = tonnage_mgr.get_daily_tonnage(target_date)
    seasonal_factor = tonnage_mgr.get_seasonal_factor(target_date.month)
    weekday_factor = tonnage_mgr.get_weekday_factor(dow)
    adjusted_target = daily_target * seasonal_factor * weekday_factor
    
    print(f"\n📊 TONAJ: {daily_target:.1f} × {seasonal_factor:.2f} × {weekday_factor:.2f} = {adjusted_target:.1f} ton")
    
    # 2. O gün toplanacak mahalleler
    day_neighborhoods = [m for m, days in rot_days.items() if dow in days]
    if not day_neighborhoods:
        print("⚠️ Bu gün için mahalle yok!")
        return [], pd.DataFrame()
    
    # 3. Mahallelere tonaj dağıt
    mah_tonnage = tonnage_mgr.distribute_to_neighborhoods(adjusted_target, pop_df, day_neighborhoods)
    
    # 4. Toplanacak konteynerler
    day_containers = containers_df[
        (containers_df["mahalle_norm"].isin(day_neighborhoods)) &
        (containers_df["is_collectible"])
    ].copy().reset_index(drop=True)
    
    # 5. Konteynerlere tonaj dağıt
    day_containers = tonnage_mgr.distribute_to_containers(day_containers, mah_tonnage)
    
    # Konteyner istatistikleri
    underground_count = day_containers['is_underground'].sum()
    narrow_street_count = (day_containers['street_width'] < 5).sum()
    
    print(f"\n📦 KONTEYNER ANALİZİ:")
    print(f"   Toplam: {len(day_containers)}")
    print(f"   Yeraltı: {underground_count} (sadece CRANE alabilir)")
    print(f"   Dar sokak (<5m): {narrow_street_count} (sadece SMALL girebilir)")
    print(f"   Toplam talep: {day_containers['demand_ton'].sum():.1f} ton")
    
    # Mahalleleri kategorize
    day_high_pop = [m for m in high_pop_mahs if m in day_neighborhoods]
    day_low_pop = [m for m in low_pop_mahs if m in day_neighborhoods]
    
    # Boşaltma pozisyonu
    unload_containers = containers_df[containers_df["mahalle_norm"] == UNLOAD_MAH]
    default_start = day_containers[day_containers["mahalle_norm"] == START_MAH]
    default_start_pos = (default_start.iloc[0]["lat"], default_start.iloc[0]["lon"]) if len(default_start) > 0 else (day_containers.iloc[0]["lat"], day_containers.iloc[0]["lon"])
    unload_pos = (unload_containers.iloc[0]["lat"], unload_containers.iloc[0]["lon"]) if len(unload_containers) > 0 else default_start_pos
    
    # Araçların gerçek başlangıç konumları (start positions JSON'dan)
    print(f"\n📍 ARAÇ BAŞLANGIÇ KONUMLARI:")
    vehicles_with_real_start = 0
    for vid, pos_data in VEHICLE_START_POSITIONS.items():
        print(f"   Araç {vid}: {pos_data['mahalle']} ({pos_data['lat']:.4f}, {pos_data['lon']:.4f})")
        vehicles_with_real_start += 1
        if vehicles_with_real_start >= 5:  # İlk 5 tanesini göster
            remaining = len(VEHICLE_START_POSITIONS) - 5
            if remaining > 0:
                print(f"   ... ve {remaining} araç daha")
            break
    
    # Numpy arrays
    container_lats = day_containers["lat"].values
    container_lons = day_containers["lon"].values
    container_demands = day_containers["demand_ton"].values
    container_mahalles = day_containers["mahalle_norm"].values
    container_high_pop = day_containers["is_high_pop"].values
    container_underground = day_containers["is_underground"].values
    container_street_widths = day_containers["street_width"].values
    
    # Araçları hazırla - gerçek başlangıç konumlarıyla
    fleet_sorted = vehicle_mgr.fleet.sort_values("capacity_ton", ascending=False)
    
    vehicles_data = []
    for _, row in fleet_sorted.iterrows():
        vid = row["vehicle_id"]
        # Araç için gerçek başlangıç konumu varsa kullan, yoksa varsayılan
        if vid in VEHICLE_START_POSITIONS:
            start_pos = (VEHICLE_START_POSITIONS[vid]['lat'], VEHICLE_START_POSITIONS[vid]['lon'])
            start_mahalle = VEHICLE_START_POSITIONS[vid]['mahalle']
        else:
            start_pos = default_start_pos
            start_mahalle = START_MAH
        
        vehicles_data.append({
            "id": vid,
            "name": row["vehicle_name"],
            "type": row["vehicle_type_norm"],
            "category": row["vehicle_category"],
            "capacity": row["capacity_ton"],
            "min_street_width": row["min_street_width"],
            "is_crane": row["is_crane"],
            "load": 0.0,
            "pos": start_pos,
            "start_pos": start_pos,  # Başlangıç konumunu sakla
            "start_mahalle": start_mahalle,
            "time": datetime(target_date.year, target_date.month, target_date.day, DAY_START_HOUR, 0, 0),
            "route": [],
            "distance": 0.0,
            "unloads": 0,
            "collected_tonnage": 0.0,
            "skipped_narrow": 0,
            "skipped_underground": 0,
        })
        
        # İlk durak olarak başlangıç konumunu ekle
        vehicles_data[-1]["route"].append({
            "container_idx": -2,  # -2 = başlangıç noktası
            "mahalle": start_mahalle,
            "lat": start_pos[0],
            "lon": start_pos[1],
            "tip": "BASLANGIC",
            "demand_ton": 0,
            "hour": DAY_START_HOUR,
            "load_ton": 0,
            "street_width": 99,
        })
    
    collected = np.zeros(len(day_containers), dtype=bool)
    
    # Zaman dilimleri
    time_slots = [
        (6, 7, day_low_pop + day_high_pop, "Erken"),
        (7, 10, day_low_pop, "Sabah Peak"),
        (10, 17, day_low_pop + day_high_pop, "Gündüz"),
        (17, 20, day_low_pop, "Akşam Peak"),
        (20, 23, day_high_pop, "Gece"),
    ]
    
    print(f"\n🚛 ROTA OLUŞTURULUYOR...")
    
    for slot_start, slot_end, allowed_mahs, slot_name in time_slots:
        allowed_set = set(allowed_mahs)
        slot_mask = np.array([m in allowed_set for m in container_mahalles]) & ~collected
        
        if not np.any(slot_mask):
            continue
        
        is_peak_slot = (slot_start == 7 and slot_end == 10) or (slot_start == 17 and slot_end == 20)
        
        print(f"⏰ [{slot_start:02d}-{slot_end:02d}] {slot_name}: {np.sum(slot_mask)} konteyner")
        
        for v in vehicles_data:
            if v["time"].hour >= slot_end:
                continue
            
            if v["time"].hour < slot_start:
                v["time"] = v["time"].replace(hour=slot_start, minute=0)
            
            while v["time"].hour < slot_end:
                available_mask = slot_mask & ~collected
                available_indices = np.where(available_mask)[0]
                
                if len(available_indices) == 0:
                    break
                
                # Peak slotta yüksek nüfuslu engelle
                if is_peak_slot:
                    not_high_pop = ~container_high_pop[available_indices]
                    available_indices = available_indices[not_high_pop]
                    if len(available_indices) == 0:
                        break
                
                # ========================================
                # ARAÇ TİPİ KISITLAMALARI
                # ========================================
                
                # 1. Yeraltı kontrolü - sadece CRANE
                if not v["is_crane"]:
                    not_underground = ~container_underground[available_indices]
                    skipped = np.sum(~not_underground)
                    if skipped > 0:
                        v["skipped_underground"] += skipped
                    available_indices = available_indices[not_underground]
                    if len(available_indices) == 0:
                        break
                
                # 2. Sokak genişliği kontrolü
                street_ok = container_street_widths[available_indices] >= v["min_street_width"]
                skipped_narrow = np.sum(~street_ok)
                if skipped_narrow > 0:
                    v["skipped_narrow"] += skipped_narrow
                available_indices = available_indices[street_ok]
                if len(available_indices) == 0:
                    break
                
                # ========================================
                
                current_hour = v["time"].hour
                
                # Mesafeler
                dists = np.sqrt(
                    (container_lats[available_indices] - v["pos"][0])**2 +
                    (container_lons[available_indices] - v["pos"][1])**2
                ) * 111
                
                # Feature matrix (8 feature)
                n_avail = len(available_indices)
                features = np.zeros((n_avail, 8))
                features[:, 0] = dists
                features[:, 1] = container_demands[available_indices]
                features[:, 2] = v["load"] / v["capacity"]
                features[:, 3] = np.where(
                    is_peak_hour(current_hour) & container_high_pop[available_indices],
                    10.0, 0.0
                )
                features[:, 4] = np.sqrt(
                    (container_lats[available_indices] - unload_pos[0])**2 +
                    (container_lons[available_indices] - unload_pos[1])**2
                ) * 111
                features[:, 5] = np.where(dists < 0.5, 1.0, 0.0)
                capacity_match = container_demands[available_indices] / v["capacity"]
                features[:, 6] = np.where((capacity_match > 0.05) & (capacity_match < 0.3), 1.0, 0.0)
                # Sokak uyumu bonusu - sokak ne kadar geniş araç için uygunsa o kadar bonus
                street_margin = container_street_widths[available_indices] - v["min_street_width"]
                features[:, 7] = np.where(street_margin > 2, 1.0, 0.0)  # 2m+ margin = bonus
                
                scores = ml_model.predict_scores_batch(features)
                
                best_local_idx = np.argmax(scores)
                best_idx = available_indices[best_local_idx]
                best_dist = dists[best_local_idx]
                
                demand = container_demands[best_idx]
                
                # ========================================
                # KAPASİTE KONTROLÜ - BOŞALTMA
                # ========================================
                if v["load"] + demand > v["capacity"]:
                    unload_dist = haversine_km_vectorized(
                        v["pos"][1], v["pos"][0],
                        unload_pos[1], unload_pos[0]
                    ) * 1.3
                    travel_min = (unload_dist / AVG_SPEED_KMH) * 60 + UNLOAD_WAIT_MIN
                    v["time"] += timedelta(minutes=travel_min)
                    v["pos"] = unload_pos
                    v["load"] = 0.0
                    v["distance"] += unload_dist
                    v["unloads"] += 1
                    
                    v["route"].append({
                        "container_idx": -1,
                        "mahalle": UNLOAD_MAH,
                        "lat": unload_pos[0],
                        "lon": unload_pos[1],
                        "tip": "BOŞALTMA",
                        "demand_ton": 0,
                        "hour": v["time"].hour,
                        "load_ton": 0,
                        "street_width": 99,
                    })
                    
                    if v["time"].hour >= slot_end:
                        break
                    continue
                
                # ========================================
                
                real_dist = best_dist * 1.3
                travel_min = (real_dist / AVG_SPEED_KMH) * 60 + CONTAINER_SERVICE_SEC / 60
                
                new_time = v["time"] + timedelta(minutes=travel_min)
                is_high_pop_container = container_high_pop[best_idx]
                
                if is_high_pop_container and is_peak_hour(new_time.hour):
                    collected[best_idx] = True
                    continue
                
                v["time"] = new_time
                v["pos"] = (container_lats[best_idx], container_lons[best_idx])
                v["load"] += demand
                v["distance"] += real_dist
                v["collected_tonnage"] += demand
                
                v["route"].append({
                    "container_idx": int(best_idx),
                    "mahalle": container_mahalles[best_idx],
                    "lat": float(container_lats[best_idx]),
                    "lon": float(container_lons[best_idx]),
                    "tip": day_containers.iloc[best_idx]["tip_norm"],
                    "demand_ton": float(demand),
                    "hour": v["time"].hour,
                    "load_ton": round(v["load"], 2),
                    "street_width": float(container_street_widths[best_idx]),
                })
                
                collected[best_idx] = True
                
                if v["time"].hour >= DAY_END_HOUR:
                    break
    
    # Sonuçlar
    all_routes = []
    for v in vehicles_data:
        for i, stop in enumerate(v["route"]):
            all_routes.append({
                "vehicle_id": v["id"],
                "vehicle_name": v["name"],
                "vehicle_type": v["type"],
                "vehicle_category": v["category"],
                "vehicle_capacity": v["capacity"],
                "is_crane": v["is_crane"],
                "step": i + 1,
                **stop
            })
    
    result_df = pd.DataFrame(all_routes)
    
    # İstatistikler
    total_collected = np.sum(collected)
    total_tonnage_collected = sum(v["collected_tonnage"] for v in vehicles_data)
    
    print(f"\n{'='*60}")
    print("📊 SONUÇ İSTATİSTİKLERİ")
    print(f"{'='*60}")
    print(f"🎯 Hedef tonaj: {adjusted_target:.1f} ton")
    print(f"✅ Toplanan tonaj: {total_tonnage_collected:.1f} ton ({100*total_tonnage_collected/adjusted_target:.1f}%)")
    print(f"📦 Toplanan konteyner: {total_collected} / {len(day_containers)} ({100*total_collected/len(day_containers):.1f}%)")
    print(f"🚛 Aktif araç: {len([v for v in vehicles_data if len(v['route']) > 0])}")
    print(f"📏 Toplam mesafe: {sum(v['distance'] for v in vehicles_data):.1f} km")
    print(f"🔄 Toplam boşaltma: {sum(v['unloads'] for v in vehicles_data)}")
    
    # Araç kategorisi bazlı özet
    print(f"\n--- Araç Kategorisi Performansı ---")
    for cat in ['CRANE', 'LARGE', 'SMALL']:
        cat_vehicles = [v for v in vehicles_data if v['category'] == cat and len(v['route']) > 0]
        if cat_vehicles:
            total_ton = sum(v['collected_tonnage'] for v in cat_vehicles)
            total_stops = sum(len([r for r in v['route'] if r['container_idx'] != -1]) for v in cat_vehicles)
            total_unloads = sum(v['unloads'] for v in cat_vehicles)
            print(f"   {cat}: {len(cat_vehicles)} araç, {total_ton:.1f} ton, {total_stops} durak, {total_unloads} boşaltma")
    
    # Toplanamayan konteyner analizi
    not_collected = day_containers[~collected]
    if len(not_collected) > 0:
        print(f"\n--- Toplanamayan Konteynerler ({len(not_collected)}) ---")
        underground_not = not_collected['is_underground'].sum()
        narrow_not = (not_collected['street_width'] < 5).sum()
        print(f"   Yeraltı: {underground_not}")
        print(f"   Dar sokak (<5m): {narrow_not}")
    
    # Peak analizi
    if not result_df.empty:
        print(f"\n--- Peak Saat Analizi ---")
        for peak_name, (start, end) in [("Sabah Peak (07-10)", (7, 10)), ("Akşam Peak (17-20)", (17, 20))]:
            peak_data = result_df[
                (result_df["hour"] >= start) & 
                (result_df["hour"] < end) & 
                (result_df["container_idx"] != -1)
            ]
            if len(peak_data) > 0:
                high_in_peak = len([m for m in peak_data["mahalle"].unique() if m in high_pop_mahs])
                print(f"{peak_name}: {len(peak_data)} konteyner, yüksek nüfuslu mahalle: {high_in_peak}")
    
    return vehicles_data, result_df

# ============================================================
# ÇALIŞTIR
# ============================================================
if __name__ == "__main__":
    # 19 Aralık 2025 - Start positions referans tarihi
    target_date = datetime(2025, 12, 19)
    dow = target_date.weekday()  # Cuma = 4
    
    start_ts = time.time()
    vehicles, result_df = plan_full_vehicle_routes(dow, target_date)
    elapsed = time.time() - start_ts
    
    print(f"\n⏱️ Toplam süre: {elapsed:.2f} saniye")
    
    if not result_df.empty:
        output_path = DATA_DIR / f"rota_fullvehicle_{target_date.strftime('%Y%m%d')}.csv"
        result_df.to_csv(output_path, index=False)
        print(f"✅ Kaydedildi: {output_path}")
        
        # JSON formatında da kaydet
        json_output = {
            "date": target_date.strftime("%Y-%m-%d"),
            "day": target_date.strftime("%A").upper(),
            "total_vehicles": len([v for v in vehicles if len(v['route']) > 1]),
            "total_stops": len(result_df[result_df['container_idx'] >= 0]),
            "vehicles": []
        }
        
        for v in vehicles:
            if len(v['route']) > 1:  # Sadece başlangıç dışında durak varsa
                json_output["vehicles"].append({
                    "vehicle_id": v['id'],
                    "vehicle_name": v['name'],
                    "vehicle_type": v['type'],
                    "vehicle_category": v['category'],
                    "capacity_ton": v['capacity'],
                    "start_position": {
                        "lat": v['start_pos'][0],
                        "lon": v['start_pos'][1],
                        "mahalle": v['start_mahalle']
                    },
                    "total_stops": len([r for r in v['route'] if r['container_idx'] >= 0]),
                    "collected_tonnage": round(v['collected_tonnage'], 2),
                    "total_distance_km": round(v['distance'], 2),
                    "unloads": v['unloads'],
                    "route": v['route']
                })
        
        json_path = DATA_DIR / f"routes_api_{target_date.strftime('%Y%m%d')}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_output, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON kaydedildi: {json_path}")
