# マツ・ナラNDVI監視システム

このシステムは、Google Earth Engineを使用してマツ・ナラのNDVIデータを監視し、市民レポート機能を提供します。

## 🌟 機能

- **インタラクティブ地図**: Leafletを使用したマツ・ナラ樹木のNDVI監視
- **NDVI分析**: 前年同期比による植生変化の可視化
- **市民レポート**: 画像アップロードとAI画像認識による樹木健康診断
- **リアルタイム可視化**: クリック操作による即座のデータ表示
- **レスポンシブデザイン**: PC・モバイル対応

## 🛠️ 技術スタック

### バックエンド
- **Flask**: 軽量Webフレームワーク
- **Python**: データ処理とAPI提供
- **TensorFlow**: AI画像認識
- **Google Earth Engine**: 衛星データ処理

### フロントエンド
- **Leaflet**: インタラクティブ地図ライブラリ
- **HTML5/CSS3/JavaScript**: モダンWeb技術

### データソース
- **Sentinel-2衛星データ**: Google Earth Engine経由
- **東京都オープンデータ**: マツ・ナラ樹木位置情報

## 🚀 デプロイ方法

### GitHub Pages + Heroku デプロイ

#### 1. GitHubリポジトリの準備
```bash
git add .
git commit -m "Initial commit for deployment"
git push origin main
```

#### 2. GitHub Pages設定
- リポジトリのSettings → Pages
- Source: Deploy from a branch
- Branch: gh-pages
- フォルダ: / (root)

#### 3. Herokuデプロイ
```bash
# Heroku CLIインストール
npm install -g heroku

# ログイン
heroku login

# アプリ作成
heroku create your-app-name

# 環境変数設定
heroku config:set FLASK_ENV=production
heroku config:set FLASK_DEBUG=False
heroku config:set SECRET_KEY=your-secret-key-here

# デプロイ
git push heroku main
```

### Vercel デプロイ

#### 1. Vercel CLIインストール
```bash
npm i -g vercel
```

#### 2. デプロイ
```bash
vercel --prod
```

## 🔧 環境変数

`env.example`ファイルを参考に`.env`ファイルを作成して以下の設定を行ってください：

```bash
# Google Earth Engine設定
GOOGLE_APPLICATION_CREDENTIALS=local-disk-456715-v8-b93668af19ac.json
GEE_PROJECT_ID=local-disk-456715-v8

# データベース設定
DATABASE_URL=sqlite:///tree_ndvi.db

# Flask設定
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=your-secret-key-here

# TensorFlow設定
TF_CPP_MIN_LOG_LEVEL=2
TF_ENABLE_ONEDNN_OPTS=0
```

## 📁 重要なファイル

- `app.py`: メインアプリケーション
- `models.py`: データベースモデル
- `ndvi_processor.py`: NDVI処理ロジック
- `gee_utils.py`: Google Earth Engine連携
- `static/`: フロントエンドファイル
- `templates/`: HTMLテンプレート
- `*.db`: SQLiteデータベース（NDVIデータ、市民レポート）
- `keras_model.h5`: AI画像認識モデル
- `labels.txt`: AIモデルのラベル

## ⚠️ 注意事項

1. **データベース**: `tree_ndvi.db`と`tree_reports.db`は`.gitignore`に含まれていません（永続化）
2. **AIモデル**: `keras_model.h5`は2.3MBのため、GitHubの制限内です
3. **環境変数**: 本番環境では必ず`.env`ファイルを設定してください
4. **Google Earth Engine**: サービスアカウントの認証情報が必要です

## 📄 ライセンス

このプロジェクトはMITライセンスのもとで公開されています。
