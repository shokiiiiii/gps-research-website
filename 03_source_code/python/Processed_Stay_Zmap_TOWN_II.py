"""GPS滞在データにZmap TOWN IIの建物属性を付与する。"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# ============================================================
# 1. 設定（分析条件は元コードから変更しない）
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent.parent  # 配置想定: scripts/Processed/本ファイル.py
INPUT_DIR = BASE_DIR / "01_Data/raw/GPS_data_with_socio" 
BUFFER_DIR = BASE_DIR / "01_Data/Building/Buffer_5km"
BUILDING_DIR = BASE_DIR / "01_Data/Building/GPKG_Zmap_Town_II"
OUTPUT_DIR = BASE_DIR / "01_Data/processed/Stay_region_building"
METRIC_CRS = "EPSG:30163" #メートル単位での距離計算
GPS_CRS = "EPSG:4326" #緯度経度での管理
MAX_NEAREST_DISTANCE_M = 500.0  # 最近傍建物までの最大許容距離（m）
ACTIVITY_MODE = "activity"
INPUT_PATTERN = "trips_*.parquet"
PARQUET_COMPRESSION = "snappy" 

REGIONS = {
    "西条_5km": {
        "shp": BUILDING_DIR / "Saijo_5km_buildings.gpkg",
        "buffer": BUFFER_DIR / "buffer_5km_SaijoStation.gpkg",
        "output": OUTPUT_DIR / "Stay_Saijo_5km_building_Z.parquet",
    },
    "広島_5km": {
        "shp": BUILDING_DIR / "Hiroshima_5km_buildings.gpkg",
        "buffer": BUFFER_DIR / "buffer_5km_HiroshimaStation.gpkg",
        "output": OUTPUT_DIR / "Stay_Hiroshima_5km_building_Z.parquet",
    },
}# もし同じ処理を新たな地域で行いたい場合、ここに追加すれば良い
REQUIRED_COLUMNS = [
    "User_Id", "Trip_Id", "TripMode", "Time_start", "Time_end",
    "Latitude_start", "Latitude_end", "Longitude_start", "Longitude_end",
    "gender", "age_group", "device_os", "device_model",
    "device_os_version", "device_carrier", "ip_address",
    "Home_Latitude", "Home_Longitude", "Office_Latitude", "Office_Longitude",
]
MATCH_TYPES = ("polygon_intersection", "nearest_polygon")
#滞在地点と建物ポリゴン突き合わせの方法
#polygon_intersection：滞在地点の中点が建物ポリゴンに重なる
#nearest_polygon：重ならない場合、最近傍建物ポリゴンを割り当てる

def load_buildings(shp_path: Path, buffer_path: Path, region_label: str):
    """建物と5kmバッファを読み込む。

    引数:
        shp_path: 建物SHPのパス
        buffer_path: 5kmバッファのパス
        region_label: 地域名

    戻り値:
        (建物GeoDataFrame, 地域Polygon)
        両者はMETRIC_CRSを使用。

    処理条件:
        - geometryが欠損・空のデータを削除
        - Polygon/MultiPolygon以外を削除
        - 無効なgeometryを修復せず削除
        - housenameが欠損・空のデータを削除
        - 建物の代表点をGPS座標に変換
        - 5kmバッファは1件であることを確認
    """
    for path in (shp_path, buffer_path):
        if not path.exists():
            raise FileNotFoundError(f"入力が存在しません: {path}")
    buildings = gpd.read_file(shp_path) #gpd:geopandas, geodataframeとしてデータを読む(geometoryを読み込むため）
    buffers = gpd.read_file(buffer_path) 
    if buildings.crs is None or buffers.crs is None: #.crsでcrsを確認できる
        raise ValueError(f"{region_label}: 建物SHPまたはバッファにCRSがありません") #(f"[変数名]"：表示させたい内容")で変数名を呼び出せる

    buildings = buildings.to_crs(METRIC_CRS)
    buffers = buffers.to_crs(METRIC_CRS)
    buildings = buildings.loc[
        buildings.geometry.notna() & ~buildings.geometry.is_empty
        & buildings.geom_type.isin(["Polygon", "MultiPolygon"])
    ].copy() #buildings.locでデータの指定ができる, .notna()：欠損していないか、empty：空白ではないか、.geom_type.isin：後述のデータ形状か
    if buildings.empty:
        raise ValueError(f"{region_label}: 有効な建物ポリゴンがありません")
    # 無効なgeometryを削除（修復しない）
    invalid = ~buildings.geometry.is_valid
    n_invalid = int(invalid.sum())

    print(f"[{region_label}] 無効なgeometryを{n_invalid:,}件削除")

    buildings = buildings.loc[~invalid].copy()
    

    name_col = "housename"
    if name_col not in buildings.columns:
        raise KeyError(
            f"housename列がありません。実際の列: {list(buildings.columns)}"
        )

    buildings["housename"] = (
        buildings[name_col].astype("string").str.strip() #.astype("string")：文字列型にデータ構造を変換,　.str.stirp()：文字の最初と最後の空白を削除
    )

    # 建物名に含まれる名称数を計算
    buildings["n_names"] = (
    buildings["housename"].str.count("/") + 1 # str.count("/") string("/"") をcount (のちに建物ポリゴンが重複している複数名があるポリゴンの判別に使用)
    ).astype("Int64")

    # 建物名が欠損・空のデータを削除
    buildings = buildings.loc[
        buildings["housename"].notna()
        & buildings["housename"].ne("")
    ].copy()



    # 建物の代表点を取得
    centers = buildings.geometry.representative_point().to_crs(GPS_CRS) # 建物代表点は計算に使うのではなく、可視化に使用する(現在使用しない予定)

    buildings["Building_Latitude"] = centers.y.to_numpy() #取り出したy座標を数値の数列リストに変換する
    buildings["Building_Longitude"] = centers.x.to_numpy()

    # 複数の建物名が統合されたポリゴンかを判定
    # 条件はこれだけで、全く同じ結果になります
    buildings["building_overlap"] = buildings["n_names"].gt(1).fillna(False) #.gt(1)：grater than 1；n_nameが１より大きい

    # 出力列を整理
    buildings = buildings[[
        "housename",
        "n_names",
        "Building_Latitude",
        "Building_Longitude",
        "building_overlap",
        "geometry",
    ]].reset_index(drop=True)

    # バッファを確認
    if len(buffers) != 1: #!= ：等しくない
        raise ValueError(
            f"{region_label}: 5kmバッファは1件の想定ですが{len(buffers)}件です"
        )

    region_geometry = buffers.geometry.iloc[0] #　.iloc[0]：一番最初のデータ、つまりgeometory

    if region_geometry is None or region_geometry.is_empty:
        raise ValueError(
            f"{region_label}: 5kmバッファが空です"
        )

    print(
        f"[{region_label}] "
        f"建物 {len(buildings):,}件 / "
        f"無効geometry除外 {n_invalid:,}件 / "
        f"CRS {METRIC_CRS}"
    )

    return buildings, region_geometry


def prepare_activity(df: pd.DataFrame) -> pd.DataFrame:
    """TripModeがactivityの滞在を抽出する。

    引数: df はGPS入力テーブル（TripMode列が必要）。
    戻り値: TripModeがactivityのDataFrame。
    条件: TripModeは前後空白・大文字小文字を無視する。
    """
    return df.loc[
        df["TripMode"].astype("string").str.strip().str.lower().eq(ACTIVITY_MODE) #.str.lower():文字を全て小文字にする #.eq(ACTIVITY_MODE)：ACTIVITY_MODEと一致する
    ].copy()


def extract_inside_region(activity_df: pd.DataFrame, region_crs, region_geometry) -> pd.DataFrame:
    """開始・終了地点が両方とも地域内の滞在のみ抽出する。

    引数: activity_df は座標列を持つ滞在、region_crs は地域CRS、
        region_geometry は対象地域ポリゴン。
    戻り値: 条件を満たす元の列構造のDataFrame。
    条件: 境界上も含める（covers）。中点だけでは地域内判定しない。
    """
    if activity_df.empty:
        return activity_df.copy()
    masks = []
    for suffix in ("start", "end"):
        points = gpd.GeoSeries( #GeoSeries：位置データを扱うための専用の列を作成
            gpd.points_from_xy(
                activity_df[f"Longitude_{suffix}"],
                activity_df[f"Latitude_{suffix}"],
            ), index=activity_df.index, crs=GPS_CRS, #index = acitivitydf.index：このlocationデータのindexとactivityデータのindexを紐付けしている
        ).to_crs(region_crs)
        masks.append(points.covered_by(region_geometry)) #.cover_by():()内のエリア内部または境界にあるかを判定
    return activity_df.loc[masks[0] & masks[1]].copy()


def assign_building(region_df: pd.DataFrame, building_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """GPS滞在中点に建物ポリゴンを割り当てる。

    引数:
        region_df: 地域内のGPS滞在データ
        building_gdf: 建物ポリゴンデータ
    戻り値:
        建物属性を付与したDataFrame
    処理条件:
        ポリゴン内一致を優先し、未一致の場合は最近傍建物を割り当てる。
        複数候補がある場合はindex_rightの小さい建物を採用する。
        最近傍距離の上限は設定しない。
    """
    if region_df.empty:
        return region_df.copy()

    df = region_df.copy().reset_index(drop=True)
    df["_row_id"] = np.arange(len(df)) #np.arrange():0からn-1までの整数を生成

    df["Midpoint_Latitude"] = (df["Latitude_start"] + df["Latitude_end"]) / 2
    df["Midpoint_Longitude"] = (df["Longitude_start"] + df["Longitude_end"]) / 2

    points = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(
            df["Midpoint_Longitude"], df["Midpoint_Latitude"]
        ),
        crs=GPS_CRS,
    ).to_crs(building_gdf.crs)

    # ポリゴン内一致
    joined = gpd.sjoin( #地理空間データの結合、今回はhowleftなのでbuilding_gdfのindexはindex_rightとして自動的に保存される
        points, building_gdf, how="left", predicate="intersects" #how = left:どちらを基準にするか。今回はgpsを残す。
    ) #predictate = "intersects": 点と建物が交差するか判定
    
    unmatched = joined.loc[joined["index_right"].isna(), "_row_id"] #joined.loc[条件, "コラム"]：条件を満たしたコラムのデータのみを取得できる。
    # 今回は滞在点が建物ポリゴンに交差しない(建物indexが存在しない)ものを取得
    print(f"    ポリゴン内一致: {len(df) - len(unmatched):,} / {len(df):,}") # :,は数字を３桁区切りで表示できる。ex)1,000

    joined["building_match_type"] = MATCH_TYPES[0] #building_match_type = polygon_intersection
    joined["nearest_distance_m"] = 0.0

    # ポリゴン外の地点は最近傍建物を割り当てる
    if not unmatched.empty:
        outside = points.loc[points["_row_id"].isin(unmatched)] #unmatchedに格納されている_row_id

        nearest = gpd.sjoin_nearest(
            outside, building_gdf,
            how="left",
            max_distance=MAX_NEAREST_DISTANCE_M,
            distance_col="nearest_distance_m",
        )

        nearest["building_match_type"] = MATCH_TYPES[1]

        joined = pd.concat([ #.concat()：縦方向にデータを追加する。今回は元々ポリゴン内と判定されていたデータに最近傍割り当てをしたデータを追加する
            joined.loc[~joined["_row_id"].isin(unmatched)],
            nearest,
        ], ignore_index=True)

        print(f"    最近傍割当: {len(nearest):,}")

    joined = pd.DataFrame(joined.sort_values("_row_id"))
    #.map()：building_gdfのgeometoryは複数のgeometoryを含む列データだが、wkb変換はひとつずつでしかできないので、一つずつ取得している。
    polygon_wkb = building_gdf.geometry.map(lambda geometry: geometry.wkb) #(lamba geometory:geometory.wkb)：建物ポリゴンをWKB(Well-Known-Binary)形式に変換
    joined["geometry"] = joined["index_right"].map(polygon_wkb) #index_rightとpolygon_wkbのインデックスの突き合わせがうまくいくのは、両方のデータとも同じbuilding_gdfのインデックスを参照しているから

    result = joined.drop( #.drop(コラム)：コラムをデータから削除
        columns=["index_right", "_row_id"]
    ).reset_index(drop=True) 

    result["housename"] = result["housename"].astype("string") #文字列
    result["n_names"] = result["n_names"].astype("Int64") #数字
    result["building_overlap"] = result["building_overlap"].astype("boolean") #boolean：True/False以外にNanがあってもエラーにならない型
    result["building_match_type"] = result["building_match_type"].astype("string")
    result["nearest_distance_m"] = pd.to_numeric(
        result["nearest_distance_m"], errors="raise" #errors = "raise"：NaNがあればコードを止める
    )

    print(f"    建物割当成功: {result['housename'].notna().sum():,} / {len(result):,}")

    return result

def write_parquet_batch(df, writer, output_path):
    """同一スキーマを保って滞在DataFrameをParquetに追記する。

    引数: df は書き込み対象、writer は既存ParquetWriterまたはNone、
        output_path は出力先。
    戻り値: 継続使用するParquetWriter。
    条件: 初回の非空データで列と型を確定する。safe=True。
    """
    if df.empty:
        return writer
    if writer is None:
        table = pa.Table.from_pandas(df, preserve_index=False) #pandasのデータフレームをPyArrowのTableに変更 #preserve_index = False：dfのindexは保存しない
        writer = pq.ParquetWriter(output_path , table.schema, compression=PARQUET_COMPRESSION) #pq.ParquetWriter：parquetファイルへの書き込み専用のトンネルを作成
        #①output_path：どこで、②table.schema(schema：列名とデータ型を取得)：どのような形式で、③compression(snappy：圧縮率そこそこ、処理スピード早い)：どのように圧縮し、保存するか
    else:
        df = df.copy()  # 呼び出し元のDataFrameは変更しない
        for col in writer.schema.names: #一度目のループで作成した、列名のリストを使う
            if col not in df.columns: #一度目ループでのコラムがなかったら、
                df[col] = pd.NA # NaNを入れる
        table = pa.Table.from_pandas(
            df[writer.schema.names], schema=writer.schema, preserve_index=False, safe=True,
        )
    writer.write_table(table)
    return writer


def process_region(activity_df, region_label, config, buildings, region_geometry,
                   writers, totals, matched_counts, date):
    """1日分のactivityから1地域分の建物付与・保存・集計を行う。

    引数: activity_df はactivityの滞在、region_label/config は地域の設定、
        buildings/region_geometry は建物と5km圏、writers/totals/各countsは更新対象、
        date は入力ファイル名由来の日付文字列。
    戻り値: なし。各辞書・配列を更新する。
    条件: 開始地点と終了地点の両方が地域内の滞在のみ処理する。
    """
    print(f"\n地域: {region_label}") #\n：改行
    region_df = extract_inside_region(activity_df, buildings.crs, region_geometry) # activity_dfの滞在の開始、終了地点が両方とも地域内に存在
    print(f"    地域内滞在: {len(region_df):,}")
    if region_df.empty:
        return
    result = assign_building(region_df, buildings) #建物情報を付与
    counts = result["building_match_type"].value_counts()

    for key in MATCH_TYPES:
        matched_counts[region_label][key] += counts.get(key, 0)
    result["date"] = date
    writers[region_label] = write_parquet_batch(result, writers[region_label], config["output"])
    totals[region_label] += len(result)


def main():
    """全GPS日別ファイルについて西条・広島の建物割当を実行する。

    引数: なし。入力パス等は冒頭の設定を使用。
    戻り値: 戻り値: なし。地域別Parquetを作成する。
    条件: 入力が存在すること。読込失敗ファイルは元コード同様スキップする。
    """
    if not INPUT_DIR.is_dir():
        raise FileNotFoundError(f"入力フォルダがありません: {INPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True) #parents = True：親フォルダも作成 exist_ok = True：既存フォルダがあっても大丈夫
    region_data = {
        label: load_buildings(config["shp"], config["buffer"], label)
        for label, config in REGIONS.items() #.items()：Pythonの辞書データからキー(key)と値(value)を取り出す。ex)key:西条_5km,value：西条のshpとbuffer
    }
    parquet_files = sorted(
        path for path in INPUT_DIR.glob(INPUT_PATTERN) #INPUT_DIR内のINPUT_PATTERNを探す
        if not path.name.startswith("._") #.startswith("._")：._で始まるマック特有のファイルを読み込まない
    )
    if not parquet_files:
        raise FileNotFoundError(f"GPSデータがありません: {INPUT_DIR}")
    print(f"\nGPSデータ処理開始 / 対象ファイル数: {len(parquet_files):,}")
    for config in REGIONS.values():
        if config["output"].exists():
            print(f"既存ファイルを上書き: {config['output']}")
            config["output"].unlink() #.unlink()：既存ファイルを削除
    writers = {label: None for label in REGIONS}
    # writers = {
    # "西条_5km": None,
    # "広島_5km": None
    # }と同じ
    totals = {label: 0 for label in REGIONS}
   
    matched_counts = {
        label: {key: 0 for key in MATCH_TYPES} for label in REGIONS
    }
    # matched_counts = {
    # "西条_5km": {
    #     "within": 0,
    #     "nearest": 0
    # },
    # "広島_5km": {
    #     "within": 0,
    #     "nearest": 0
    # }}と同じ

    skipped_files = []
    try:
        for file_no, parquet_path in enumerate(parquet_files, start=1): #enemerate()：file_no:1, parequet_path：trips_20230801.parquet、、、
            print(f"\n[{file_no}/{len(parquet_files)}] {parquet_path.name}")
            try:
                df = pd.read_parquet(parquet_path, columns=REQUIRED_COLUMNS) #colums =REQUIRED_COLUMNS：REQUIRED_COLUMNSだけ読み込む
            except Exception as exc: #Exception as exc：直前行でエラーが起こると発生
                print(f"読み込み失敗: {exc}") #起こったエラー(exc)が書き込まれる
                skipped_files.append(parquet_path.name)
                continue
            print(f"全データ: {len(df):,}")
            activity_df = prepare_activity(df)
            print(f"activity: {len(activity_df):,}")
            if activity_df.empty:
                continue
            date = parquet_path.stem.removeprefix("trips_") #parquet_path.stem = trips_20230801, parquet_path.stem.removeprefix = 20230801 
            for label, config in REGIONS.items():
                buildings, region_geometry = region_data[label]
                process_region(
                    activity_df, label, config, buildings, region_geometry,
                    writers, totals, matched_counts, date,
                )
    finally:
        for writer in writers.values():
            if writer is not None:
                writer.close()
    print("\n全日処理完了")
    for label, config in REGIONS.items():
        print(f"{label}: {totals[label]:,}件 / 出力: {config['output']}")

        for match_type, count in matched_counts[label].items():
            print(f"  {match_type}: {count:,}件")

        if writers[label] is None:
            print(f"  注意: 対象滞在0件のためParquetは作成されません: {label}")
    if skipped_files:
        print(f"注意: 読み込みに失敗したファイル {len(skipped_files)}件: {skipped_files}")


if __name__ == "__main__":
    main()
