"""
Label History 路由 - 查历史库位/标签
"""
import os
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from core import get_db_connection, get_config, rows_to_dicts, clean_dataframe_data
import tempfile

router = APIRouter()

# 查询类型到SQL key的映射
QUERY_MAP = {
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


@router.get("/label_history/query_types")
def get_query_types():
    """返回可用的查询类型列表"""
    return list(QUERY_MAP.keys()) + ["Export inventory"]


@router.post("/label_history/query")
def query_label_history(
    carton_numbers: list[str] = Query(..., description="箱号列表"),
    query_type: str = Query("default_location", description="查询类型"),
):
    """
    查询标签历史 - 对一个或多个箱号执行查询
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cfg = get_config()
        label_sqls = cfg['sql_queries']['label_history']

        all_results = []
        fields = []

        for carton in carton_numbers:
            carton = carton.strip()
            if not carton:
                continue

            if query_type == "Export inventory":
                # 特殊处理: 导出库存, 不做分页
                params = {'CARTON_PLAN': carton}
                queries = ['export_inventory_q1', 'export_inventory_q2',
                           'export_inventory_q3', 'export_inventory_q4']
                inventory_data = []
                for qk in queries:
                    sql = label_sqls[qk].format(**params)
                    cur.execute(sql)
                    rows = cur.fetchall()
                    fds = [f[0] for f in cur.description]
                    inventory_data.append({
                        "sql_key": qk,
                        "fields": fds,
                        "rows": rows_to_dicts(rows, fds)
                    })
                conn.close()
                return {
                    "type": "inventory_export",
                    "carton": carton,
                    "data": inventory_data
                }
            else:
                sql_key = QUERY_MAP.get(query_type, "default_location")
                sql = label_sqls[sql_key].replace('CARTON_PLAN', carton)
                cur.execute(sql)
                rows = cur.fetchall()
                if rows and not fields:
                    fields = [f[0] for f in cur.description]
                all_results.extend(rows_to_dicts(rows, [f[0] for f in cur.description]))

        conn.close()

        return {
            "type": "query_result",
            "query_type": query_type,
            "fields": fields,
            "rows": all_results,
            "total": len(all_results)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/label_history/export_excel")
def export_label_history_excel(
    carton_numbers: list[str] = Query(...),
    query_type: str = Query("default_location"),
):
    """导出查询结果为Excel文件"""
    try:
        result = query_label_history(carton_numbers, query_type)
        if not isinstance(result, dict):
            return result

        if result.get("type") == "inventory_export":
            # 使用xlsxwriter创建多sheet Excel
            import xlsxwriter
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            workbook = xlsxwriter.Workbook(tmp.name)
            center_format = workbook.add_format({'align': 'center', 'valign': 'vcenter'})

            for section in result["data"]:
                ws = workbook.add_worksheet(section["sql_key"][:31])
                if section["fields"]:
                    ws.write_row(0, 0, section["fields"], center_format)
                    for ri, row in enumerate(section["rows"]):
                        for ci, f in enumerate(section["fields"]):
                            ws.write(ri + 1, ci, row.get(f, ''), center_format)

            workbook.close()
            return FileResponse(tmp.name, filename=f"inventory_{result['carton']}.xlsx",
                                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        else:
            # 简单导出
            import pandas as pd
            df = clean_dataframe_data(result['rows'], result['fields'])
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            df.to_excel(tmp.name, index=False)
            return FileResponse(tmp.name, filename=f"label_history_{query_type}.xlsx",
                                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
