"""
データベースモデル定義
SQLAlchemyを使用してNDVIサンプリングとツリーポイントのデータモデルを定義
"""

from sqlalchemy import Column, Integer, Float, String, Date, DateTime, ForeignKey, create_engine, UniqueConstraint, Text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class TreePoint(Base):
    """樹木ポイントのデータモデル"""
    __tablename__ = 'tree_points'
    
    id = Column(Integer, primary_key=True)
    tree_id = Column(String, unique=True, nullable=True)  # 外部ID（市民レポートのIDなど）
    species = Column(String, nullable=True)  # 樹種
    lon = Column(Float, nullable=False)  # 経度
    lat = Column(Float, nullable=False)  # 緯度
    source = Column(String, nullable=True)  # データソース（citizen_report, csv_import など）
    description = Column(Text, nullable=True)  # 説明
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # NDVIサンプルとのリレーション
    ndvi_samples = relationship("NDVISample", back_populates="tree_point")

class NDVISample(Base):
    """NDVIサンプルのデータモデル"""
    __tablename__ = 'ndvi_samples'
    
    id = Column(Integer, primary_key=True)
    tree_point_id = Column(Integer, ForeignKey('tree_points.id'), nullable=False)
    period_month = Column(Date, nullable=False)  # サンプル期間（月初日で統一: 2024-01-01）
    ndvi = Column(Float, nullable=True)  # 当月のNDVI値
    ndvi_prev_year = Column(Float, nullable=True)  # 前年同月のNDVI値
    ndvi_diff = Column(Float, nullable=True)  # 差分（当月 - 前年同月）
    cloud_cover = Column(Float, nullable=True)  # 雲被覆率
    pixel_count = Column(Integer, nullable=True)  # サンプルピクセル数
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # ツリーポイントとのリレーション
    tree_point = relationship("TreePoint", back_populates="ndvi_samples")
    
    # 同じポイントの同じ月のデータは1つだけ
    __table_args__ = (UniqueConstraint('tree_point_id', 'period_month', name='_tree_period_uc'),)

def get_database_session(database_url=None):
    """データベースセッションを取得"""
    if database_url is None:
        database_url = os.environ.get('DATABASE_URL', 'sqlite:///tree_ndvi.db')
    
    # SQLiteの場合は同時接続の制限を緩和
    connect_args = {}
    if database_url.startswith("sqlite:"):
        connect_args = {"check_same_thread": False}
    
    engine = create_engine(database_url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def init_database(database_url=None):
    """データベースを初期化"""
    if database_url is None:
        database_url = os.environ.get('DATABASE_URL', 'sqlite:///tree_ndvi.db')
    
    connect_args = {}
    if database_url.startswith("sqlite:"):
        connect_args = {"check_same_thread": False}
    
    engine = create_engine(database_url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    print(f"データベースが初期化されました: {database_url}")
    return engine
