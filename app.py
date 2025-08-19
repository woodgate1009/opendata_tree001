from flask import Flask, render_template, jsonify, request
import json
import os
from datetime import datetime, timedelta
import random
import uuid
import sqlite3
import base64

app = Flask(__name__)

# データベースの初期化
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
    
    conn.commit()
    conn.close()

# アプリ起動時にDBを初期化
init_db()

# メインページのルート
@app.route('/')
def index():
    return render_template('index.html')

# 公園データを返すAPI
@app.route('/api/parks')
def get_parks():
    # ダミーの公園データ（GeoJSON形式）
    parks_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [139.6917, 35.6895],  # 新宿御苑周辺
                        [139.6950, 35.6895],
                        [139.6950, 35.6860],
                        [139.6917, 35.6860],
                        [139.6917, 35.6895]
                    ]]
                },
                "properties": {
                    "park_id": "park_001",
                    "park_name": "新宿御苑"
                }
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [139.7455, 35.6581],  # 上野公園周辺
                        [139.7485, 35.6581],
                        [139.7485, 35.6550],
                        [139.7455, 35.6550],
                        [139.7455, 35.6581]
                    ]]
                },
                "properties": {
                    "park_id": "park_002",
                    "park_name": "上野公園"
                }
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [139.7514, 35.6762],  # 隅田公園周辺
                        [139.7544, 35.6762],
                        [139.7544, 35.6730],
                        [139.7514, 35.6730],
                        [139.7514, 35.6762]
                    ]]
                },
                "properties": {
                    "park_id": "park_003",
                    "park_name": "隅田公園"
                }
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [139.6503, 35.6764],  # 杉並区の公園
                        [139.6533, 35.6764],
                        [139.6533, 35.6734],
                        [139.6503, 35.6734],
                        [139.6503, 35.6764]
                    ]]
                },
                "properties": {
                    "park_id": "park_004",
                    "park_name": "善福寺公園"
                }
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [139.6789, 35.6681],  # 代々木公園周辺
                        [139.6819, 35.6681],
                        [139.6819, 35.6650],
                        [139.6789, 35.6650],
                        [139.6789, 35.6681]
                    ]]
                },
                "properties": {
                    "park_id": "park_005",
                    "park_name": "代々木公園"
                }
            }
        ]
    }
    return jsonify(parks_data)

# 時系列データを返すAPI
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
        
        # バリデーション
        if not latitude or not longitude:
            return jsonify({'error': '位置情報が必要です'}), 400
        
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
        
        # データベースに保存
        conn = sqlite3.connect('tree_reports.db')
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO citizen_reports 
        (id, latitude, longitude, report_type, severity, description, image_data, image_filename, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            report_id,
            lat,
            lng,
            report_type,
            int(severity),
            description,
            image_data,
            image_file.filename,
            'analyzing'
        ))
        
        conn.commit()
        conn.close()
        
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
            'message': 'アップロード成功！AIによる分析を開始します。',
            'report_id': report_id,
            'estimated_analysis_time': '30-60秒'
        })
        
    except Exception as e:
        print(f"エラー: {str(e)}")
        return jsonify({'error': 'サーバーエラーが発生しました'}), 500

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
            # Base64エンコードして返す
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
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
            
            return jsonify({
                'success': True,
                'image_data': f'data:{mime_type};base64,{image_base64}',
                'filename': filename
            })
        else:
            return jsonify({'error': '画像が見つかりません'}), 404
            
    except Exception as e:
        print(f"画像取得エラー: {str(e)}")
        return jsonify({'error': '画像取得に失敗しました'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 