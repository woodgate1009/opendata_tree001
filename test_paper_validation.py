#!/usr/bin/env python3
"""
論文検証用のテストスクリプト
自然教育園のNDVI値を論文の基準と比較
"""

import os
import sys
from datetime import date

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """メイン実行関数"""
    print("マツ・ナラNDVI監視システム - 論文検証テスト")
    print("=" * 60)
    
    try:
        # Google Earth Engineの初期化をテスト
        print("1. Google Earth Engine接続テスト...")
        from gee_utils import test_gee_connection
        if test_gee_connection():
            print("OK GEE接続成功")
        else:
            print("NG GEE接続失敗")
            return
        
        print("\n2. 論文検証実行...")
        from gee_utils import validate_against_paper
        results = validate_against_paper()
        
        print("\n3. 詳細結果:")
        print("-" * 40)
        for result in results:
            print(f"日付: {result['date']}")
            print(f"NDVI値: {result['ndvi']}")
            print(f"論文基準: {result['paper_range']}")
            print(f"判定: {result['status']}")
            print(f"色: {result['color']}")
            print("-" * 40)
        
        print("\n4. 統計サマリー:")
        valid_results = [r for r in results if r['ndvi'] is not None]
        if valid_results:
            ndvi_values = [r['ndvi'] for r in valid_results]
            avg_ndvi = sum(ndvi_values) / len(ndvi_values)
            min_ndvi = min(ndvi_values)
            max_ndvi = max(ndvi_values)
            
            print(f"有効データ数: {len(valid_results)}/3")
            print(f"平均NDVI: {avg_ndvi:.4f}")
            print(f"最小NDVI: {min_ndvi:.4f}")
            print(f"最大NDVI: {max_ndvi:.4f}")
            print(f"論文基準範囲(0.7-0.8)内: {sum(1 for v in ndvi_values if 0.7 <= v <= 0.8)}/{len(ndvi_values)}")
        else:
            print("有効なデータがありません")
        
        print("\nOK 論文検証完了!")
        
    except Exception as e:
        print(f"NG エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
