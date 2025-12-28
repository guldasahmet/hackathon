"""
Neighborhood API Endpoints
Mahalle ve konteyner yönetimi API'leri
"""
from flask import jsonify
import pandas as pd
from . import neighborhoods_bp


@neighborhoods_bp.route('/mahalleler')
def api_mahalleler():
    """Mahalle listesi - GERÇEK VERİ (65 mahalle)"""
    
    try:
        # 1. Konteyner sayıları
        df_containers = pd.read_csv('full_dataset/container_counts.csv', sep=';', encoding='utf-8')
        
        # 2. Toplama programları
        df_schedule = pd.read_csv('full_dataset/neighbor_days_rotations.csv', sep=';', encoding='utf-8')
        
        # Mahalle isimlerini normalize et
        df_containers['mahalle_clean'] = df_containers['MAHALLE'].str.strip().str.upper()
        df_schedule['mahalle_clean'] = df_schedule['MAHALLE ADI'].str.replace(' MAHALLESİ', '', regex=False).str.strip().str.upper()
        
        # Merge
        df_merged = pd.merge(
            df_containers,
            df_schedule,
            on='mahalle_clean',
            how='left'
        )
        
        def safe_int(val):
            if pd.isna(val) or val == '':
                return 0
            if isinstance(val, str):
                val = val.replace('.', '').replace(',', '')
            try:
                return int(float(val))
            except:
                return 0
        
        mahalleler = []
        for _, row in df_merged.iterrows():
            mahalle = {
                'mahalle': row['MAHALLE'],
                'toplam_konteyner': safe_int(row['TOPLAM']),
                'yeralti': safe_int(row['YERALTI KONTEYNER']),
                'lt_770': safe_int(row['770 LT KONTEYNER']),
                'lt_400': safe_int(row['400 LT KONTEYNER']),
                'plastik': safe_int(row['PLASTİK']),
                'gunluk_toplama': safe_int(row['Days Collected Per Week']) if pd.notna(row.get('Days Collected Per Week')) else 3,
                'vinc_gerekli': bool(row.get('Is Crane Used')) if pd.notna(row.get('Is Crane Used')) and row.get('Is Crane Used') != 'FALSE' else False
            }
            mahalleler.append(mahalle)
        
        # Toplam konteyner
        total_containers = sum(m['toplam_konteyner'] for m in mahalleler)
        
        return jsonify({
            'mahalleler': mahalleler,
            'toplam': len(mahalleler),
            'toplam_konteyner': total_containers
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@neighborhoods_bp.route('/mahalleler/liste')
def api_mahalleler_liste():
    """Dropdown için mahalle listesi"""
    
    # Mahalle koordinatları (CSV'deki tam isimlerle)
    mahalle_koordinatlari = {
        '100. YIL ': {'lat': 40.2234, 'lon': 28.8678},
        '19 MAYIS': {'lat': 40.2156, 'lon': 28.8423},
        '23 NİSAN': {'lat': 40.2189, 'lon': 28.8567},
        '29 EKİM': {'lat': 40.2112, 'lon': 28.8789},
        '30 AĞUSTOS ZAFER ': {'lat': 40.2043, 'lon': 28.8601},
        'AHMET YESEVİ': {'lat': 40.2267, 'lon': 28.8512},
        'AKÇALAR': {'lat': 40.1998, 'lon': 28.8842},
        'ALAADDİNBEY': {'lat': 40.2189, 'lon': 28.8518},
        'ALTINŞEHİR': {'lat': 40.1998, 'lon': 28.8842},
        'ATAEVLER': {'lat': 40.2043, 'lon': 28.8601},
        'ATLAS': {'lat': 40.2156, 'lon': 28.8950},
        'AYVA': {'lat': 40.2089, 'lon': 28.8823},
        'BADIRGA': {'lat': 40.2445, 'lon': 28.8934},
        'BALAT': {'lat': 40.2609, 'lon': 28.9377},
        'BALKAN': {'lat': 40.2398, 'lon': 28.8645},
        'BARIŞ': {'lat': 40.1889, 'lon': 28.8567},
        'BAŞKÖY': {'lat': 40.1767, 'lon': 28.8678},
        'BEŞEVLER': {'lat': 40.2156, 'lon': 28.9156},
        'BÜYÜKBALIKLI': {'lat': 40.2523, 'lon': 28.9234},
        'CUMHURİYET': {'lat': 40.2234, 'lon': 28.9089},
        'ÇALI': {'lat': 40.1834, 'lon': 28.8423},
        'ÇAMLICA': {'lat': 40.2345, 'lon': 28.8456},
        'ÇATALAĞIL': {'lat': 40.2378, 'lon': 28.8234},
        'ÇAYLI': {'lat': 40.1723, 'lon': 28.9234},
        'DAĞYENİCE': {'lat': 40.2089, 'lon': 28.8967},
        'DEMİRCİ': {'lat': 40.1998, 'lon': 28.9156},
        'DOĞANKÖY': {'lat': 40.2267, 'lon': 28.9377},
        'DUMLUPINAR': {'lat': 40.2089, 'lon': 28.8967},
        'ERTUĞRUL': {'lat': 40.2234, 'lon': 28.9089},
        'ESENTEPE': {'lat': 40.2156, 'lon': 28.8789},
        'FADILLI': {'lat': 40.1889, 'lon': 28.9234},
        'FETHİYE': {'lat': 40.1889, 'lon': 28.8567},
        'GELEMİT': {'lat': 40.2445, 'lon': 28.9567},
        'GÖKÇE': {'lat': 40.2523, 'lon': 28.9089},
        'GÖLYAZI': {'lat': 40.2609, 'lon': 28.8456},
        'GÖRÜKLE': {'lat': 40.2267, 'lon': 28.8512},
        'GÜMÜŞTEPE': {'lat': 40.2378, 'lon': 28.8823},
        'GÜNGÖREN': {'lat': 40.2189, 'lon': 28.9234},
        'HASANAĞA': {'lat': 40.2043, 'lon': 28.9377},
        'IŞIKTEPE': {'lat': 40.2156, 'lon': 28.8601},
        'İHSANİYE': {'lat': 40.2445, 'lon': 28.8934},
        'İNEGAZİ': {'lat': 40.1998, 'lon': 28.8678},
        'İRFANİYE': {'lat': 40.2089, 'lon': 28.8512},
        'KADRİYE': {'lat': 40.2234, 'lon': 28.8456},
        'KARACAOBA': {'lat': 40.1767, 'lon': 28.9089},
        'KARAMAN': {'lat': 40.2398, 'lon': 28.9156},
        'KAYAPA': {'lat': 40.1834, 'lon': 28.8423},
        'KIZILCIKLI': {'lat': 40.2267, 'lon': 28.8645},
        'KORUBAŞI': {'lat': 40.2156, 'lon': 28.8967},
        'KONAK': {'lat': 40.2112, 'lon': 28.8789},
        'KONAKLI': {'lat': 40.1889, 'lon': 28.9234},
        'KURUÇEŞME': {'lat': 40.2345, 'lon': 28.9377},
        'KURTULUŞ': {'lat': 40.2523, 'lon': 28.8789},
        'KÜLTÜR': {'lat': 40.2234, 'lon': 28.8678},
        'MAKSEMPINAR': {'lat': 40.2609, 'lon': 28.8823},
        'MİNARELİÇAVUŞ': {'lat': 40.2378, 'lon': 28.9089},
        'ODUNLUK': {'lat': 40.2345, 'lon': 28.8456},
        'ÖZLÜCE': {'lat': 40.2523, 'lon': 28.8645},
        'TAHTALI': {'lat': 40.2189, 'lon': 28.8967},
        'UNÇUKURU': {'lat': 40.2043, 'lon': 28.9156},
        'ÜÇEVLER': {'lat': 40.2267, 'lon': 28.8601},
        'ÜÇPINAR': {'lat': 40.2156, 'lon': 28.8512},
        'ÜRÜNLÜ': {'lat': 40.2398, 'lon': 28.8456},
        'YAYLACIK': {'lat': 40.1889, 'lon': 28.8823},
        'YOLÇATI': {'lat': 40.2112, 'lon': 28.9234}
    }
    
    try:
        df = pd.read_csv('full_dataset/container_counts.csv', sep=';', encoding='utf-8')
        
        mahalleler = []
        for _, row in df.iterrows():
            mahalle_ad = str(row['MAHALLE']).strip()
            coords = mahalle_koordinatlari.get(mahalle_ad, {'lat': 40.22, 'lon': 28.94})
            mahalleler.append({
                'id': mahalle_ad.lower().replace(' ', '_').replace('ı', 'i').replace('ö', 'o').replace('ü', 'u').replace('ş', 's').replace('ç', 'c').replace('ğ', 'g').replace('.', ''),
                'ad': mahalle_ad,
                'lat': coords['lat'],
                'lon': coords['lon']
            })
        
        mahalleler.sort(key=lambda x: x['ad'])
        
        return jsonify({
            'mahalleler': mahalleler,
            'toplam': len(mahalleler)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@neighborhoods_bp.route('/nilufer/sinir')
def api_nilufer_sinir():
    """Nilüfer ilçe sınırı polygon verisi"""
    
    try:
        import json
        
        with open('full_dataset/nilufer_sinir.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify(data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
