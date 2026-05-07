"""
GI Status 路由
"""
from fastapi import APIRouter, HTTPException
from core import get_db_connection, get_config

router = APIRouter()


@router.get("/gi_status")
def query_gi_status():
    """查询GI发货状态 - 同原 GI_status() 函数"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cfg = get_config()
        sqls = cfg['sql_queries']['gi_status']

        # 1. 查询 STSCODE 汇总
        cur.execute(sqls['summary'])
        summary = [
            {"STSCODE": str(r[0]).strip() if r[0] else '', "FLOW_TYPE": str(r[1]).strip() if r[1] else '',
             "CARTONS": int(r[2]) if r[2] else 0}
            for r in cur.fetchall()
        ]

        # 2. GI 状态
        cur.execute(sqls['gi_status'])
        gi_status = [
            {"SHGISFLG": str(r[0]).strip() if r[0] else '', "COUNT": int(r[1]) if r[1] else 0}
            for r in cur.fetchall()
        ]

        # 3. GI ERRORS
        cur.execute(sqls['errors'])
        errors = [
            {"DATE": str(r[0]) if r[0] else '', "TIME": str(r[1]) if r[1] else '',
             "LNK": str(r[2]).strip() if r[2] else '', "MSG": str(r[3]).strip() if r[3] else ''}
            for r in cur.fetchall()
        ]

        # 4. 最大CMR时间
        cur.execute(sqls['max_cmr_time'])
        max_cmr = cur.fetchone()[0]
        max_cmr_str = f"{str(max_cmr)[:2]}:{str(max_cmr)[2:4]}:{str(max_cmr)[4:6]}" if max_cmr else None

        # 5. 今日量
        cur.execute(sqls['today_volume'])
        tv = cur.fetchone()
        today_volume = {
            "units": int(tv[0]) if tv and tv[0] else 0,
            "cartons": int(tv[1]) if tv and tv[1] else 0,
            "dns": int(tv[2]) if tv and tv[2] else 0,
            "pls": int(tv[3]) if tv and tv[3] else 0,
        }

        # 6. 最大GI时间
        cur.execute(sqls['max_gi_time'])
        max_gi = cur.fetchone()[0]
        max_gi_str = f"{str(max_gi)[:2]}:{str(max_gi)[2:4]}:{str(max_gi)[4:6]}" if max_gi else None

        conn.close()

        # 判断GI是否完成
        stscodes = {r['STSCODE'] for r in summary}
        pl_flags = {r['SHGISFLG'] for r in gi_status}
        gi_done = stscodes.issubset({'160', '090'}) and pl_flags.issubset({'Y'}) and len(errors) == 0

        # 如果GI完成并且 CMR < GI，显示结束状态
        cmr_done = False
        if max_cmr and max_gi:
            cmr_done = max_cmr < max_gi

        return {
            "gi_done": gi_done,
            "cmr_done": cmr_done,
            "summary": summary,
            "gi_status": gi_status,
            "errors": errors,
            "max_cmr_time": max_cmr_str,
            "max_gi_time": max_gi_str,
            "today_volume": today_volume,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
