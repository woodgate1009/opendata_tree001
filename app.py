from flask import Flask, render_template, jsonify, request, make_response, send_from_directory
import json
import os
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import random
import uuid
import sqlite3
import base64
from apscheduler.schedulers.background import BackgroundScheduler
import tensorflow as tf
from PIL import Image, ImageOps
import numpy as np

# NDVI関連のインポート（条件付き）
try:
    from ndvi_processor import NDVIProcessor
    from models import init_database, get_database_session, TreePoint, NDVISample
    NDVI_ENABLED = True
    print("NDVI機能が有効です")
except ImportError as e:
    print(f"NDVI機能は無効です（依存関係不足）: {e}")
    NDVI_ENABLED = False

app = Flask(__name__, static_folder='static', static_url_path='/static')

# TensorFlowのログレベル設定
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')

# より包括的な警告抑制
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='google.protobuf')
warnings.filterwarnings('ignore', category=UserWarning, module='tensorflow')
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='.*protobuf.*')
warnings.filterwarnings('ignore', message='.*tensorflow.*')

# TensorFlowの設定を最適化
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # より厳格なログレベル
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_ENABLE_MKL_NATIVE_FORMAT'] = '0'

# AI関連の初期化
ai_model = None
ai_class_names = []

def initialize_ai():
    global ai_model, ai_class_names
    try:
        # TensorFlowの設定を最適化
        tf.config.set_soft_device_placement(True)
        tf.config.experimental.set_memory_growth(tf.config.list_physical_devices('GPU')[0], True) if tf.config.list_physical_devices('GPU') else None
        
        if os.path.exists('keras_model.h5'):
            print("AIモデルを読み込み中...")
            ai_model = tf.keras.models.load_model('keras_model.h5', compile=False)
            print("AIモデルの読み込み完了")
            
            if os.path.exists('labels.txt'):
                with open('labels.txt', 'r', encoding='utf-8') as f:
                    ai_class_names = [line.strip() for line in f.readlines()]
                print(f"ラベル読み込み完了: {ai_class_names}")
            else:
                print("labels.txt が見つかりません")
        else:
            print("keras_model.h5 が見つかりません")
    except Exception as e:
        print(f"AI初期化エラー: {e}")

def predict_tree_health(image_data):
    """樹木画像から健康状態を予測"""
    global ai_model, ai_class_names
    
    if ai_model is None:
        return None, 0.0
        
    try:
        # 画像を224x224にリサイズし、正規化
        image = Image.open(image_data).convert('RGB')
        size = (224, 224)
        image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
        image_array = np.asarray(image)
        normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
        
        # 配列の形を整える
        data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
        data[0] = normalized_image_array

        # 予測
        prediction = ai_model.predict(data)
        index = np.argmax(prediction)
        
        if index < len(ai_class_names):
            class_name = ai_class_names[index]
            confidence_score = float(prediction[0][index])
            return class_name, confidence_score
        else:
            return None, 0.0
            
    except Exception as e:
        print(f"AI予測エラー: {e}")
        return None, 0.0

