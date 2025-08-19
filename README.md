# 東京都公園樹木健康監視システム

このプロジェクトは、東京都知事杯オープンデータハッカソンに向けて開発された、衛星データを活用した公園樹木の健康状態可視化システムです。

## 🌟 機能

- **インタラクティブ地図**: Leafletを使用した東京都内の公園表示
- **時系列分析**: NDVI、NDRE、PSRI指数による樹木健康度の経時変化
- **リアルタイム可視化**: クリック操作による即座のデータ表示
- **レスポンシブデザイン**: PC・モバイル対応

## 🛠️ 技術スタック

### バックエンド
- **Flask**: 軽量Webフレームワーク
- **Python**: データ処理とAPI提供

### フロントエンド
- **Leaflet**: インタラクティブ地図ライブラリ
- **Chart.js**: 時系列グラフ表示
- **HTML5/CSS3/JavaScript**: モダンWeb技術

### データソース
- **Sentinel-2衛星データ**: Google Earth Engine経由
- **東京都オープンデータ**: 公園・樹木位置情報

## 🚀 セットアップ手順

### 1. 環境準備
```bash
# リポジトリのクローン
git clone <repository-url>
cd opendata

# 仮想環境の作成（推奨）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# または
venv\Scripts\activate  # Windows

# 依存関係のインストール
pip install -r requirements.txt
```

### 2. アプリケーションの起動
```bash
python app.py
```

### 3. ブラウザでアクセス
```
http://localhost:5000
```

## 📁 プロジェクト構造

```
opendata/
├── app.py                 # Flaskアプリケーション
├── requirements.txt       # Python依存関係
├── README.md             # プロジェクト説明
├── templates/
│   └── index.html        # メインページテンプレート
├── static/
│   ├── style.css         # スタイルシート
│   └── script.js         # JavaScript機能
└── suginami/             # 既存データファイル
    ├── opendata_1500.csv
    └── ...
```

## 🎯 API エンドポイント

### GET `/api/parks`
公園の境界データをGeoJSON形式で取得

**レスポンス例:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {...},
      "properties": {
        "park_id": "park_001",
        "park_name": "新宿御苑"
      }
    }
  ]
}
```

### GET `/api/timeseries/<park_id>`
指定公園の時系列データを取得

**レスポンス例:**
```json
[
  {
    "date": "2023-01-15",
    "ndvi": 0.25,
    "ndre": 0.15,
    "psri": 0.08
  }
]
```

## 🌱 開発ロードマップ

### 現在の状態（プロトタイプ）
- [x] 基本的なWeb UI
- [x] ダミーデータによる動作確認
- [x] インタラクティブな地図表示
- [x] 時系列グラフ機能

### 今後の予定
- [ ] Google Earth Engine API連携
- [ ] リアルタイムデータ更新
- [ ] ヒートマップ機能
- [ ] アラート通知機能
- [ ] データエクスポート機能

## 🔧 開発・カスタマイズ

### 新しい指数の追加
1. `app.py`の`get_timeseries()`関数でデータ項目を追加
2. `script.js`の`displayChart()`関数でグラフ設定を更新

### 地図スタイルの変更
- `static/style.css`の`.park-polygon`クラスを編集

### 新しい公園の追加
- `app.py`の`get_parks()`関数内のGeoJSONデータを編集

## 📊 データ分析指標

- **NDVI (正規化植生指数)**: 植物の緑の健康度を示す基本指標
- **NDRE (正規化差分レッドエッジ)**: より詳細な植物活性度
- **PSRI (植物老化反射指数)**: 植物の老化や病害状態

## 🎨 デザインコンセプト

- **自然をイメージした緑系カラーパレット**
- **直感的な操作性を重視したUI**
- **データの可読性を最優先としたグラフデザイン**

## 📱 デプロイメント

### Vercel（推奨）
```bash
# vercel-cliのインストール
npm i -g vercel

# デプロイ
vercel
```

### PythonAnywhere
1. ファイルをアップロード
2. Webアプリを設定
3. WSGIファイルを設定

## 🤝 コントリビューション

1. このリポジトリをフォーク
2. フィーチャーブランチを作成
3. 変更をコミット
4. プルリクエストを作成

## 📄 ライセンス

このプロジェクトはMITライセンスのもとで公開されています。

## 🏆 謝辞

- 東京都知事杯オープンデータハッカソン主催者
- Google Earth Engine開発チーム
- オープンソースコミュニティ 