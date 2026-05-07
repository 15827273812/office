"""
PS Tool Desktop - 核心模块
配置加载、数据库连接、数据清洗
"""
import json
import os
import pathlib
import logging
import tempfile
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

SCRIPT_DIR = pathlib.Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR.parent / 'config.json'
if not CONFIG_PATH.exists():
    CONFIG_PATH = SCRIPT_DIR / 'config.json'  # 回退到同目录

def get_config():
    cfg_path = os.environ.get('PS_TOOL_CONFIG', str(CONFIG_PATH))
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # 尝试常见的其他位置
        alt_paths = [
            SCRIPT_DIR.parent / 'backend' / 'config.json',
            SCRIPT_DIR / 'config.json',
            pathlib.Path.home() / '.openclaw' / 'workspace' / 'temp_refactor' / 'review_check' / 'config.json',
        ]
        for p in alt_paths:
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
        raise

def get_db_connection():
    """创建数据库连接（自动选择可用驱动）"""
    import pyodbc
    cfg = get_config()
    conn_str = cfg['database']['connection_string']
    return pyodbc.connect(conn_str)

class DBManager:
    """数据库管理器"""
    
    def __init__(self, config_path=None):
        if config_path:
            os.environ['PS_TOOL_CONFIG'] = config_path
        self._cfg = None
    
    @property
    def cfg(self):
        if self._cfg is None:
            self._cfg = get_config()
        return self._cfg
    
    @property
    def sql_data(self):
        return self.cfg['sql_queries']
    
    def get_connection(self):
        return get_db_connection()
    
    def execute_query(self, sql, params=None):
        conn = self.get_connection()
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
    
    def rows_to_dicts(self, rows, fields):
        result = []
        for row in rows:
            d = {}
            for i, f in enumerate(fields):
                val = row[i]
                if isinstance(val, bytes):
                    try:
                        val = val.decode('cp037')
                    except:
                        val = val.decode('utf-8', errors='replace')
                elif isinstance(val, str):
                    val = val.strip()
                d[f] = val
            result.append(d)
        return result
    
    def clean_df(self, df):
        """清理DataFrame"""
        for col in df.select_dtypes(include='object').columns:
            if df[col].dtype == 'O':
                df[col] = df[col].astype(str).str.strip().str.replace(r'\s+', '', regex=True)
                df[col] = df[col].astype(str).str.replace('None', '', regex=True)
        return df

# GI Status
def query_gi_status(db: DBManager):
    """查询GI状态，返回结果字典"""
    sqls = db.sql_data['gi_status']
    conn = db.get_connection()
    cur = conn.cursor()
    
    try:
        # 1. STSCODE 汇总
        cur.execute(sqls['summary'])
        sum_fields = [f[0] for f in cur.description]
        summary = db.rows_to_dicts(cur.fetchall(), sum_fields)
        
        # 2. GI 状态
        cur.execute(sqls['gi_status'])
        gi_f = [f[0] for f in cur.description]
        gi_status = db.rows_to_dicts(cur.fetchall(), gi_f)
        
        # 3. GI Errors
        cur.execute(sqls['errors'])
        err_f = [f[0] for f in cur.description]
        errors = db.rows_to_dicts(cur.fetchall(), err_f)
        
        # 4. 最大CMR时间
        cur.execute(sqls['max_cmr_time'])
        max_cmr = cur.fetchone()[0]
        max_cmr_str = f"{str(max_cmr)[:2]}:{str(max_cmr)[2:4]}:{str(max_cmr)[4:6]}" if max_cmr else 'N/A'
        
        # 5. 今日量
        cur.execute(sqls['today_volume'])
        tv = cur.fetchone()
        today_volume = {
            'units': int(tv[0]) if tv and tv[0] else 0,
            'cartons': int(tv[1]) if tv and tv[1] else 0,
            'dns': int(tv[2]) if tv and tv[2] else 0,
            'pls': int(tv[3]) if tv and tv[3] else 0,
        }
        
        # 6. 最大GI时间
        cur.execute(sqls['max_gi_time'])
        max_gi = cur.fetchone()[0]
        max_gi_str = f"{str(max_gi)[:2]}:{str(max_gi)[2:4]}:{str(max_gi)[4:6]}" if max_gi else 'N/A'
        
        # 判断
        stscodes = {r['STSCODE'] for r in summary}
        pl_flags = {r['SHGISFLG'] for r in gi_status}
        gi_done = stscodes.issubset({'160', '090'}) and pl_flags.issubset({'Y'}) and len(errors) == 0
        cmr_done = False
        if max_crom := max_cmr:
            if max_gi:
                cmr_done = str(max_cmr) < str(max_gi)
        
        return {
            'summary': summary,
            'gi_status': gi_status,
            'errors': errors,
            'max_cmr_time': max_cmr_str,
            'max_gi_time': max_gi_str,
            'today_volume': today_volume,
            'gi_done': gi_done,
            'cmr_done': cmr_done,
        }
    finally:
        cur.close()
        conn.close()