# 既存のデータベースの初期化
def init_db():
    conn = sqlite3.connect('tree_reports.db')
    cursor = conn.cursor()
    
    # 市民レポートテーブル
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS citizen_reports (
        id TEXT PRIMARY KEY,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        report_type TEXT NOT NULL,
        severity INTEGER NOT NULL,
        description TEXT,
        image_data BLOB,
        image_filename TEXT,
        status TEXT DEFAULT 'submitted',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        analysis_result TEXT,
        tree_species TEXT,
        health_score REAL,
        health_status TEXT,
        analysis_date DATETIME
    )
    ''')
    
    # 既存テーブルにAI予測カラムを追加（存在しない場合のみ）
    try:
        cursor.execute('ALTER TABLE citizen_reports ADD COLUMN ai_prediction TEXT')
        print("ai_predictionカラムを追加しました")
    except sqlite3.OperationalError:
        print("ai_predictionカラムは既に存在します")
    
    try:
        cursor.execute('ALTER TABLE citizen_reports ADD COLUMN ai_confidence REAL')
        print("ai_confidenceカラムを追加しました")
    except sqlite3.OperationalError:
        print("ai_confidenceカラムは既に存在します")
    
    conn.commit()
    conn.close()

# 既存DB初期化
init_db()

# NDVI関連の初期化（利用可能な場合のみ）
if NDVI_ENABLED:
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///tree_ndvi.db')
    init_database(DATABASE_URL)
    ndvi_processor = NDVIProcessor(DATABASE_URL)
    
    # スケジューラー設定
    scheduler = BackgroundScheduler()
    
    def weekly_ndvi_job():
        """週次NDVI処理ジョブ（最新データ＋1年前比較）"""
        print("Starting weekly NDVI processing job...")
        try:
            today = date.today()
            # 最新のNDVIデータを取得（現在月）
            target_date = today
            result = ndvi_processor.run_latest_processing(target_date)
            print(f"Weekly NDVI processing completed: {result}")
        except Exception as e:
            print(f"Error in weekly NDVI processing: {e}")
    
    # 毎週月曜日の午前3時に実行
    scheduler.add_job(weekly_ndvi_job, 'cron', day_of_week='1', hour='3', minute='0')

# メインページのルート
@app.route('/')
def index():
    return render_template('index.html')

# 廃止: 公園データAPIは削除（マツ・ナラデータに移行）

# 時系列データを返すAPI（元のダミーデータ + NDVIデータ統合対応）
@app.route('/api/timeseries/<park_id>')
def get_timeseries(park_id):
    # ダミーの時系列データを生成
    start_date = datetime(2023, 1, 15)
    data = []
    
    for i in range(12):  # 12ヶ月分のデータ
        current_date = start_date + timedelta(days=30*i)
        
        # 季節変動を模擬（春夏は高く、秋冬は低く）
        month = current_date.month
        if month in [3, 4, 5, 6, 7, 8]:  # 春夏
            base_ndvi = random.uniform(0.6, 0.8)
            base_ndre = random.uniform(0.4, 0.6)
        else:  # 秋冬
            base_ndvi = random.uniform(0.2, 0.4)
            base_ndre = random.uniform(0.1, 0.3)
        
        # 公園ごとに少し異なる傾向を追加
        if park_id == "park_002":  # 上野公園は少し健康度が低い設定
            base_ndvi *= 0.9
            base_ndre *= 0.9
        elif park_id == "park_001":  # 新宿御苑は健康度が高い設定
            base_ndvi *= 1.1
            base_ndre *= 1.1
        
        data.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "ndvi": round(base_ndvi, 3),
            "ndre": round(base_ndre, 3),
            "psri": round(random.uniform(0.05, 0.15), 3)
        })
    
    return jsonify(data)

# 市民レポート投稿API
@app.route('/api/submit', methods=['POST'])
def submit_citizen_report():
    try:
        # 画像ファイルの取得
        if 'image' not in request.files:
            return jsonify({'error': '画像ファイルが必要です'}), 400
        
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'error': '画像ファイルが選択されていません'}), 400
        
        # フォームデータの取得
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        report_type = request.form.get('report_type', '健康チェック')
        severity = request.form.get('severity', '3')
        description = request.form.get('description', '')
        existing_tree_id = request.form.get('existing_tree_id')
        
        print(f"フォームデータ: latitude={latitude}, longitude={longitude}, existing_tree_id={existing_tree_id}")
        
        # 既存樹木の場合は位置情報不要、新規樹木の場合は必要
        if not existing_tree_id and (not latitude or not longitude):
            return jsonify({'error': '位置情報が必要です'}), 400
        
        # 座標変換
        if existing_tree_id:
            # 既存樹木の場合：NDVIデータベースから実際の座標を取得
            try:
                print(f"既存樹木ID検索開始: {existing_tree_id}, type: {type(existing_tree_id)}")
                from models import get_database_session, TreePoint
                session = get_database_session()
                
                # 全てのTreePointを確認
                all_points = session.query(TreePoint).all()
                print(f"データベース内のTreePoint数: {len(all_points)}")
                for point in all_points[:5]:  # 最初の5件を表示
                    print(f"  TreePoint: id={point.id}, lat={point.lat}, lon={point.lon}")
                
                # 特定のIDで検索
                tree_point = session.query(TreePoint).filter(TreePoint.id == int(existing_tree_id)).first()
                print(f"検索結果: {tree_point}")
                
                if tree_point:
                    lat, lng = tree_point.lat, tree_point.lon
                    print(f"既存樹木ID {existing_tree_id}の座標を取得: ({lat}, {lng})")
                else:
                    lat, lng = 0.0, 0.0  # 見つからない場合のフォールバック
                    print(f"既存樹木ID {existing_tree_id}が見つかりません - 全データベース検索を実行")
                    # 全件検索でIDが存在するか確認
                    for point in all_points:
                        if str(point.id) == str(existing_tree_id):
                            lat, lng = point.lat, point.lon
                            print(f"文字列マッチで発見: ({lat}, {lng})")
                            break
                
                session.close()
            except Exception as e:
                import traceback
                print(f"座標取得エラー: {e}")
                print(f"エラー詳細: {traceback.format_exc()}")
                lat, lng = 0.0, 0.0
        else:
            # 新規樹木の場合：フォームから座標を取得
            try:
                lat = float(latitude)
                lng = float(longitude)
                if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                    raise ValueError("無効な座標")
            except ValueError:
                return jsonify({'error': '無効な位置情報です'}), 400
        
        # ユニークなIDを生成
        report_id = str(uuid.uuid4())
        
        # 画像データを読み取り
        image_data = image_file.read()
        
        # AI予測を実行
        from io import BytesIO
        ai_prediction = None
        ai_confidence = 0.0
        
        try:
            image_stream = BytesIO(image_data)
            ai_prediction, ai_confidence = predict_tree_health(image_stream)
            print(f"AI予測結果: {ai_prediction}, 信頼度: {ai_confidence}")
        except Exception as e:
            print(f"AI予測エラー: {e}")
            # エラーの場合はデフォルト値を設定
            ai_prediction = "Class1"
            ai_confidence = 0.5
        
        # データベースに保存
        conn = sqlite3.connect('tree_reports.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO citizen_reports 
        (id, latitude, longitude, report_type, severity, description, image_data, image_filename, status, ai_prediction, ai_confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            report_id,
            lat,
            lng,
            report_type,
            int(severity),
            description,
            image_data,
            image_file.filename,
            'analyzing',
            ai_prediction,
            ai_confidence
        ))
        
        conn.commit()
        conn.close()
        
        # NDVI機能が有効な場合、ポイントをNDVIデータベースにも追加
        if NDVI_ENABLED:
            try:
                # 直接TreePointテーブルに追加
                from models import get_database_session, TreePoint
                session = get_database_session()
                
                new_tree_point = TreePoint(
                    tree_id=report_id,
                    species='市民報告',
                    lon=lng,
                    lat=lat,
                    source='citizen_report',
                    description=f'{report_type}: {description}'
                )
                
                session.add(new_tree_point)
                session.commit()
                print(f"Tree point added: ID={new_tree_point.id}, coords=({lng}, {lat})")
                session.close()
                
            except Exception as e:
                print(f"Failed to add point to NDVI database: {e}")
                import traceback
                print(f"Error details: {traceback.format_exc()}")
        
        print(f"データベースに保存されたレポート:")
        print(f"  ID: {report_id}")
        print(f"  位置: ({lat}, {lng})")
        print(f"  タイプ: {report_type}")
        print(f"  深刻度: {severity}")
        print(f"  説明: {description}")
        print(f"  画像ファイル: {image_file.filename}")
        print(f"  画像サイズ: {len(image_data)} bytes")
        
        # レスポンス
        return jsonify({
            'success': True,
            'message': '報告を受信しました。ありがとうございます！',
            'report_id': report_id
        })
        
    except Exception as e:
        import traceback
        print(f"詳細エラー: {str(e)}")
        print(f"エラートレースバック:")
        print(traceback.format_exc())
        return jsonify({'error': f'サーバーエラーが発生しました: {str(e)}'}), 500

# AI分析結果取得API（ダミー）
@app.route('/api/get_analysis_result/<report_id>')
def get_analysis_result(report_id):
    try:
        # ダミーの分析結果を複数パターン用意
        dummy_results = [
            {
                "tree_species": "クロマツ",
                "species_confidence": 0.92,
                "health_status": "初期症状の可能性",
                "health_score": 75.5,
                "issues_detected": ["葉の変色", "軽微な病害の兆候"],
                "recommendations": ["定期的な観察を継続", "専門家による詳細検査を推奨"],
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "tree_species": "ソメイヨシノ",
                "species_confidence": 0.88,
                "health_status": "健康",
                "health_score": 92.3,
                "issues_detected": [],
                "recommendations": ["現在の管理を継続"],
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "tree_species": "イチョウ",
                "species_confidence": 0.95,
                "health_status": "要注意",
                "health_score": 65.8,
                "issues_detected": ["葉の萎縮", "枝の一部で枯れ"],
                "recommendations": ["早急な専門家診断が必要", "周辺の樹木も調査推奨"],
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        ]
        
        # report_idに基づいてランダムに結果を選択
        result_index = hash(report_id) % len(dummy_results)
        dummy_result = dummy_results[result_index]
        
        # データベースに分析結果を保存
        conn = sqlite3.connect('tree_reports.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE citizen_reports 
        SET status = ?, analysis_result = ?, tree_species = ?, health_score = ?, 
            health_status = ?, analysis_date = ?
        WHERE id = ?
        ''', (
            'completed',
            json.dumps(dummy_result),
            dummy_result['tree_species'],
            dummy_result['health_score'],
            dummy_result['health_status'],
            dummy_result['analysis_date'],
            report_id
        ))
        
        conn.commit()
        conn.close()
        
        # NDVI機能が有効な場合、樹種情報を更新
        if NDVI_ENABLED:
            try:
                session = get_database_session()
                tree_point = session.query(TreePoint).filter_by(tree_id=report_id).first()
                if tree_point:
                    tree_point.species = dummy_result['tree_species']
                    session.commit()
                    print(f"Updated tree species in NDVI database: {dummy_result['tree_species']}")
            except Exception as e:
                print(f"Failed to update tree species in NDVI database: {e}")
        
        print(f"分析結果をデータベースに保存: {report_id}")
        
        return jsonify({
            'success': True,
            'analysis_complete': True,
            'result': dummy_result
        })
        
    except Exception as e:
        print(f"分析結果取得エラー: {str(e)}")
        return jsonify({'error': '分析結果の取得に失敗しました'}), 500

