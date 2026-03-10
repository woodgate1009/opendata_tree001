"""
Google Earth Engine ユーティリティ
NDVIデータの取得と処理を行う
"""

import ee
import os
import time
import json
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from google.cloud import storage
import tempfile

# 環境変数の設定
EE_SERVICE_ACCOUNT = os.environ.get('EE_SERVICE_ACCOUNT')
EE_PRIVATE_KEY_FILE = os.environ.get('EE_PRIVATE_KEY_FILE')
GCS_BUCKET = os.environ.get('GCS_BUCKET')

def initialize_earth_engine():
    """Earth Engineを初期化"""
    try:
        if not ee.data._initialized:
            ee.Initialize(project="local-disk-456715-v8")
            print("Earth Engine initialized successfully")
    except Exception as e:
        print(f"Earth Engine initialization failed: {e}")
        raise

def create_monthly_ndvi_image(target_date):
    """
    指定された月のNDVI画像を作成
    
    Args:
        target_date (date): 対象の年月
    
    Returns:
        ee.Image: NDVI画像、またはNone（データなしの場合）
    """
    # 月の開始日と終了日を設定
    start_date = ee.Date(target_date.strftime('%Y-%m-01'))
    end_date = start_date.advance(1, 'month')
    
    # Sentinel-2データを取得
    s2_collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterDate(start_date, end_date) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    
    def calculate_ndvi(image):
        """NDVI計算関数"""
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        return image.addBands(ndvi)
    
    # NDVIを計算
    ndvi_collection = s2_collection.map(calculate_ndvi)
    
    # データが存在するかチェック
    collection_size = ndvi_collection.size().getInfo()
    if collection_size == 0:
        print(f"No satellite data available for {target_date.strftime('%Y-%m')}")
        return None
    
    # 月次中央値を計算
    monthly_ndvi = ndvi_collection.select('NDVI').median()
    
    return monthly_ndvi

def sample_ndvi_points_sync(points_list, target_date, max_points=None):
    """
    確実に動作するNDVI取得（Flaskバックエンド用）
    
    Args:
        points_list: ポイントのリスト [{'id': int, 'lon': float, 'lat': float}, ...]
        target_date: サンプリング対象の日付
        max_points: 最大処理ポイント数（None=制限なし）
    
    Returns:
        pandas.DataFrame: サンプリング結果
    """
    if max_points and len(points_list) > max_points:
        print(f"Warning: {len(points_list)} points exceed limit {max_points}. Processing first {max_points} points only.")
        points_list = points_list[:max_points]
    
    initialize_earth_engine()
    
    print(f"Processing {len(points_list)} points for {target_date.strftime('%Y-%m')}")
    
    results = []
    
    for i, point in enumerate(points_list):
        try:
            print(f"  Processing {i+1}/{len(points_list)}: {point.get('tree_id', point['id'])}")
            
            # ポイントとバッファ
            geometry = ee.Geometry.Point([point['lon'], point['lat']])
            buffered = geometry.buffer(12)
            
            # 期間設定（8月に変更 - データが豊富）
            year = target_date.year
            start_date = f'{year}-08-01'
            end_date = f'{year}-08-31'
            
            # Sentinel-2データ取得
            collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
                .filterBounds(buffered)\
                .filterDate(start_date, end_date)\
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 45))
            
            collection_size = collection.size().getInfo()
            
            if collection_size == 0:
                print(f"    ❌ No images available")
                ndvi_value = None
            else:
                # 月次平均＋スケーリング（確実に動作する方法）
                monthly_mean = collection.mean()
                scaled_optical = monthly_mean.select(['B4', 'B8']).multiply(0.0001)
                ndvi = scaled_optical.normalizedDifference(['B8', 'B4']).rename('NDVI')
                
                # reduceRegionで値取得
                result = ndvi.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=buffered,
                    scale=10
                ).getInfo()
                
                ndvi_value = result.get('NDVI')
                
                if ndvi_value is not None:
                    print(f"    ✅ NDVI: {ndvi_value:.6f} ({collection_size} images)")
                else:
                    print(f"    ❌ NDVI calculation failed")
            
            results.append({
                'point_id': str(point['id']),
                'tree_id': point.get('tree_id', ''),
                'ndvi': ndvi_value,
                'lon': point['lon'],
                'lat': point['lat']
            })
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
            results.append({
                'point_id': str(point['id']),
                'tree_id': point.get('tree_id', ''),
                'ndvi': None,
                'lon': point['lon'],
                'lat': point['lat']
            })
    
    # リストとして返却（ndvi_processor.pyでの互換性のため）
    return results

