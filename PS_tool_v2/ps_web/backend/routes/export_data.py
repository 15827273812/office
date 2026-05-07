"""
Export Data 路由 - Receiving 数据导出
"""
import tempfile
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from core import get_db_connection, get_config, rows_to_dicts, clean_dataframe_data
import os

router = APIRouter()


@router.post("/export_data/query")
def export_data_query(
    conditions: list[str] = Query(..., description="输入条件列表"),
    condition_type: str = Query("num", description="条件类型: num(数字) / alpha(字母)"),
):
    """
    查询并导出数据 - 根据条件长度自动判断SQL类型
    原 export_data() 函数逻辑
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cfg = get_config()
        sqls = cfg['sql_queries']['export_data']

        results = []
        fields = []
        file_prefix = "data"

        if condition_type == "num" and conditions:
            conditions = [c.strip() for c in conditions if c.strip()]

            if conditions and len(conditions[0]) <= 4:
                # 短条件 - shipping 类查询
                placeholders = ', '.join(['?'] * len(conditions))
                sql = sqls['ap_shipping'].replace('{placeholders}', placeholders)
                cur.execute(sql, conditions)
                rows = cur.fetchall()
                fields = [f[0] for f in cur.description]
                results = rows_to_dicts(rows, fields)
                file_prefix = "AP_Shipping"

                if not results:
                    sql = sqls['fw_shipping'].replace('{placeholders}', placeholders)
                    cur.execute(sql, conditions)
                    rows = cur.fetchall()
                    fields = [f[0] for f in cur.description]
                    results = rows_to_dicts(rows, fields)
                    file_prefix = "FW_Shipping"

                if not results:
                    sql = sqls['replenishment'].replace('{placeholders}', placeholders)
                    cur.execute(sql, conditions)
                    rows = cur.fetchall()
                    fields = [f[0] for f in cur.description]
                    results = rows_to_dicts(rows, fields)
                    file_prefix = "Replenishment"

            elif conditions:
                # 长条件分类处理
                ten_digit = [c for c in conditions if len(c) == 10]
                six_digit = [c for c in conditions if len(c) == 6]

                if ten_digit and not six_digit:
                    placeholders_10 = ', '.join(['?'] * len(ten_digit))
                    sql = sqls['shipment_info'].replace('{placeholders}', placeholders_10)
                    cur.execute(sql, ten_digit)
                    rows = cur.fetchall()
                    fields = [f[0] for f in cur.description]
                    results = rows_to_dicts(rows, fields)
                    file_prefix = "Shipment_Info"

                    if not results:
                        sql = sqls['plan_info_by_por'].replace('{placeholders}', placeholders_10)
                        cur.execute(sql, ten_digit)
                        rows = cur.fetchall()
                        fields = [f[0] for f in cur.description]
                        results = rows_to_dicts(rows, fields)
                        file_prefix = "Plan_By_POR"

                if not results and six_digit and not ten_digit:
                    placeholders_6 = ', '.join(['?'] * len(six_digit))
                    sql = sqls['plan_info_by_ibrc'].replace('{placeholders}', placeholders_6)
                    cur.execute(sql, six_digit)
                    rows = cur.fetchall()
                    fields = [f[0] for f in cur.description]
                    results = rows_to_dicts(rows, fields)
                    file_prefix = "Plan_By_IBRC"

                if not results and six_digit and ten_digit:
                    placeholders_10 = ', '.join(['?'] * len(ten_digit))
                    placeholders_6 = ', '.join(['?'] * len(six_digit))
                    sql = sqls['plan_info_by_both']
                    sql = sql.replace('{placeholders_10}', placeholders_10)
                    sql = sql.replace('{placeholders_6}', placeholders_6)
                    cur.execute(sql, ten_digit + six_digit)
                    rows = cur.fetchall()
                    fields = [f[0] for f in cur.description]
                    results = rows_to_dicts(rows, fields)
                    file_prefix = "Plan_By_Both"

                if not results and conditions:
                    first = conditions[0]
                    if len(first) == 8:
                        placeholders = ', '.join(['?'] * len(conditions))
                        sql = sqls['packlist_info'].replace('{placeholders}', placeholders)
                        cur.execute(sql, conditions)
                        rows = cur.fetchall()
                        fields = [f[0] for f in cur.description]
                        results = rows_to_dicts(rows, fields)
                        file_prefix = "Packlist"
                    elif len(first) == 20:
                        placeholders = ', '.join(['?'] * len(conditions))
                        sql = sqls['fs_info'].replace('{placeholders}', placeholders)
                        cur.execute(sql, conditions)
                        rows = cur.fetchall()
                        fields = [f[0] for f in cur.description]
                        results = rows_to_dicts(rows, fields)
                        file_prefix = "FS"

                if not results:
                    first = conditions[0]
                    if len(first) != 4:
                        placeholders = ', '.join(['?'] * len(conditions))
                        sql = sqls['trailer_info'].replace('{placeholders}', placeholders)
                        cur.execute(sql, conditions)
                        rows = cur.fetchall()
                        fields = [f[0] for f in cur.description]
                        results = rows_to_dicts(rows, fields)
                        file_prefix = "Trailer"

                    if not results:
                        placeholders = ', '.join(['?'] * len(conditions))
                        sql = sqls['delay_info'].replace('{placeholders}', placeholders)
                        cur.execute(sql, conditions)
                        rows = cur.fetchall()
                        fields = [f[0] for f in cur.description]
                        results = rows_to_dicts(rows, fields)
                        file_prefix = "Delay"

        elif condition_type == "alpha" and conditions:
            conditions = [c.strip() for c in conditions if c.strip()]
            if not conditions:
                return {"fields": [], "rows": [], "total": 0, "file_prefix": "data"}

            first = conditions[0]
            if len(first) == 10:
                sql = sqls['data_by_sku']
            elif len(first) == 9:
                sql = sqls['trailer_info_by_csn']
            else:
                sql = sqls['inventory_by_sku']

            placeholders = ', '.join(['?'] * len(conditions))
            sql = sql.replace('{placeholders}', placeholders)
            cur.execute(sql, conditions)
            rows = cur.fetchall()
            fields = [f[0] for f in cur.description]
            results = rows_to_dicts(rows, fields)
            file_prefix = "Alpha_Query"

        conn.close()

        return {
            "fields": fields,
            "rows": results,
            "total": len(results),
            "file_prefix": file_prefix
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export_data/export_excel")
def export_data_excel(
    conditions: list[str] = Query(...),
    condition_type: str = Query("num"),
):
    """导出数据为Excel文件"""
    try:
        result = export_data_query(conditions, condition_type)
        if isinstance(result, dict) and result.get("rows"):
            import pandas as pd
            df = clean_dataframe_data(result['rows'], result['fields'])
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            df.to_excel(tmp.name, index=False)
            prefix = result.get('file_prefix', 'data')
            return FileResponse(tmp.name, filename=f"{prefix}.xlsx",
                                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        return {"error": "no_data", "message": "没有数据可以导出"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