# 市民レポート一覧取得API
@app.route('/api/citizen-reports')
def get_citizen_reports():
    try:
        conn = sqlite3.connect('tree_reports.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, latitude, longitude, report_type, severity, status, 
               timestamp, tree_species, health_score
        FROM citizen_reports
        ORDER BY timestamp DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        reports = []
        for row in rows:
            reports.append({
                "id": row[0],
                "latitude": row[1],
                "longitude": row[2],
                "report_type": row[3],
                "severity": row[4],
                "status": row[5],
                "timestamp": row[6],
                "tree_species": row[7],
                "health_score": row[8]
            })
        
        # データベースが空の場合はダミーデータを返す
        if not reports:
            dummy_reports = [
                {
                    "id": "demo_001",
                    "latitude": 35.6895,
                    "longitude": 139.6917,
                    "report_type": "病気の疑い",
                    "severity": 4,
                    "status": "completed",
                    "timestamp": "2024-01-15 10:30:00",
                    "tree_species": "クロマツ",
                    "health_score": 65.5
                },
                {
                    "id": "demo_002", 
                    "latitude": 35.6581,
                    "longitude": 139.7455,
                    "report_type": "健康チェック",
                    "severity": 2,
                    "status": "analyzing",
                    "timestamp": "2024-01-15 11:15:00",
                    "tree_species": None,
                    "health_score": None
                }
            ]
            return jsonify(dummy_reports)
        
        return jsonify(reports)
        
    except Exception as e:
        print(f"市民レポート取得エラー: {str(e)}")
        return jsonify({'error': 'データ取得に失敗しました'}), 500

# 画像表示API
@app.route('/api/image/<report_id>')
def get_image(report_id):
    try:
        conn = sqlite3.connect('tree_reports.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT image_data, image_filename FROM citizen_reports WHERE id = ?', (report_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            image_data, filename = row
            
            # ファイル拡張子から MIME type を判定
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                if filename.lower().endswith('.png'):
                    mime_type = 'image/png'
                elif filename.lower().endswith('.gif'):
                    mime_type = 'image/gif'
                elif filename.lower().endswith('.bmp'):
                    mime_type = 'image/bmp'
                else:
                    mime_type = 'image/jpeg'
            else:
                mime_type = 'image/jpeg'  # デフォルト
            
            # 直接画像データを返す（Base64ではなく）
            response = make_response(image_data)
            response.headers.set('Content-Type', mime_type)
            response.headers.set('Content-Disposition', 'inline', filename=filename)
            return response
        else:
            return jsonify({'error': '画像が見つかりません'}), 404
            
    except Exception as e:
        print(f"画像取得エラー: {str(e)}")
        return jsonify({'error': '画像取得に失敗しました'}), 500

# === NDVI関連のAPI（条件付きで有効） ===

if NDVI_ENABLED:
    @app.route('/api/trigger-ndvi-processing', methods=['POST'])
    def trigger_ndvi_processing():
        """NDVI処理を手動でトリガー"""
        try:
            data = request.get_json() or {}
            target_date = data.get('target_date')
            
            if target_date:
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            else:
                target_date = date.today()
            
            # 最新データ処理を実行（現在月＋前年同月比較）
            result = ndvi_processor.run_latest_processing(target_date)
            return jsonify(result)
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/ndvi-points', methods=['GET'])
    def get_ndvi_points():
        """NDVIポイントデータを取得"""
        try:
            session = get_database_session()
            
            points = []
            tree_points = session.query(TreePoint).all()
            
            for point in tree_points:
                tree_id = point.tree_id or ''
                species = point.species or ''
                
                # 本物マツ・ナラデータ + 市民報告データを含める
                is_real_matsu = 'マツ' in species and ('PT' in tree_id or 'MATSU_ROAD' in tree_id)
                is_real_nara = ('ナラ' in species or 'カシ' in species) and ('PT' in tree_id or 'NARA_ROAD' in tree_id)
                is_citizen_report = species == '市民報告'  # 新規追加
                
                if not (is_real_matsu or is_real_nara or is_citizen_report):
                    continue  # その他のテストデータ除外
                
                # 地理的範囲チェック（東京都周辺のみ）
                lat, lon = point.lat, point.lon
                if not (35.0 <= lat <= 36.0 and 138.5 <= lon <= 140.5):
                    continue  # 異常値除外
                
                # 海上チェック
                if (lat < 35.4 and 139.7 <= lon <= 140.1):
                    continue  # 東京湾内除外
                
                latest_sample = session.query(NDVISample)\
                    .filter_by(tree_point_id=point.id)\
                    .order_by(NDVISample.period_month.desc())\
                    .first()
                
                # 本物データのみ表示
                points.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [point.lon, point.lat]
                    },
                    'properties': {
                        'id': point.id,
                        'tree_id': point.tree_id,
                        'species': point.species,
                        'period': latest_sample.period_month.isoformat() if latest_sample else None,
                        'ndvi': latest_sample.ndvi if latest_sample else None,
                        'ndvi_prev_year': latest_sample.ndvi_prev_year if latest_sample else None,
                        'ndvi_diff': latest_sample.ndvi_diff if latest_sample else None
                    }
                })
            
            return jsonify({
                'type': 'FeatureCollection',
                'features': points
            })
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500