def sample_ndvi_points_async(points_list, target_date, task_prefix='ndvi_export'):
    """
    非同期でポイントのNDVIをサンプリング（大規模データセット用）
    Google Cloud Storageを使用
    
    Args:
        points_list: ポイントのリスト
        target_date: サンプリング対象の日付
        task_prefix: エクスポートタスクの接頭辞
    
    Returns:
        pandas.DataFrame: サンプリング結果
    """
    if not GCS_BUCKET:
        raise ValueError("GCS_BUCKET environment variable not set")
    
    initialize_earth_engine()
    
    # NDVI画像を作成
    ndvi_image = create_monthly_ndvi_image(target_date)
    if ndvi_image is None:
        return pd.DataFrame()
    
    # ポイントをGEEフィーチャーに変換
    features = []
    for point in points_list:
        geometry = ee.Geometry.Point([point['lon'], point['lat']])
        feature = ee.Feature(geometry, {
            'point_id': str(point['id']),
            'tree_id': point.get('tree_id', '')
        })
        features.append(feature)
    
    point_collection = ee.FeatureCollection(features)
    
    # NDVIをサンプリング
    sampled = ndvi_image.sampleRegions(
        collection=point_collection,
        scale=10,
        geometries=True
    )
    
    # GCSにエクスポート
    task = ee.batch.Export.table.toCloudStorage(
        collection=sampled,
        description=f'{task_prefix}_{target_date.strftime("%Y_%m")}',
        bucket=GCS_BUCKET,
        fileNamePrefix=f'ndvi_exports/{task_prefix}_{target_date.strftime("%Y_%m")}',
        fileFormat='CSV'
    )
    
    task.start()
    
    # タスクの完了を待機
    print(f"Starting GEE export task: {task.id}")
    while True:
        status = task.status()
        state = status.get('state')
        print(f"Task state: {state}")
        
        if state == 'COMPLETED':
            break
        elif state in ('FAILED', 'CANCELLED'):
            raise RuntimeError(f'GEE export task failed: {status}')
        
        time.sleep(10)
    
    # GCSからファイルをダウンロード
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    
    # エクスポートされたファイルを検索
    blobs = list(client.list_blobs(bucket, prefix=f'ndvi_exports/{task_prefix}_{target_date.strftime("%Y_%m")}'))
    
    if not blobs:
        print("No files found in GCS")
        return pd.DataFrame()
    
    # 一時ディレクトリにファイルをダウンロード
    temp_dir = tempfile.mkdtemp()
    csv_files = []
    
    for blob in blobs:
        if blob.name.endswith('.csv'):
            local_path = os.path.join(temp_dir, os.path.basename(blob.name))
            blob.download_to_filename(local_path)
            csv_files.append(local_path)
    
    # CSVファイルを結合
    if csv_files:
        dfs = []
        for csv_file in csv_files:
            df = pd.read_csv(csv_file)
            dfs.append(df)
        
        # 一時ファイルを削除
        for csv_file in csv_files:
            os.remove(csv_file)
        os.rmdir(temp_dir)
        
        if dfs:
            return pd.concat(dfs, ignore_index=True)
    
    return pd.DataFrame()

def test_gee_connection():
    """GEE接続をテスト"""
    try:
        initialize_earth_engine()
        
        # 簡単なテスト
        image = ee.Image("COPERNICUS/S2_SR_HARMONIZED/20230101T000000_20230101T000000_T01ABC")
        info = image.getInfo()
        print("GEE connection test successful")
        return True
    except Exception as e:
        print(f"GEE connection test failed: {e}")
        return False

def get_specific_date_ndvi(target_date, lat, lon):
    """
    特定日付のNDVI値を取得（論文検証用）
    
    Args:
        target_date (date): 対象日付
        lat (float): 緯度
        lon (float): 経度
    
    Returns:
        float: NDVI値、またはNone（データなしの場合）
    """
    try:
        initialize_earth_engine()
        
        # ポイント設定
        geometry = ee.Geometry.Point([lon, lat])
        buffered = geometry.buffer(12)  # 12mバッファ
        
        # 論文と同じ期間設定（9月）
        start_date = f'{target_date.year}-09-01'
        end_date = f'{target_date.year}-09-30'
        
        print(f"Processing NDVI for {target_date} at ({lat}, {lon})")
        print(f"Date range: {start_date} to {end_date}")
        
        # SENTINEL-2データ取得
        collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
            .filterBounds(buffered)\
            .filterDate(start_date, end_date)\
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 45))
        
        collection_size = collection.size().getInfo()
        print(f"Found {collection_size} images")
        
        if collection_size == 0:
            print("No images available")
            return None
        
        # NDVI計算
        monthly_mean = collection.mean()
        scaled_optical = monthly_mean.select(['B4', 'B8']).multiply(0.0001)
        ndvi = scaled_optical.normalizedDifference(['B8', 'B4']).rename('NDVI')
        
        # 値取得
        result = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=buffered,
            scale=10
        ).getInfo()
        
        ndvi_value = result.get('NDVI')
        print(f"NDVI value: {ndvi_value}")
        
        return ndvi_value
        
    except Exception as e:
        print(f"Error getting NDVI for {target_date}: {e}")
        return None

