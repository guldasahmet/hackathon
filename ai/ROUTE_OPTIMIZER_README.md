# 🚛 ML Tabanlı Çöp Toplama Rota Optimizasyonu v6

Nilüfer Belediyesi için geliştirilmiş, makine öğrenmesi destekli akıllı çöp toplama rota optimizasyon sistemi.

## 📋 İçindekiler

- [Proje Hakkında](#-proje-hakkında)
- [Özellikler](#-özellikler)
- [Kurulum](#-kurulum)
- [Kullanım](#-kullanım)
- [Veri Dosyaları](#-veri-dosyaları)
- [Sistem Mimarisi](#-sistem-mimarisi)
- [Araç Yönetimi](#-araç-yönetimi)
- [Algoritma Detayları](#-algoritma-detayları)
- [Çıktılar](#-çıktılar)

---

## 🎯 Proje Hakkında

Bu proje, belediye çöp toplama operasyonlarını optimize etmek için geliştirilmiş bir rota planlama sistemidir. Makine öğrenmesi algoritmaları kullanarak:

- **Araç tipine göre** en uygun rotaları belirler
- **Sokak genişliğini** dikkate alarak erişilebilirlik kontrolü yapar
- **Nüfus yoğunluğuna** göre tonaj dağılımı hesaplar
- **Trafik yoğunluğunu** (peak saatler) göz önünde bulundurur
- **Kapasite yönetimi** ile boşaltma zamanlaması optimize eder

---

## ✨ Özellikler

### 🚛 Akıllı Araç Yönetimi
| Araç Tipi | Kapasite | Min. Sokak Genişliği | Özellik |
|-----------|----------|---------------------|---------|
| **CRANE** | Değişken | 5.0m | Sadece yeraltı konteynerlerini alabilir |
| **LARGE** | ≥6 ton | 4.0m | Yüksek kapasiteli, dar sokaklara giremez |
| **SMALL** | <6 ton | 2.5m | Her yere girebilir |

### 📊 Tonaj Optimizasyonu
- Aylık tonaj verilerine göre günlük hedef belirleme
- Mevsimsel faktörler (yaz +%15, kış -%10)
- Hafta içi/sonu faktörleri (Pazartesi +%20, hafta sonu -%15)
- Nüfusa oranla mahalle bazlı dağıtım

### ⏰ Zaman Dilimi Yönetimi
| Saat | Dilim | Hedef Mahalleler |
|------|-------|------------------|
| 06:00-07:00 | Erken | Tüm mahalleler |
| 07:00-10:00 | Sabah Peak | Düşük nüfuslu (trafik önleme) |
| 10:00-17:00 | Gündüz | Tüm mahalleler |
| 17:00-20:00 | Akşam Peak | Düşük nüfuslu (trafik önleme) |
| 20:00-23:00 | Gece | Yüksek nüfuslu |

### 🛣️ Sokak Genişliği Kontrolü
- GeoJSON'dan sokak genişliklerini okur
- Her konteynere en yakın sokağın genişliğini atar
- Araç tipine göre erişilebilirlik kontrolü yapar

---

## 🔧 Kurulum

### Gereksinimler

```bash
pip install numpy pandas scipy
```

### Python Sürümü
- Python 3.8 veya üzeri

### Dosya Yapısı

```
hackathonai/
├── güncel_v6_fullvehicle.py    # Ana script
├── README.md                    # Bu dosya
└── Database/
    ├── fleet.csv                # Araç filosu
    ├── mahalle_nufus.csv        # Nüfus verileri
    ├── neighbor_days_rotations.csv  # Toplama günleri
    ├── tonnages.csv             # Aylık tonaj verileri
    ├── Yol-2025-12-16_13-38-47.json  # Sokak genişlikleri
    └── container/
        └── konteyner_tipli.csv  # Konteyner verileri
```

---

## 🚀 Kullanım

### Temel Kullanım

```python
python güncel_v6_fullvehicle.py
```

### Özel Tarih için Çalıştırma

Script içinde tarihi değiştirin:

```python
if __name__ == "__main__":
    target_date = datetime(2025, 6, 25)  # İstediğiniz tarihi girin
    dow = target_date.weekday()
    
    vehicles, result_df = plan_full_vehicle_routes(dow, target_date)
```

### Programatik Kullanım

```python
from güncel_v6_fullvehicle import plan_full_vehicle_routes
from datetime import datetime

# Belirli bir gün için rota oluştur
target_date = datetime(2025, 7, 15)
dow = target_date.weekday()  # 0=Pazartesi, 6=Pazar

vehicles, result_df = plan_full_vehicle_routes(dow, target_date)

# Sonuçları incele
print(f"Toplam araç: {len(vehicles)}")
print(f"Toplam durak: {len(result_df)}")
```

---

## 📁 Veri Dosyaları

### 1. `fleet.csv` - Araç Filosu
Araç bilgilerini içerir.

| Sütun | Açıklama |
|-------|----------|
| vehicle_id | Araç ID |
| vehicle_name | Araç adı |
| vehicle_type | Araç tipi (CRANE, LARGE, SMALL) |
| capacity_ton | Kapasite (ton) |

### 2. `konteyner_tipli.csv` - Konteyner Verileri
Tüm konteynerlerin konum ve tip bilgileri.

| Sütun | Açıklama |
|-------|----------|
| lat/enlem | Enlem koordinatı |
| lon/boylam | Boylam koordinatı |
| mahalle | Mahalle adı |
| tip/type | Konteyner tipi (770L, 400L, YERALTI vb.) |

### 3. `mahalle_nufus.csv` - Nüfus Verileri
Mahalle bazlı nüfus bilgileri.

| Sütun | Açıklama |
|-------|----------|
| mahalle | Mahalle adı |
| nufus | Nüfus (bin) |

### 4. `neighbor_days_rotations.csv` - Toplama Günleri
Hangi mahallenin hangi gün toplanacağı.

| Sütun | Açıklama |
|-------|----------|
| MAHALLE ADI | Mahalle adı |
| frequency | Toplama günleri (MONDAY, TUESDAY vb.) |

### 5. `tonnages.csv` - Tonaj Verileri
Aylık çöp tonajı istatistikleri.

| Sütun | Açıklama |
|-------|----------|
| AY | Ay adı (OCAK, ŞUBAT vb.) |
| YIL | Yıl |
| Ortalama Günlük | Günlük ortalama tonaj |

### 6. `Yol-*.json` - Sokak Verileri (GeoJSON)
Sokak genişlikleri ve geometri bilgileri.

---

## 🏗️ Sistem Mimarisi

```
┌─────────────────────────────────────────────────────────────┐
│                    VERİ KATMANI                             │
├─────────────────────────────────────────────────────────────┤
│  fleet.csv │ konteyner.csv │ nufus.csv │ tonnages.csv │ JSON│
└──────┬──────────────┬───────────────┬───────────────┬───────┘
       │              │               │               │
       ▼              ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                   YÖNETİCİ SINIFLAR                         │
├─────────────────────────────────────────────────────────────┤
│ VehicleTypeManager │ StreetWidthManager │ TonnageManager    │
│ FastDistanceMatrix │ MLRouteOptimizer                       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              ROTA PLANLAMA MOTORİ                           │
├─────────────────────────────────────────────────────────────┤
│  plan_full_vehicle_routes()                                 │
│  - Günlük tonaj hesaplama                                   │
│  - Mahalle-konteyner eşleştirme                            │
│  - Zaman dilimi yönetimi                                    │
│  - Araç-konteyner ataması                                   │
│  - Kapasite ve boşaltma yönetimi                           │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      ÇIKTI                                  │
├─────────────────────────────────────────────────────────────┤
│  rota_fullvehicle_YYYYMMDD.csv                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚛 Araç Yönetimi

### Araç Kategorileri

#### CRANE (Vinçli Araç)
- **Görev:** Yeraltı konteynerlerini boşaltma
- **Kısıtlama:** Minimum 5m sokak genişliği gerekli
- **Özellik:** Vinç kolu ile yeraltı konteynerlerini kaldırır

#### LARGE (Büyük Kamyon)
- **Görev:** Yüksek kapasiteli toplama
- **Kısıtlama:** Minimum 4m sokak genişliği gerekli
- **Kapasite:** ≥6 ton

#### SMALL (Küçük Kamyon)
- **Görev:** Dar sokaklarda toplama
- **Kısıtlama:** Minimum 2.5m sokak genişliği
- **Kapasite:** <6 ton
- **Avantaj:** Her sokağa girebilir

### Erişilebilirlik Kuralları

```python
# Yeraltı konteyner → Sadece CRANE
if is_underground and vehicle_type != 'CRANE':
    return False

# Dar sokak → Araç tipine göre kontrol
if street_width < vehicle_min_width:
    return False
```

---

## 🧠 Algoritma Detayları

### ML Skor Hesaplama

Her konteyner için 8 özellikli skor hesaplanır:

| # | Özellik | Ağırlık | Açıklama |
|---|---------|---------|----------|
| 0 | Mesafe | -2.0 | Yakın konteynerler tercih edilir |
| 1 | Talep | +2.5 | Yüksek talepli konteynerler öncelikli |
| 2 | Doluluk | -0.5 | Aşırı dolu araçtan kaçınma |
| 3 | Peak Ceza | -100.0 | Peak saatte yoğun bölgelerden kaçınma |
| 4 | Boşaltma Uzaklığı | -0.3 | Boşaltma noktasına uzaklık |
| 5 | Yakınlık Bonus | +3.0 | Cluster halinde toplama |
| 6 | Kapasite Uyumu | +1.5 | Araç kapasitesine uyum |
| 7 | Sokak Uyumu | +2.0 | Araç-sokak uyumu bonusu |

### Rota Oluşturma Adımları

1. **Günlük Tonaj Hesaplama**
   ```
   Hedef = Baz Tonaj × Mevsim Faktörü × Hafta Faktörü
   ```

2. **Mahalle Seçimi**
   - Gün rotasyonuna göre toplanacak mahalleler belirlenir

3. **Tonaj Dağıtımı**
   - Nüfusa oranla mahallelere tonaj atanır
   - Konteyner kapasitesine göre konteyner bazlı dağıtım

4. **Zaman Dilimi İterasyonu**
   - Her zaman dilimi için uygun mahalleler seçilir
   - Peak saatlerde yoğun bölgelerden kaçınılır

5. **Araç-Konteyner Eşleştirme**
   - ML skoru hesaplanır
   - En yüksek skorlu konteyner seçilir
   - Kapasite kontrolü yapılır
   - Gerekirse boşaltmaya gidilir

---

## 📤 Çıktılar

### CSV Çıktısı

`Database/rota_fullvehicle_YYYYMMDD.csv` dosyası oluşturulur:

| Sütun | Açıklama |
|-------|----------|
| vehicle_id | Araç ID |
| vehicle_name | Araç adı |
| vehicle_type | Araç tipi |
| vehicle_category | Kategori (CRANE/LARGE/SMALL) |
| vehicle_capacity | Kapasite (ton) |
| is_crane | Vinçli mi? |
| step | Adım numarası |
| container_idx | Konteyner index |
| lat, lon | Koordinatlar |
| mahalle | Mahalle adı |
| demand_ton | Talep (ton) |
| load_after | Toplama sonrası yük |
| hour, minute | Zaman |
| action | Eylem (COLLECT/UNLOAD) |

### Konsol Çıktısı

```
============================================================
🚛 TAM ARAÇ YÖNETİMLİ ROTA - 2025-06-25 Wednesday
============================================================

📊 TONAJ: 550.0 × 1.15 × 1.00 = 632.5 ton

📦 KONTEYNER ANALİZİ:
   Toplam: 1250
   Yeraltı: 45 (sadece CRANE alabilir)
   Dar sokak (<5m): 180 (sadece SMALL girebilir)
   Toplam talep: 625.3 ton

🚛 ROTA OLUŞTURULUYOR...
⏰ [06-07] Erken: 320 konteyner
⏰ [07-10] Sabah Peak: 280 konteyner
...

============================================================
📊 SONUÇ İSTATİSTİKLERİ
============================================================
🎯 Hedef tonaj: 632.5 ton
✅ Toplanan tonaj: 618.2 ton (97.7%)
📦 Toplanan konteyner: 1235 / 1250 (98.8%)
🚛 Aktif araç: 12
📏 Toplam mesafe: 245.6 km
🔄 Toplam boşaltma: 28
```

---

## 🔧 Konfigürasyon

Script içindeki sabitler düzenlenebilir:

```python
# Başlangıç ve boşaltma noktaları
START_MAH = "ALAADDINBEY"
UNLOAD_MAH = "YENIKENT"

# Boşaltma bekleme süresi (dakika)
UNLOAD_WAIT_MIN = 10

# Ortalama hız (km/saat)
AVG_SPEED_KMH = 25.0

# Konteyner servis süresi (saniye)
CONTAINER_SERVICE_SEC = 30

# Çalışma saatleri
DAY_START_HOUR = 6
DAY_END_HOUR = 23

# Peak saatleri
PEAK_MORNING = (7, 10)
PEAK_EVENING = (17, 20)

# Yüksek nüfus eşiği (bin)
POP_THRESHOLD = 15

# Araç minimum sokak genişlikleri (metre)
VEHICLE_MIN_STREET_WIDTH = {
    "LARGE": 4.0,
    "CRANE": 5.0,
    "SMALL": 2.5,
}
```

---

## 📝 Lisans

Bu proje Nilüfer Belediyesi Hackathon yarışması için geliştirilmiştir.

---

## 👥 Katkıda Bulunanlar

Hackathon AI Takımı

---

## 📞 İletişim

Sorularınız için issue açabilirsiniz.