# 数据导出查询
def query_export_data(db: DBManager, num_conditions, alpha_conditions):
    """执行数据导出查询，返回结果列表（每个结果对应一个SQL匹配）"""
    sqls = db.sql_data['export_data']
    results = []
    
    def try_sql(sql_key, params, prefix):
        sql = sqls[sql_key].replace('{placeholders}', ', '.join(['?'] * len(params)))
        rows, fields = db.execute_query(sql, params)
        if rows:
            return {'rows': db.rows_to_dicts(rows, fields), 'fields': fields, 'file_prefix': prefix}
        return None
    
    if num_conditions:
        first = num_conditions[0]
        placeholders = ', '.join(['?'] * len(num_conditions))
        
        if len(first) <= 4:
            # 短条件 - 依次尝试 3 个SQL，每个都有数据则全部返回
            for sql_key, prefix in [
                ('ap_shipping', 'AP_Shipping'),
                ('fw_shipping', 'FW_Shipping'),
                ('replenishment', 'Replenishment'),
            ]:
                sql = sqls[sql_key].replace('{placeholders}', placeholders)
                rows, fields = db.execute_query(sql, num_conditions)
                if rows:
                    results.append({'rows': db.rows_to_dicts(rows, fields), 'fields': fields, 'file_prefix': prefix})
            return results
        
        # 长条件
        ten_digit = [c for c in num_conditions if len(c) == 10]
        six_digit = [c for c in num_conditions if len(c) == 6]
        
        if ten_digit and not six_digit:
            for key, pref in [('shipment_info','Shipment_info'), ('plan_info_by_por','plan_info'), ('delay_info','Delay_info')]:
                r = try_sql(key, ten_digit, pref)
                if r:
                    results.append(r)
                    break  # 找到第一个有数据的就返回
            return results
            
        if six_digit and not ten_digit:
            r = try_sql('plan_info_by_ibrc', six_digit, 'plan_info')
            if r: results.append(r)
            return results
            
        if six_digit and ten_digit:
            ph6 = ', '.join(['?'] * len(six_digit))
            ph10 = ', '.join(['?'] * len(ten_digit))
            sql = sqls['plan_info_by_both'].replace('{placeholders_10}', ph10).replace('{placeholders_6}', ph6)
            rows, fields = db.execute_query(sql, ten_digit + six_digit)
            if rows:
                results.append({'rows': db.rows_to_dicts(rows, fields), 'fields': fields, 'file_prefix': 'plan_info'})
            return results
        
        if len(first) == 8:
            sql = sqls['packlist_info'].replace('{placeholders}', placeholders)
            rows, fields = db.execute_query(sql, num_conditions)
            if rows:
                results.append({'rows': db.rows_to_dicts(rows, fields), 'fields': fields, 'file_prefix': 'Packlist_info'})
            return results
        
        if len(first) == 20:
            for key, pref in [('fs_info','FS_info'), ('trailer_info','trailer_info')]:
                sql = sqls[key].replace('{placeholders}', placeholders)
                rows, fields = db.execute_query(sql, num_conditions)
                if rows:
                    results.append({'rows': db.rows_to_dicts(rows, fields), 'fields': fields, 'file_prefix': pref})
                    break
            return results
    
    if alpha_conditions:
        first = alpha_conditions[0]
        ph = ', '.join(['?'] * len(alpha_conditions))
        
        if len(first) == 10:
            sql = sqls['data_by_sku'].replace('{placeholders}', ph)
        elif len(first) == 9:
            sql = sqls['trailer_info_by_csn'].replace('{placeholders}', ph)
        else:
            sql = sqls['inventory_by_sku'].replace('{placeholders}', ph)
        
        rows, fields = db.execute_query(sql, alpha_conditions)
        if rows:
            results.append({'rows': db.rows_to_dicts(rows, fields), 'fields': fields, 'file_prefix': 'Alpha_Query' if len(alpha_conditions[0]) in (9,10) else 'Inventory'})
        return results
    
    return results

