import pandas as pd

# --- 設定ここから ---

# 1. 元になるCSVファイルの名前を指定してください
original_csv_file = 'tokyo_gairoju.csv'

# 2. 樹種が書かれている列の名前を指定してください (ご提示の画像から判断)
species_column = '樹種'

# 3. 新しく作るCSVファイルに含めたい列のリストです
#    必須の列と、使えそうだとおっしゃっていた列を追加しています。
columns_to_keep = [
    '樹種',
    '経度',
    '緯度',
    '樹高(m)',
    '枝張(m)',
    '区分',
    '幹周(cm）'
]

# 4. 新しく作成するファイルの名前です
matsu_output_file = 'マツの木リスト.csv'
nara_output_file = 'ナラの木リスト.csv'

# --- 設定ここまで ---


try:
    # 1. 元のCSVファイルを読み込みます
    # ★修正点1: 文字コードを 'cp932' (Shift_JIS) に変更
    print(f"'{original_csv_file}' を読み込んでいます...")
    df = pd.read_csv(original_csv_file, encoding='cp932')
    print("読み込みが完了しました。")

    # 2. 「マツ」が含まれる行を抽出します
    # ★修正点2: 抽出条件を「'マツ'を含み、かつ'キリシマツツジ'と'ヤマツツジ'を含まない」に変更
    print(f"'{species_column}' 列から条件に合う「マツ」を検索中...")
    matsu_df = df[
        df[species_column].str.contains('マツ', na=False) &
        ~df[species_column].str.contains('キリシマツツジ', na=False) &
        ~df[species_column].str.contains('ヤマツツジ', na=False)
    ]
    print(f"マツの木: {len(matsu_df)} 件見つかりました。")

    # 3. 「ナラ」が含まれる行を抽出します (こちらは変更なし)
    print(f"'{species_column}' 列から「ナラ」を含む行を検索中...")
    nara_df = df[df[species_column].str.contains('ナラ', na=False)]
    print(f"ナラの木: {len(nara_df)} 件見つかりました。")

    # 4. 結果を新しいCSVファイルとして保存します
    if not matsu_df.empty:
        print(f"マツの木リストを '{matsu_output_file}' に保存しています...")
        matsu_df[columns_to_keep].to_csv(matsu_output_file, index=False, encoding='utf-8-sig')
        print("保存が完了しました。")
    else:
        print("条件に合うマツの木は見つかりませんでした。ファイルは作成されません。")

    if not nara_df.empty:
        print(f"ナラの木リストを '{nara_output_file}' に保存しています...")
        nara_df[columns_to_keep].to_csv(nara_output_file, index=False, encoding='utf-8-sig')
        print("保存が完了しました。")
    else:
        print("ナラの木は見つかりませんでした。ファイルは作成されません。")

except FileNotFoundError:
    print(f"エラー: ファイル '{original_csv_file}' が見つかりませんでした。ファイル名と場所を確認してください。")
except KeyError as e:
    print(f"エラー: CSVファイルに列 {e} が存在しません。設定の'species_column'や'columns_to_keep'の名前が正しいか確認してください。")
except Exception as e:
    print(f"予期せぬエラーが発生しました: {e}")