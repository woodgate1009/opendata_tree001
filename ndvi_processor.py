"""
NDVI処理とデータベース操作
Colabで行っていた処理をFlaskバックエンドに移植
"""

import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from models import get_database_session, TreePoint, NDVISample
from gee_utils import sample_ndvi_points_sync, sample_ndvi_points_async
import numpy as np

class NDVIProcessor:
    """NDVI処理クラス"""
    
    def __init__(self, database_url=None):
        self.session = get_database_session(database_url)
    
    def close(self):
        """セッションを閉じる"""
        if self.session:
            self.session.close()
    
    def add_tree_point(self, lon, lat, tree_id=None, species=None, source='manual', description=None):
        """
        新しい樹木ポイントを追加
        
        Args:
            lon: 経度
            lat: 緯度
            tree_id: ツリーID（オプション）
            species: 樹種（オプション）
            source: データソース
            description: 説明
        
        Returns:
            TreePoint: 追加されたポイント
        """
        point = TreePoint(
            tree_id=tree_id,
            species=species,
            lon=float(lon),
            lat=float(lat),
            source=source,
            description=description
        )
        
        self.session.add(point)
        self.session.commit()
        
        print(f"Tree point added: ID={point.id}, coords=({lon}, {lat})")
        return point
    
    def import_points_from_csv(self, csv_file_path, lon_col='経度', lat_col='緯度', 
                              species_col='樹種', id_col=None, encoding='utf-8-sig'):
        """
        CSVファイルから樹木ポイントをインポート
        
        Args:
            csv_file_path: CSVファイルパス
            lon_col: 経度列名
            lat_col: 緯度列名
            species_col: 樹種列名
            id_col: ID列名（オプション）
            encoding: ファイルエンコーディング
        
        Returns:
            int: インポートされたポイント数
        """
        try:
            # CSVを読み込み
            df = pd.read_csv(csv_file_path, encoding=encoding)
            print(f"CSV loaded: {len(df)} rows")
            
            # 必要な列が存在するかチェック
            required_cols = [lon_col, lat_col]
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Missing columns: {missing_cols}")
            
            # データを追加
            imported_count = 0
            for _, row in df.iterrows():
                try:
                    lon = float(row[lon_col])
                    lat = float(row[lat_col])
                    
                    # 有効な座標かチェック
                    if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
                        continue
                    
                    tree_id = row.get(id_col) if id_col and id_col in df.columns else None
                    species = row.get(species_col) if species_col in df.columns else None
                    
                    # 既存のポイントがないかチェック（同じ座標の場合）
                    existing = self.session.query(TreePoint).filter(
                        TreePoint.lon == lon,
                        TreePoint.lat == lat
                    ).first()
                    
                    if not existing:
                        point = TreePoint(
                            tree_id=str(tree_id) if tree_id is not None else None,
                            species=str(species) if species is not None else None,
                            lon=lon,
                            lat=lat,
                            source='csv_import'
                        )
                        self.session.add(point)
                        imported_count += 1
                
                except (ValueError, TypeError) as e:
                    print(f"Skipped invalid row: {e}")
                    continue
            
            self.session.commit()
            print(f"Imported {imported_count} tree points from CSV")
            return imported_count
        
        except Exception as e:
            self.session.rollback()
            print(f"Error importing CSV: {e}")
            raise
    
    def get_all_tree_points(self):
        """全ての樹木ポイントを取得"""
        return self.session.query(TreePoint).all()
    
    def sample_ndvi_for_month(self, target_date, use_async=False, max_sync_points=500):
        """
        指定月のNDVIをサンプリングして保存
        
        Args:
            target_date: 対象の年月（date型）
            use_async: 非同期処理を使用するか
            max_sync_points: 同期処理の最大ポイント数
        
        Returns:
            int: 処理されたポイント数
        """
        # 月初日に正規化
        target_date = target_date.replace(day=1)
        
        # 全ての樹木ポイントを取得
        tree_points = self.get_all_tree_points()
        if not tree_points:
            print("No tree points found")
            return 0
        
        # ポイントリストを作成
        points_list = []
        for point in tree_points:
            points_list.append({
                'id': point.id,
                'lon': point.lon,
                'lat': point.lat,
                'tree_id': point.tree_id
            })
        
        print(f"Sampling NDVI for {len(points_list)} points for {target_date.strftime('%Y-%m')}")
        
        # GEEでNDVIをサンプリング
        if use_async or len(points_list) > max_sync_points:
            df_sampled = sample_ndvi_points_async(points_list, target_date)
        else:
            df_sampled = sample_ndvi_points_sync(points_list, target_date)
        
        if df_sampled.empty:
            print("No NDVI data obtained")
            return 0
        
        # データベースに保存
        return self._store_ndvi_samples(df_sampled, target_date)
    
    def _store_ndvi_samples(self, df_sampled, period_month):
        """
        サンプリングされたNDVIデータをデータベースに保存し、差分を計算
        
        Args:
            df_sampled: サンプリング結果のDataFrame
            period_month: 対象月
        
        Returns:
            int: 保存されたサンプル数
        """
        saved_count = 0
        
        # DataFrameの列名を正規化
        id_column = None
        ndvi_column = None
        
        for col in df_sampled.columns:
            if col.lower() in ['point_id', 'id', 'tree_id']:
                id_column = col
            elif col.lower().startswith('ndvi'):
                ndvi_column = col
        
        if id_column is None or ndvi_column is None:
            print(f"Required columns not found. Available: {df_sampled.columns.tolist()}")
            return 0
        
        # 各ポイントについて処理
        for _, row in df_sampled.iterrows():
            try:
                # point_idの変換を修正（文字列IDに対応）
                point_id_str = str(row[id_column])
                ndvi_value = row[ndvi_column]
                
                # 数値IDに変換を試行、失敗したら文字列IDでlookup
                try:
                    point_id = int(point_id_str)
                except ValueError:
                    # 文字列IDの場合、tree_idで検索
                    tree_point = self.session.query(TreePoint).filter(TreePoint.tree_id == point_id_str).first()
                    if tree_point:
                        point_id = tree_point.id
                    else:
                        print(f"Point not found for tree_id: {point_id_str}")
                        continue
                
                # NaN値をNoneに変換
                if pd.isna(ndvi_value):
                    ndvi_value = None
                else:
                    ndvi_value = float(ndvi_value)
                
                # 対応する樹木ポイントを検索
                tree_point = self.session.query(TreePoint).filter(TreePoint.id == point_id).first()
                if not tree_point:
                    continue
                
                # 前年同月のデータを検索
                prev_year_date = period_month.replace(year=period_month.year - 1)
                prev_sample = self.session.query(NDVISample).filter(
                    NDVISample.tree_point_id == point_id,
                    NDVISample.period_month == prev_year_date
                ).first()
                
                prev_ndvi = prev_sample.ndvi if prev_sample else None
                
                # 差分を計算
                ndvi_diff = None
                if ndvi_value is not None and prev_ndvi is not None:
                    ndvi_diff = ndvi_value - prev_ndvi
                
                # 既存のサンプルを検索（upsert）
                existing_sample = self.session.query(NDVISample).filter(
                    NDVISample.tree_point_id == point_id,
                    NDVISample.period_month == period_month
                ).first()
                
                if existing_sample:
                    # 更新
                    existing_sample.ndvi = ndvi_value
                    existing_sample.ndvi_prev_year = prev_ndvi
                    existing_sample.ndvi_diff = ndvi_diff
                else:
                    # 新規作成
                    new_sample = NDVISample(
                        tree_point_id=point_id,
                        period_month=period_month,
                        ndvi=ndvi_value,
                        ndvi_prev_year=prev_ndvi,
                        ndvi_diff=ndvi_diff
                    )
                    self.session.add(new_sample)
                
                saved_count += 1
            
            except (ValueError, TypeError) as e:
                print(f"Error processing sample: {e}")
                continue
        
        self.session.commit()
        print(f"Saved {saved_count} NDVI samples with difference calculation")
        return saved_count
    
    def get_alerts(self, threshold=-0.1, months_back=3):
        """
        異常検知アラートを取得
        
        Args:
            threshold: 差分の閾値（これより小さい場合にアラート）
            months_back: 過去何ヶ月のデータを見るか
        
        Returns:
            list: アラート対象のポイント情報
        """
        # 対象期間を計算
        end_date = date.today().replace(day=1)
        start_date = end_date - relativedelta(months=months_back)
        
        # 差分が閾値を下回るサンプルを検索
        alerts = self.session.query(NDVISample, TreePoint) \
            .join(TreePoint, NDVISample.tree_point_id == TreePoint.id) \
            .filter(NDVISample.ndvi_diff < threshold) \
            .filter(NDVISample.period_month >= start_date) \
            .filter(NDVISample.period_month <= end_date) \
            .order_by(NDVISample.ndvi_diff.asc()) \
            .all()
        
        alert_list = []
        for sample, point in alerts:
            alert_list.append({
                'point_id': point.id,
                'tree_id': point.tree_id,
                'species': point.species,
                'lon': point.lon,
                'lat': point.lat,
                'period_month': sample.period_month.isoformat(),
                'ndvi': sample.ndvi,
                'ndvi_prev_year': sample.ndvi_prev_year,
                'ndvi_diff': sample.ndvi_diff,
                'severity': 'high' if sample.ndvi_diff < threshold * 2 else 'medium'
            })
        
        return alert_list
    
    def get_point_timeseries(self, point_id, months_back=24):
        """
        特定ポイントの時系列データを取得
        
        Args:
            point_id: ポイントID
            months_back: 過去何ヶ月のデータを取得するか
        
        Returns:
            list: 時系列データ
        """
        # 対象期間を計算
        end_date = date.today().replace(day=1)
        start_date = end_date - relativedelta(months=months_back)
        
        samples = self.session.query(NDVISample) \
            .filter(NDVISample.tree_point_id == point_id) \
            .filter(NDVISample.period_month >= start_date) \
            .filter(NDVISample.period_month <= end_date) \
            .order_by(NDVISample.period_month.asc()) \
            .all()
        
        timeseries = []
        for sample in samples:
            timeseries.append({
                'date': sample.period_month.isoformat(),
                'ndvi': sample.ndvi,
                'ndvi_prev_year': sample.ndvi_prev_year,
                'ndvi_diff': sample.ndvi_diff
            })
        
        return timeseries
    
    def run_monthly_processing(self, target_date=None, use_async=None):
        """
        月次処理を実行
        
        Args:
            target_date: 処理対象月（デフォルトは前月）
            use_async: 非同期処理を使用するか（自動判定）
        
        Returns:
            dict: 処理結果
        """
        if target_date is None:
            # 前月を対象とする
            today = date.today()
            target_date = (today.replace(day=1) - relativedelta(months=1))
        
        print(f"Starting monthly NDVI processing for {target_date.strftime('%Y-%m')}")
        
        try:
            # ポイント数を確認して処理方法を決定
            point_count = self.session.query(TreePoint).count()
            
            if use_async is None:
                use_async = point_count > 500
            
            # NDVIサンプリングを実行
            processed_count = self.sample_ndvi_for_month(target_date, use_async=use_async)
            
            # アラートを生成
            alerts = self.get_alerts()
            
            result = {
                'status': 'success',
                'target_date': target_date.isoformat(),
                'processed_points': processed_count,
                'total_points': point_count,
                'alerts_count': len(alerts),
                'processing_method': 'async' if use_async else 'sync'
            }
            
            print(f"Monthly processing completed: {result}")
            return result
        
        except Exception as e:
            print(f"Monthly processing failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'target_date': target_date.isoformat() if target_date else None
            }
    
    def run_latest_processing(self, target_date):
        """
        最新データ処理を実行（現在の最新データ＋1年前との比較）
        
        Args:
            target_date (date): 現在日付
            
        Returns:
            dict: 処理結果
        """
        try:
            # 現在月のNDVIデータを取得
            current_month = target_date.replace(day=1)
            print(f"Processing latest NDVI for {current_month.strftime('%Y-%m')}")
            
            # 現在月のデータ取得
            current_samples = sample_ndvi_points_sync(
                self._get_all_points(), 
                target_date
            )
            
            # 前年同月のデータ取得
            prev_year_date = target_date.replace(year=target_date.year - 1)
            print(f"Processing previous year NDVI for {prev_year_date.strftime('%Y-%m')}")
            
            prev_year_samples = sample_ndvi_points_sync(
                self._get_all_points(),
                prev_year_date
            )
            
            # 両方のデータを結合して差分計算
            saved_count = self._store_comparative_samples(
                current_samples, prev_year_samples, current_month
            )
            
            # アラートチェック
            alerts = self.get_alerts()
            
            return {
                'status': 'success',
                'target_date': target_date.isoformat(),
                'processed_points': saved_count,
                'total_points': len(self._get_all_points()),
                'alerts_count': len(alerts),
                'processing_method': 'latest_comparative'
            }
            
        except Exception as e:
            print(f"Error in latest processing: {e}")
            return {
                'status': 'error',
                'error_message': str(e)
            }
    
    def _store_comparative_samples(self, current_samples, previous_samples, period_month):
        """
        現在と前年のNDVIデータを比較して保存
        
        Args:
            current_samples (list): 現在年のNDVIサンプル
            previous_samples (list): 前年のNDVIサンプル
            period_month (date): 期間月
            
        Returns:
            int: 保存されたサンプル数
        """
        # 安全な空データチェック
        has_current = current_samples is not None and len(current_samples) > 0
        has_previous = previous_samples is not None and len(previous_samples) > 0
        
        if not has_current and not has_previous:
            return 0
        
        # リスト処理に変更（DataFrameを使わない）
        saved_count = 0
        
        # 現在・前年データを辞書に変換
        current_dict = {}
        if has_current:
            for sample in current_samples:
                tree_id = sample.get('tree_id')
                if tree_id:
                    current_dict[tree_id] = sample.get('ndvi')
        
        previous_dict = {}
        if has_previous:
            for sample in previous_samples:
                tree_id = sample.get('tree_id')
                if tree_id:
                    previous_dict[tree_id] = sample.get('ndvi')
        
        # 全ポイントIDを取得
        all_point_ids = set()
        all_point_ids.update(current_dict.keys())
        all_point_ids.update(previous_dict.keys())
        
        for point_id in all_point_ids:
            try:
                # 現在・前年データ取得
                current_ndvi = current_dict.get(point_id)
                previous_ndvi = previous_dict.get(point_id)
                
                # 数値型に変換
                if current_ndvi is not None:
                    try:
                        current_ndvi = float(current_ndvi)
                    except (ValueError, TypeError):
                        current_ndvi = None
                
                if previous_ndvi is not None:
                    try:
                        previous_ndvi = float(previous_ndvi)
                    except (ValueError, TypeError):
                        previous_ndvi = None
                
                # ポイントID変換
                try:
                    db_point_id = int(point_id)
                except ValueError:
                    tree_point = self.session.query(TreePoint).filter(TreePoint.tree_id == str(point_id)).first()
                    if tree_point:
                        db_point_id = tree_point.id
                    else:
                        print(f"Point not found for tree_id: {point_id}")
                        continue
                
                # 差分計算
                ndvi_diff = None
                if current_ndvi is not None and previous_ndvi is not None:
                    ndvi_diff = current_ndvi - previous_ndvi
                
                # データベースに保存または更新
                existing_sample = self.session.query(NDVISample).filter(
                    NDVISample.tree_point_id == db_point_id,
                    NDVISample.period_month == period_month
                ).first()
                
                if existing_sample:
                    # 既存データを更新
                    existing_sample.ndvi = current_ndvi
                    existing_sample.ndvi_prev_year = previous_ndvi
                    existing_sample.ndvi_diff = ndvi_diff
                else:
                    # 新規データ作成
                    sample = NDVISample(
                        tree_point_id=db_point_id,
                        period_month=period_month,
                        ndvi=current_ndvi,
                        ndvi_prev_year=previous_ndvi,
                        ndvi_diff=ndvi_diff
                    )
                    self.session.add(sample)
                
                saved_count += 1
                
            except Exception as e:
                print(f"Error processing comparative sample for {point_id}: {e}")
                continue
        
        try:
            self.session.commit()
            print(f"Saved {saved_count} comparative NDVI samples")
        except Exception as e:
            self.session.rollback()
            print(f"Error saving comparative samples: {e}")
            saved_count = 0
        
        return saved_count

    def _get_all_points(self):
        """本物マツ・ナラデータのみを取得（異常データ除外）"""
        points = self.session.query(TreePoint).all()
        
        # 本物データのみフィルタリング + 地理的異常値除外
        valid_points = []
        for p in points:
            tree_id = p.tree_id or ''
            species = p.species or ''
            
            # 本物データかどうかチェック
            is_real_matsu = 'マツ' in species and ('PT' in tree_id or 'MATSU_ROAD' in tree_id)
            is_real_nara = ('ナラ' in species or 'カシ' in species) and ('PT' in tree_id or 'NARA_ROAD' in tree_id)
            
            if not (is_real_matsu or is_real_nara):
                continue  # 本物データ以外は除外
            
            # 地理的範囲チェック（東京都周辺のみ）
            lat, lon = p.lat, p.lon
            if not (35.0 <= lat <= 36.0 and 138.5 <= lon <= 140.5):
                print(f"地理的異常値除外: {tree_id} ({lat}, {lon})")
                continue
            
            # 海上チェック（簡易的な陸地判定）
            # 東京湾内座標の除外
            if (lat < 35.4 and 139.7 <= lon <= 140.1):  # 東京湾エリア
                print(f"海上データ除外: {tree_id} ({lat}, {lon})")
                continue
            
            valid_points.append({
                'id': p.id, 
                'tree_id': tree_id, 
                'lon': lon, 
                'lat': lat, 
                'species': species
            })
        
        # マツ・ナラ優先でソート
        def priority_key(point):
            species = point['species']
            if 'マツ' in species:
                return 0  # マツ最優先
            else:
                return 1  # ナラ次優先
        
        valid_points.sort(key=priority_key)
        print(f"有効な本物データ: {len(valid_points)}件（マツ・ナラのみ、異常値除外済み）")
        return valid_points