# 标签历史查询
def query_label_history(db: DBManager, carton_numbers, query_type):
    """查询标签历史"""
    sqls = db.sql_data['label_history']
    
    LH_MAP = {
        "查询打印记录": "print_record",
        "CHECK OPEN WORK": "check_open_work",
        "CHECK AUDIT WORK": "check_audit_work",
        "检查SKU是否是AMINUS": "check_sku_aminus",
        "QA解锁?": "qa_unlock",
        "SO查询": "so_query",
        "NFC": "nfc",
        "查询包装信息": "pack_info",
        "RSO": "rso",
        "查询历史库位": "history_location",
        "DP_area_info": "dp_area_info",
    }
    
    all_rows = []
    fields = []
    
    if query_type == "Export inventory":
        # 特殊导出: 4个sheet
        inventory_data = []
        for qk in ['export_inventory_q1', 'export_inventory_q2', 'export_inventory_q3', 'export_inventory_q4']:
            sql = sqls[qk].replace('CARTON_PLAN', carton_numbers[0])
            rows, fields = db.execute_query(sql)
            inventory_data.append({
                'sheet_name': qk,
                'fields': fields,
                'rows': db.rows_to_dicts(rows, fields),
            })
        return {'type': 'inventory_export', 'carton': carton_numbers[0], 'data': inventory_data}
    
    sql_key = LH_MAP.get(query_type, 'default_location')
    for carton in carton_numbers:
        sql = sqls[sql_key].replace('CARTON_PLAN', carton)
        rows, new_fields = db.execute_query(sql)
        if rows and not fields:
            fields = new_fields
        all_rows.extend(db.rows_to_dicts(rows, new_fields))
    
    return {'type': 'query_result', 'query_type': query_type, 'fields': fields, 'rows': all_rows, 'total': len(all_rows)}

# 日期查询
DATE_QUERY_MAP = {
    "Sorter(VNA来货)": ("sorter_vna", "Sorter"),
    "Final-Sorter(发货)": ("final_sorter", "Final-Sorter"),
    "DP & PROMO & NSRT区域补货": ("dp_promo_nsrt_replenish", "DP_PROMO_NSRT_补货"),
    "DP & PROMO & NSRT区域发货": ("dp_promo_nsrt_shipping", "DP_PROMO_NSRT_发货"),
    "异常tote": ("abnormal_tote", "异常tote"),
    "发货箱型数量(9种)": ("shipping_box_types", "发货箱型"),
    "收货人效": ("receiving_efficiency", "收货人效"),
    "生产信息": ("production_info", "生产信息"),
    "Cycle count data": ("cycle_count_data", "Cycle_count"),
    "Packlist_check": ("packlist_check", "Packlist_check"),
    "Picking": ("picking", "Picking"),
    "Replenishment": ("replenishment_qty", "Replenishment"),
    "FM": ("fm", "FM"),
    "GR": ("gr", "GR"),
    "Pre_SKU_info": ("pre_sku_info", "Pre_SKU_info"),
    "FW_Conveyor_info": ("fw_conveyor_info", "FW_Conveyor_info"),
    "AP_Conveyor_info": ("ap_conveyor_info", "AP_Conveyor_info"),
    "Hopper_info": ("hopper_info", "Hopper_info"),
    "Staging_info": ("staging_info", "Staging_info"),
    "FM_inventory": ("fm_inventory", "FM_inventory"),
    "Oversize_inventory": ("oversize_inventory", "Oversize_inventory"),
}

def query_date_range(db: DBManager, query_type, start_date=None, end_date=None):
    """按日期范围查询"""
    key, prefix = DATE_QUERY_MAP[query_type]
    sql = db.sql_data['date_query'][key]
    
    conn = db.get_connection()
    cur = conn.cursor()
    if start_date and end_date:
        cur.execute(sql, (start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date,
                          end_date.isoformat() if hasattr(end_date, 'isoformat') else end_date))
    else:
        cur.execute(sql)
    fields = [f[0] for f in cur.description]
    rows = db.rows_to_dicts(cur.fetchall(), fields)
    cur.close()
    conn.close()
    
    return {'fields': fields, 'rows': rows, 'total': len(rows), 'file_prefix': prefix}

# Excel导出
def export_to_excel(rows, fields, filename):
    """导出数据到Excel临时文件"""
    if not rows:
        return None
    
    df = pd.DataFrame(rows, columns=fields) if isinstance(rows[0], dict) else pd.DataFrame(rows)
    # 清理
    for col in df.select_dtypes(include='object').columns:
        if df[col].dtype == 'O':
            df[col] = df[col].astype(str).str.strip().str.replace(r'\s+', '', regex=True)
            df[col] = df[col].astype(str).str.replace('None', '', regex=True)
    
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    df.to_excel(tmp.name, index=False)
    return tmp.name

def export_inventory_to_excel(data, filename):
    """导出库存Excel（多sheet）"""
    import xlsxwriter
    
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    workbook = xlsxwriter.Workbook(tmp.name)
    cf = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
    
    for section in data:
        ws = workbook.add_worksheet(section['sheet_name'][:31])
        if section['fields']:
            ws.write_row(0, 0, section['fields'], cf)
            for ri, row in enumerate(section['rows']):
                for ci, f in enumerate(section['fields']):
                    ws.write(ri + 1, ci, row.get(f, ''), cf)
    
    workbook.close()
    return tmp.name