# AI画像認識エンドポイント
@app.route('/predict', methods=['POST'])
def predict_endpoint():
    if 'file' not in request.files:
        return jsonify({'error': 'ファイルがありません'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    try:
        # AI予測を実行
        prediction, confidence = predict_tree_health(file.stream)
        
        if prediction is None:
            return jsonify({'error': 'AI予測に失敗しました'}), 500
            
        return jsonify({
            'prediction': prediction,
            'confidence': round(confidence, 4),
            'health_status': 'healthy' if 'Class1' in prediction else 'unhealthy'
        })
        
    except Exception as e:
        print(f"予測エラー: {e}")
        return jsonify({'error': str(e)}), 500

# 樹木の報告履歴を取得
@app.route('/api/tree-reports/<tree_id>')
def get_tree_reports(tree_id):
    try:
        conn = sqlite3.connect('tree_reports.db')
        cursor = conn.cursor()
        
        # 樹木IDまたは座標で報告を検索
        cursor.execute('''
            SELECT id, report_type, severity, description, image_filename, timestamp, ai_prediction, ai_confidence, latitude, longitude
            FROM citizen_reports 
            ORDER BY timestamp DESC
            LIMIT 100
        ''')
        
        # 結果をフィルタリング（同じエリアまたは同じtree_id）
        all_reports = cursor.fetchall()
        target_reports = []
        
        for row in all_reports:
            report_id = row[0]
            lat = row[8]
            lng = row[9]
            
            # 座標が近い場合（約100m以内）またはIDが一致する場合
            if report_id == tree_id:
                target_reports.append(row)
            else:
                # NDVIデータベースからtree_idに対応する座標を取得
                try:
                    from models import get_database_session, TreePoint
                    session = get_database_session()
                    tree_point = session.query(TreePoint).filter(TreePoint.id == int(tree_id)).first()
                    if tree_point:
                        # 距離計算（簡易版）
                        lat_diff = abs(float(lat) - tree_point.lat)
                        lng_diff = abs(float(lng) - tree_point.lon)
                        if lat_diff < 0.001 and lng_diff < 0.001:  # 約100m以内
                            target_reports.append(row)
                    session.close()
                except:
                    pass
        
        reports = []
        for row in target_reports[:20]:  # 最新20件
            report = {
                'id': row[0],
                'report_type': row[1],
                'severity': row[2],
                'description': row[3],
                'tree_image': row[4],
                'timestamp': row[5],
                'ai_prediction': row[6],
                'ai_confidence': row[7]
            }
            reports.append(report)
        
        conn.close()
        return jsonify(reports)
        
    except Exception as e:
        print(f"報告履歴取得エラー: {e}")
        return jsonify([])
    
    @app.route('/api/ndvi-alerts', methods=['GET'])
    def get_ndvi_alerts():
        """NDVIアラート（閾値を超える差分）を取得"""
        try:
            threshold = float(request.args.get('threshold', -0.1))
            alerts = ndvi_processor.get_alerts(threshold=threshold)
            
            features = []
            for alert in alerts:
                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [alert['lon'], alert['lat']]
                    },
                    'properties': {
                        'id': alert['point_id'],
                        'tree_id': alert['tree_id'],
                        'species': alert['species'],
                        'period': alert['period_month'],
                        'ndvi_diff': alert['ndvi_diff'],
                        'severity': alert['severity']
                    }
                })
            
            return jsonify({
                'type': 'FeatureCollection',
                'features': features
            })
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/import-points', methods=['POST'])
    def import_points():
        """CSVからポイントをインポート"""
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'ファイルが必要です'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'ファイルが選択されていません'}), 400
            
            # 一時ファイルとして保存
            import tempfile
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, file.filename)
            file.save(temp_path)
            
            try:
                count = ndvi_processor.import_points_from_csv(
                    temp_path,
                    lon_col=request.form.get('lon_col', '経度'),
                    lat_col=request.form.get('lat_col', '緯度'),
                    species_col=request.form.get('species_col', '樹種'),
                    id_col=request.form.get('id_col')
                )
                
                return jsonify({
                    'success': True,
                    'imported_count': count,
                    'message': f'{count}件のポイントをインポートしました'
                })
                
            finally:
                os.remove(temp_path)
                os.rmdir(temp_dir)
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/ndvi-status')
def get_ndvi_status():
    """NDVI機能の状態を確認"""
    if NDVI_ENABLED:
        try:
            session = get_database_session()
            point_count = session.query(TreePoint).count()
            sample_count = session.query(NDVISample).count()
            
            return jsonify({
                'enabled': True,
                'point_count': point_count,
                'sample_count': sample_count,
                'database_url': DATABASE_URL
            })
        except Exception as e:
            return jsonify({
                'enabled': True,
                'error': str(e)
            })
    else:
        return jsonify({
            'enabled': False,
            'message': 'NDVI機能は無効です（依存関係をインストールしてください）'
        })
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    # AI初期化
    initialize_ai()
    
    # スケジューラー開始（NDVI機能が有効な場合のみ）
    if NDVI_ENABLED:
        scheduler.start()
    
    try:
        # 本番環境では環境変数からポートを取得
        port = int(os.environ.get('PORT', 5000))
        debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
        
        app.run(debug=debug_mode, host='0.0.0.0', port=port)
    finally:
        if NDVI_ENABLED:
            scheduler.shutdown()