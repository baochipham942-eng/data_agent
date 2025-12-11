import sqlite3
from pathlib import Path

import pandas as pd

from app.config import DATA_DB_PATH, PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DB_PATH

FILES = {
    "gio_event": DATA_DIR / "gio_event.csv",
    "dealer_store_info": DATA_DIR / "dealer_store_info.csv",
    "data_source": DATA_DIR / "data_source.csv",
    "event_dic": DATA_DIR / "event_dic.csv",
    "page_dic": DATA_DIR / "page_dic.csv",
}

# SQLite 的表结构（把 MySQL 类型转换成 SQLite 类型）
TABLE_SCHEMAS = {
    "gio_event": """
        CREATE TABLE IF NOT EXISTS gio_event (
            event_key TEXT,
            event_time TEXT,
            client_time TEXT,
            gio_id TEXT,
            user_key TEXT,
            session TEXT,
            region TEXT,
            city TEXT,
            channel TEXT,
            data_source_id TEXT,
            omp_attr_store_id TEXT,
            omp_attr_action_name TEXT,
            omp_attr_category TEXT,
            omp_attr_channel TEXT,
            event_duration TEXT,
            omp_attr_session TEXT,
            omp_attr_module_name TEXT,
            omp_attr_page_path TEXT,
            omp_attr_model_code TEXT,
            omp_attr_model_year TEXT,
            omp_attr_flag TEXT,
            dt TEXT,
            omp_attr_vin TEXT,
            omp_attr_sales_id TEXT
        )
    """,

    "dealer_store_info": """
        CREATE TABLE IF NOT EXISTS dealer_store_info (
            dealer_store_id TEXT PRIMARY KEY,
            province TEXT,
            city TEXT,
            dealer_group_name TEXT
        )
    """,

    "data_source": """
        CREATE TABLE IF NOT EXISTS data_source (
            data_source_id TEXT PRIMARY KEY,
            name TEXT
        )
    """,

    "event_dic": """
        CREATE TABLE IF NOT EXISTS event_dic (
            event_key TEXT PRIMARY KEY,
            comment TEXT
        )
    """,

    "page_dic": """
        CREATE TABLE IF NOT EXISTS page_dic (
            page_name TEXT PRIMARY KEY,
            name TEXT,
            feature TEXT,
            page_first_category TEXT,
            page_second_category TEXT
        )
    """
}


def import_to_sqlite():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    # 创建表
    for table, schema in TABLE_SCHEMAS.items():
        print(f"Creating table: {table}...")
        conn.execute(schema)

    # 导入 CSV
    for table, filename in FILES.items():
        print(f"\n📥 Importing {filename} → {table} ...")

        try:
            df = pd.read_csv(filename)
            df.to_sql(table, conn, if_exists="replace", index=False)
            print(f"✅ 导入成功：{len(df)} 行")
        except Exception as e:
            print(f"❌ 导入失败：{table}: {e}")

    conn.commit()
    conn.close()
    print("\n🎉 数据全部导入完成！")


if __name__ == "__main__":
    import_to_sqlite()
