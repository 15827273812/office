"""
Date Query 路由 - 按日期查询
"""
import tempfile
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from core import get_db_connection, get_config, rows_to_dicts

router = APIRouter()

# 查询类型 -> (config_key, file_prefix) 映射
QUERY_MAP = {
    "Sorter(VNA来货)": ("sorter_vna", "Sorter"),
    "Final-Sorter(发货)": ("final_sorter", "Final-Sorter"),
    "DP & PROMO & NSRT区域补货": ("dp_promo_nsrt_replenish", "DP & PROMO & NSRT区域补货"),
    "DP & PROMO & NSRT区域发货": ("dp_promo_nsrt_shipping", "DP & PROMO & NSRT区域发货"),
    "异常tote": ("abnormal_tote", "异常tote"),
    "发货箱型数量(9种)": ("shipping_box_types", "发货箱型数量"),
    "收货人效": ("receiving_efficiency", "收货人效"),
    "生产信息": ("production_info", "生产信息"),
    "Cycle count data": ("cycle_count_data", "Cycle count data"),
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


@router.get("/date_query/query_types")
def get_date_query_types():
    """返回可用的查询类型列表"""
    return list(QUERY_MAP.keys())


@router.get("/date_query/query")
def query_date_range(
    query_type: str = Query(..., description="查询类型"),
    start_date: str = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """
    按日期范围查询数据
    """
    try:
        if query_type not in QUERY_MAP:
            raise HTTPException(status_code=400, detail=f"未知查询类型: {query_type}")

        config_key, file_prefix = QUERY_MAP[query_type]
        cfg = get_config()
        sql = cfg['sql_queries']['date_query'][config_key]

        conn = get_db_connection()
        cur = conn.cursor()

        if start_date and end_date:
            cur.execute(sql, (start_date, end_date))
        else:
            cur.execute(sql)

        rows = cur.fetchall()
        fields = [f[0] for f in cur.description]
        conn.close()

        return {
            "fields": fields,
            "rows": rows_to_dicts(rows, fields),
            "total": len(rows),
            "file_prefix": file_prefix
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/date_query/export_excel")
def export_date_query_excel(
    query_type: str = Query(...),
    start_date: str = Query(None),
    end_date: str = Query(None),
):
    """导出日期查询结果为Excel"""
    try:
        result = query_date_range(query_type, start_date, end_date)
        if isinstance(result, dict) and result.get("rows"):
            import pandas as pd
            df = pd.DataFrame(result['rows'])
            for col in df.select_dtypes(include='object').columns:
                if df[col].dtype == 'O':
                    df[col] = df[col].astype(str).str.strip().str.replace(r'\s+', '', regex=True)
                    df[col] = df[col].astype(str).str.replace('None', '', regex=True)

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            df.to_excel(tmp.name, index=False)
            prefix = result.get('file_prefix', 'query')
            return FileResponse(tmp.name, filename=f"{prefix}.xlsx",
                                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        return {"error": "no_data", "message": "没有数据可导出"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
