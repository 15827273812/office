"""
核心模块：配置加载、数据库连接管理
"""
import json
import os
import pathlib

# 延迟导入 pyodbc，避免缺少系统依赖时无法加载配置
# import pyodbc -> 在具体函数中导入

BACKEND_DIR = pathlib.Path(__file__).parent.absolute()
PROJECT_ROOT = BACKEND_DIR.parent
CONFIG_PATH = PROJECT_ROOT / 'config.json'


def load_config():
    """加载配置文件"""
    if not CONFIG_PATH.exists():
        alt = BACKEND_DIR / 'config.json'
        if alt.exists():
            return json.loads(alt.read_text(encoding='utf-8'))
        raise FileNotFoundError(f"config.json not found at: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


_config = None


def get_config():
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_db_connection():
    """创建一个新的数据库连接"""
    import pyodbc
    cfg = get_config()
    conn_str = cfg['database']['connection_string']
    return pyodbc.connect(conn_str)


def execute_query(sql, params=None):
    """执行SQL并返回结果"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        rows = cur.fetchall()
        fields = [f[0] for f in cur.description] if cur.description else []
        return rows, fields
    finally:
        conn.close()


def clean_dataframe_data(rows, fields):
    """清理数据：bytes转字符串、去空格、去None"""
    import pandas as pd
    df = pd.DataFrame(rows, columns=fields)
    for col in df.select_dtypes(include='object').columns:
        if df[col].dtype == 'O':
            df[col] = df[col].astype(str).str.strip().str.replace(r'\s+', '', regex=True)
            df[col] = df[col].astype(str).str.replace('None', '', regex=True)
    return df


def rows_to_dicts(rows, fields):
    """将查询结果转为字典列表 (bytes自动转string)"""
    result = []
    for row in rows:
        d = {}
        for i, f in enumerate(fields):
            val = row[i]
            if isinstance(val, bytes):
                try:
                    val = val.decode('cp037')
                except Exception:
                    val = val.decode('utf-8', errors='replace')
            elif isinstance(val, str):
                val = val.strip()
            d[f] = val
        result.append(d)
    return result