def validate_against_paper_with_comparison():
    """
    論文との比較検証（前年同期比差分も含む）
    """
    from datetime import date
    
    # 自然教育園内の複数ポイント（正確な座標）
    NATURAL_EDUCATION_GARDEN_POINTS = [
        {
            'lat': 35.638718,
            'lon': 139.718717,
            'name': '自然教育園（地点1）',
            'id': 'point1'
        },
        {
            'lat': 35.638039,
            'lon': 139.718368,
            'name': '自然教育園（地点2）',
            'id': 'point2'
        },
        {
            'lat': 35.638659,
            'lon': 139.720293,
            'name': '自然教育園（地点3）',
            'id': 'point3'
        },
        {
            'lat': 35.639066,
            'lon': 139.721452,
            'name': '自然教育園（地点4）',
            'id': 'point4'
        },
        {
            'lat': 35.638289,
            'lon': 139.719035,
            'name': '自然教育園（地点5）',
            'id': 'point5'
        }
    ]
    
    # 論文の調査日（2019年を基準に前年同期比を計算）
    paper_dates = [
          # 基準年
        date(2019, 9, 10),  # 論文の主要調査日
        date(2020, 9, 9),
        date(2021, 9, 5)    # 比較年
    ]
    
    print("=== 論文検証開始（前年同期比差分含む） ===")
    print(f"対象地点数: {len(NATURAL_EDUCATION_GARDEN_POINTS)}")
    print()
    
    all_results = []
    
    for point in NATURAL_EDUCATION_GARDEN_POINTS:
        print(f"--- {point['name']} の処理 ---")
        print(f"座標: ({point['lat']}, {point['lon']})")
        
        point_results = []
        
        for target_date in paper_dates:
            print(f"  {target_date} の処理中...")
            
            # 現在年のNDVI取得
            current_ndvi = get_specific_date_ndvi(
                target_date, 
                point['lat'], 
                point['lon']
            )
            
            # 前年同期のNDVI取得
            prev_year_date = target_date.replace(year=target_date.year - 1)
            prev_year_ndvi = get_specific_date_ndvi(
                prev_year_date,
                point['lat'],
                point['lon']
            )
            
            # 差分計算（前年同期比）
            ndvi_diff = None
            if current_ndvi is not None and prev_year_ndvi is not None:
                ndvi_diff = current_ndvi - prev_year_ndvi
            
            # 論文の基準との比較（現在年NDVI）
            if current_ndvi is not None:
                if 0.7 <= current_ndvi <= 0.8:
                    status = "健全（論文基準と一致）"
                    color = "[OK]"
                elif current_ndvi > 0.8:
                    status = "高値（論文基準より高い）"
                    color = "[HIGH]"
                elif current_ndvi < 0.7:
                    status = "低値（論文基準より低い）"
                    color = "[LOW]"
                else:
                    status = "要確認"
                    color = "[?]"
            else:
                status = "データなし"
                color = "[NO DATA]"
            
            result = {
                'point_id': point['id'],
                'point_name': point['name'],
                'lat': point['lat'],
                'lon': point['lon'],
                'date': target_date.isoformat(),
                'current_ndvi': current_ndvi,
                'prev_year_ndvi': prev_year_ndvi,
                'ndvi_diff': ndvi_diff,
                'paper_range': '0.7-0.8 (健全)',
                'status': status,
                'color': color
            }
            
            point_results.append(result)
            all_results.append(result)
            
            print(f"    {color} 現在年NDVI: {current_ndvi}")
            print(f"    前年同期NDVI: {prev_year_ndvi}")
            print(f"    差分: {ndvi_diff}")
            print(f"    論文基準: 0.7-0.8 (健全)")
            print(f"    判定: {status}")
        
        print()
    
    print("=== 全体検証結果サマリー ===")
    for result in all_results:
        print(f"{result['color']} {result['point_name']} {result['date']}: NDVI={result['current_ndvi']}, 差分={result['ndvi_diff']} - {result['status']}")
    
    return all_results