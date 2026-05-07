"""
PS Tool Desktop - Flet 桌面客户端
现代化仓储管理工具 - v2.0
"""
import flet as ft
import threading
import os
import sys
import tempfile
import pandas as pd
from datetime import datetime
from functools import partial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (
    DBManager, query_gi_status, query_export_data, query_label_history,
    query_date_range, DATE_QUERY_MAP, export_to_excel, export_inventory_to_excel,
    get_config
)

__version__ = "2.0.0"

# ==================== 主题色 ====================
COLORS = {
    "bg": "#1a1a2e",
    "bg_dark": "#16213e",
    "bg_card": "#1e293b",
    "accent": "#0ea5e9",
    "accent_light": "#38bdf8",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "purple": "#a855f7",
    "text": "#f1f5f9",
    "text_muted": "#94a3b8",
    "border": "#334155",
}


class PSToolApp:
    """PS Tool 应用主类 - 管理所有状态和UI"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.db = DBManager()
        self.loading = self._build_loading()
        self.content_container = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)
        self._export_data_cache = None
        self._label_data_cache = None
        self._date_data_cache = None
        self._build_ui()

    # ---------------------------------------------------------------
    #  工具方法
    # ---------------------------------------------------------------
    def _build_loading(self):
        return ft.Container(
            ft.Column([
                ft.ProgressRing(width=48, height=48, color=COLORS["accent"]),
                ft.Text("加载中...", color=COLORS["text_muted"], size=14),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
            alignment=ft.alignment.center,
            bgcolor=ft.Colors.with_opacity(0.7, COLORS["bg_dark"]),
            visible=False,
            expand=True,
        )

    def toast(self, msg, color=COLORS["success"]):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg, color=ft.Colors.WHITE), bgcolor=color, duration=3000)
        self.page.snack_bar.open = True
        self.page.update()

    def toast_error(self, msg):
        self.toast(str(msg), COLORS["error"])

    def run_db(self, fn, on_done):
        """在后台线程中运行数据库操作，完成时回调"""
        def wrapper():
            try:
                result = fn()
                # 线程安全更新
                self.page.schedule_update()
                on_done(result)
                self.loading.visible = False
                self.page.update()
            except Exception as e:
                self.page.schedule_update()
                self.loading.visible = False
                self.toast_error(str(e))
                self.page.update()

        self.loading.visible = True
        self.page.update()
        threading.Thread(target=wrapper, daemon=True).start()

    def _make_data_table(self, fields, rows, max_rows=50, height=500):
        """创建可滚动的数据表"""
        if not fields or not rows:
            return ft.Container(ft.Text("无数据", color=COLORS["text_muted"]), padding=20)
        
        cols = [ft.DataColumn(ft.Text(c[:20], size=11, weight=ft.FontWeight.BOLD, color=COLORS["accent"]))
                for c in fields]
        data_rows = []
        for r in rows[:max_rows]:
            cells = []
            for f in fields:
                val = str(r.get(f, ''))[:60]
                cells.append(ft.DataCell(ft.Text(val, size=11, color=COLORS["text"],
                                                selectable=True)))
            data_rows.append(ft.DataRow(cells))
        
        dt = ft.DataTable(
            columns=cols, rows=data_rows,
            bgcolor=COLORS["bg_card"],
            border=ft.border.all(1, COLORS["border"]),
            heading_row_color=COLORS["bg_dark"],
            column_spacing=16,
            data_row_max_height=30,
            heading_row_height=36,
        )
        
        extra = ""
        if len(rows) > max_rows:
            extra = f" (显示前 {max_rows} 条，共 {len(rows)} 条)"
        
        return ft.Column([
            ft.Text(f"共 {len(rows)} 条记录{extra}", size=12, color=COLORS["text_muted"]),
            ft.Container(dt, height=height),
        ], spacing=4)

    def _build_card(self, title, content, icon=None):
        """构建统一的卡片容器"""
        items = []
        if title:
            row = [ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=COLORS["text"])]
            if icon:
                row.insert(0, ft.Icon(icon, color=COLORS["accent"], size=18))
            items.append(ft.Row(row, spacing=8))
        if content:
            items.append(content)
        return ft.Container(
            ft.Column(items, spacing=8),
            padding=16, bgcolor=COLORS["bg_card"], border_radius=8,
            margin=ft.margin.only(bottom=8),
        )

    # ---------------------------------------------------------------
    #  GI Status 视图
    # ---------------------------------------------------------------
    def _build_gi_view(self):
        self.gi_result_view = ft.Column(visible=False, spacing=12)

        def on_query(e):
            self.run_db(
                lambda: query_gi_status(self.db),
                self._update_gi_result,
            )

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Row([
                        ft.Text("GI 状态监控", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                        ft.Container(expand=True),
                        ft.FilledButton(
                            "刷新 GI 状态",
                            icon=ft.Icons.REFRESH,
                            on_click=on_query,
                            style=ft.ButtonStyle(bgcolor=COLORS["accent"]),
                        ),
                    ]),
                    ft.Divider(color=COLORS["border"]),
                    self.gi_result_view,
                ], spacing=12),
                padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    def _update_gi_result(self, data):
        self.gi_result_view.visible = True
        self.gi_result_view.controls.clear()

        # 状态徽章
        done = data.get("gi_done", False)
        sc = COLORS["success"] if done else COLORS["error"]
        st = "GI 已完成 ✓" if done else "GI 未完成 ✗"
        self.gi_result_view.controls.append(
            ft.Container(
                ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE if done else ft.Icons.ERROR, color=sc, size=20),
                    ft.Text(st, size=16, weight=ft.FontWeight.BOLD, color=sc),
                ], spacing=8),
                padding=12, bgcolor=ft.Colors.with_opacity(0.1, sc), border_radius=8,
            )
        )

        # 纯 CMR/GI 时间 + 今日量卡片
        tv = data.get("today_volume", {})
        vol_cards = ft.ResponsiveRow([
            ft.Container(
                ft.Column([
                    ft.Text(str(tv.get(k, 0)), size=24, weight=ft.FontWeight.BOLD, color=c),
                    ft.Text(l, size=11, color=COLORS["text_muted"]),
                ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=12, bgcolor=COLORS["bg_card"], border_radius=8, col={"sm": 6, "md": 3},
            )
            for k, l, c in [
                ("units", "总数量", COLORS["accent"]),
                ("cartons", "箱数", COLORS["success"]),
                ("dns", "DN 数量", COLORS["warning"]),
                ("pls", "PL 数量", COLORS["purple"]),
            ]
        ], spacing=12)

        time_info = ft.Row([
            ft.Column([ft.Text("最后 CMR 时间", size=11, color=COLORS["text_muted"]),
                       ft.Text(str(data.get("max_cmr_time", "N/A")), size=16,
                               weight=ft.FontWeight.BOLD, color=COLORS["text"])]),
            ft.VerticalDivider(color=COLORS["border"]),
            ft.Column([ft.Text("最后 GI 时间", size=11, color=COLORS["text_muted"]),
                       ft.Text(str(data.get("max_gi_time", "N/A")), size=16,
                               weight=ft.FontWeight.BOLD, color=COLORS["text"])]),
        ], spacing=24)

        self.gi_result_view.controls.extend([
            self._build_card("今日量统计", vol_cards, ft.Icons.BAR_CHART),
            self._build_card("CMR / GI 时间", time_info, ft.Icons.ACCESS_TIME),
        ])

        # STSCODE 汇总
        if data.get("summary"):
            rows = [[r.get('STSCODE', ''), r.get('FLOW_TYPE', ''), str(r.get('QTY', 0))] for r in data['summary']]
            tbl = self._simple_table(["STSCODE", "流程类型", "箱数"], rows)
            self.gi_result_view.controls.append(self._build_card("STSCODE 汇总", tbl, ft.Icons.TABLE_CHART))

        # GI 状态统计
        if data.get("gi_status"):
            rows = [[r.get('SHGISFLG', ''), str(r.get('COUNT', 0))] for r in data['gi_status']]
            tbl = self._simple_table(["状态", "数量"], rows)
            self.gi_result_view.controls.append(self._build_card("GI 状态统计", tbl))

        # 错误记录
        if data.get("errors"):
            rows = [[r.get('ERRORDATE', ''), r.get('ERRORTIME', ''), r.get('LNK', ''), r.get('MSG', '')]
                    for r in data['errors']]
            tbl = self._simple_table(["日期", "时间", "LNK", "消息"], rows, err=True)
            self.gi_result_view.controls.append(self._build_card("GI 错误记录", tbl, ft.Icons.ERROR))

    def _simple_table(self, headers, rows, err=False):
        """简单表格辅助"""
        tc = COLORS["error"] if err else COLORS["accent"]
        cols = [ft.DataColumn(ft.Text(c, size=11, weight=ft.FontWeight.BOLD, color=tc)) for c in headers]
        dr = []
        for row in rows:
            cells = [ft.DataCell(ft.Text(str(cell), size=11, color=COLORS["text"])) for cell in row]
            dr.append(ft.DataRow(cells))
        return ft.DataTable(columns=cols, rows=dr, bgcolor=COLORS["bg_card"],
                            border=ft.border.all(1, COLORS["border"]),
                            heading_row_color=COLORS["bg_dark"],
                            heading_row_height=32, data_row_max_height=28)

    # ---------------------------------------------------------------
    #  数据导出视图
    # ---------------------------------------------------------------
    def _build_export_view(self):
        num_input = ft.TextField(
            label="数字条件（每行一个）", multiline=True, min_lines=4, max_lines=8,
            hint_text="计划号 / Shipment / Packlist / Run / 箱号\n每行一个",
            border_color=COLORS["border"], color=COLORS["text"],
            cursor_color=COLORS["accent"],
        )
        alpha_input = ft.TextField(
            label="字母条件（每行一个）", multiline=True, min_lines=4, max_lines=8,
            hint_text="物料 / SKU / Access Number\n每行一个",
            border_color=COLORS["border"], color=COLORS["text"],
            cursor_color=COLORS["accent"],
        )
        export_result_view = ft.Column(visible=False, spacing=8, scroll=ft.ScrollMode.AUTO)

        def on_query_num(e):
            conds = [c.strip() for c in num_input.value.split('\n') if c.strip()]
            if not conds:
                self.toast_error("请输入数字条件")
                return
            self._do_export_query(conds, 'num', export_result_view)

        def on_query_alpha(e):
            conds = [c.strip() for c in alpha_input.value.split('\n') if c.strip()]
            if not conds:
                self.toast_error("请输入字母条件")
                return
            self._do_export_query(conds, 'alpha', export_result_view)

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Text("Receiving / 数据导出", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ft.Divider(color=COLORS["border"]),
                    ft.ResponsiveRow([
                        ft.Container(num_input, col={"sm": 12, "md": 6}),
                        ft.Container(alpha_input, col={"sm": 12, "md": 6}),
                    ]),
                    ft.Row([
                        ft.FilledButton("查询（数字条件）", icon=ft.Icons.SEARCH,
                                       on_click=on_query_num,
                                       style=ft.ButtonStyle(bgcolor=COLORS["accent"])),
                        ft.FilledButton("查询（字母条件）", icon=ft.Icons.TEXT_SNIPPET,
                                       on_click=on_query_alpha,
                                       style=ft.ButtonStyle(bgcolor=COLORS["success"])),
                        ft.OutlinedButton("导出 Excel", icon=ft.Icons.DOWNLOAD,
                                        on_click=lambda e: self._export_excel_cached("export_data"),
                                        style=ft.ButtonStyle(color=COLORS["accent"])),
                    ], spacing=8, wrap=True),
                    export_result_view,
                ], spacing=12),
                padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    def _do_export_query(self, conditions, ctype, result_view):
        self._export_data_cache = None
        result_view.visible = False
        result_view.controls.clear()

        def query_fn():
            if ctype == 'num':
                return query_export_data(self.db, conditions, [])
            else:
                return query_export_data(self.db, [], conditions)

        def done(data):
            self._export_data_cache = data
            result_view.visible = True
            if not data.get('rows'):
                result_view.controls.append(ft.Text("查询结果为空", color=COLORS["text_muted"]))
                return
            tbl = self._make_data_table(data['fields'], data['rows'], height=450)
            prefix = data.get('file_prefix', 'data')
            result_view.controls.append(
                ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.INSERT_CHART, color=COLORS["success"]),
                        ft.Text(f"导出类型: {prefix}", size=13, color=COLORS["text"]),
                        ft.Text(f"共 {len(data['rows'])} 行", size=13, color=COLORS["text_muted"]),
                    ], spacing=8),
                    tbl,
                ], spacing=8)
            )

        self.run_db(query_fn, done)

    # ---------------------------------------------------------------
    #  标签历史视图
    # ---------------------------------------------------------------
    def _build_label_view(self):
        LH_TYPES = [
            "查询打印记录", "CHECK OPEN WORK", "CHECK AUDIT WORK",
            "检查SKU是否是AMINUS", "QA解锁?", "SO查询", "NFC",
            "查询包装信息", "RSO", "查询历史库位", "DP_area_info",
            "Export inventory",
        ]
        query_type_dd = ft.Dropdown(
            label="查询类型", options=[ft.dropdown.Option(t) for t in LH_TYPES],
            value=LH_TYPES[0], border_color=COLORS["border"], color=COLORS["text"], width=300,
        )
        carton_input = ft.TextField(
            label="箱号（每行一个）", multiline=True, min_lines=3, max_lines=6,
            hint_text="每行输入一个箱号", border_color=COLORS["border"], color=COLORS["text"],
        )
        label_result_view = ft.Column(visible=False, spacing=8)

        def on_query(e):
            cartons = [c.strip() for c in carton_input.value.split('\n') if c.strip()]
            if not cartons:
                self.toast_error("请输入箱号")
                return
            label_result_view.visible = False
            label_result_view.controls.clear()
            qt = query_type_dd.value

            def query_fn():
                return query_label_history(self.db, cartons, qt)

            def done(data):
                self._label_data_cache = data
                label_result_view.visible = True
                if data.get('type') == 'inventory_export':
                    label_result_view.controls.append(
                        ft.Text(f"Export Inventory - 箱号: {data.get('carton', '')}", size=14, color=COLORS["text"])
                    )
                    # 多 sheet 显示用 Tabs
                    tabs = []
                    for section in data.get('data', []):
                        tbl = self._make_data_table(section['fields'], section['rows'], height=300)
                        tabs.append(ft.Tab(text=section['sheet_name'][:15], content=tbl))
                    label_result_view.controls.append(ft.Tabs(tabs, selected_index=0))
                else:
                    if not data.get('fields') or not data.get('rows'):
                        label_result_view.controls.append(ft.Text("查询结果为空", color=COLORS["text_muted"]))
                        return
                    tbl = self._make_data_table(data['fields'], data['rows'], height=450)
                    label_result_view.controls.append(
                        ft.Column([
                            ft.Text(f"{data.get('query_type', '')} | 共 {data.get('total', 0)} 条",
                                   size=13, color=COLORS["text"]),
                            tbl,
                        ], spacing=8)
                    )

            self.run_db(query_fn, done)

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Text("查历史库位 / 标签", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ft.Divider(color=COLORS["border"]),
                    query_type_dd,
                    carton_input,
                    ft.Row([
                        ft.FilledButton("查询", icon=ft.Icons.SEARCH, on_click=on_query,
                                       style=ft.ButtonStyle(bgcolor=COLORS["accent"])),
                        ft.OutlinedButton("导出 Excel", icon=ft.Icons.DOWNLOAD,
                                        on_click=lambda e: self._export_excel_cached("label"),
                                        style=ft.ButtonStyle(color=COLORS["accent"])),
                    ], spacing=8),
                    label_result_view,
                ], spacing=12),
                padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ---------------------------------------------------------------
    #  日期查询视图
    # ---------------------------------------------------------------
    def _build_date_view(self):
        dq_types = list(DATE_QUERY_MAP.keys())
        date_dd = ft.Dropdown(
            label="查询类型", options=[ft.dropdown.Option(t) for t in dq_types],
            value=dq_types[0], border_color=COLORS["border"], color=COLORS["text"], width=350,
        )
        start_dp = ft.DatePicker()
        end_dp = ft.DatePicker()
        start_field = ft.TextField(
            label="开始日期", hint_text="点击选择", read_only=True,
            border_color=COLORS["border"], color=COLORS["text"], width=200,
        )
        end_field = ft.TextField(
            label="结束日期", hint_text="点击选择", read_only=True,
            border_color=COLORS["border"], color=COLORS["text"], width=200,
        )
        date_result_view = ft.Column(visible=False, spacing=8)

        def on_start(e):
            self.page.open(start_dp)

        def on_end(e):
            self.page.open(end_dp)

        def on_start_chg(e):
            if start_dp.value:
                start_field.value = start_dp.value.strftime("%Y-%m-%d")
                self.page.update()

        def on_end_chg(e):
            if end_dp.value:
                end_field.value = end_dp.value.strftime("%Y-%m-%d")
                self.page.update()

        start_dp.on_change = on_start_chg
        end_dp.on_change = on_end_chg

        def on_query(e):
            qt = date_dd.value
            dstart = start_dp.value
            dend = end_dp.value
            date_result_view.visible = False
            date_result_view.controls.clear()

            def query_fn():
                return query_date_range(self.db, qt, dstart, dend)

            def done(data):
                self._date_data_cache = data
                date_result_view.visible = True
                if not data.get('rows'):
                    date_result_view.controls.append(ft.Text("查询结果为空", color=COLORS["text_muted"]))
                    return
                tbl = self._make_data_table(data['fields'], data['rows'], height=450)
                pfx = data.get("file_prefix", "")
                date_result_view.controls.append(
                    ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.DATE_RANGE, color=COLORS["accent"]),
                            ft.Text(f"{pfx} | 共 {data.get('total', 0)} 条", size=13, color=COLORS["text"]),
                        ], spacing=8),
                        tbl,
                    ], spacing=8)
                )

            self.run_db(query_fn, done)

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Text("按日期查询", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ft.Divider(color=COLORS["border"]),
                    date_dd,
                    ft.Row([
                        ft.Row([start_field,
                                ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=on_start, icon_color=COLORS["accent"])]),
                        ft.Text("至", color=COLORS["text_muted"]),
                        ft.Row([end_field,
                                ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=on_end, icon_color=COLORS["accent"])]),
                    ], spacing=8, wrap=True),
                    ft.Row([
                        ft.FilledButton("查询", icon=ft.Icons.SEARCH, on_click=on_query,
                                       style=ft.ButtonStyle(bgcolor=COLORS["accent"])),
                        ft.OutlinedButton("导出 Excel", icon=ft.Icons.DOWNLOAD,
                                        on_click=lambda e: self._export_excel_cached("date"),
                                        style=ft.ButtonStyle(color=COLORS["accent"])),
                    ], spacing=8),
                    date_result_view,
                ], spacing=12),
                padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ---------------------------------------------------------------
    #  Incident 视图
    # ---------------------------------------------------------------
    def _build_incident_view(self):
        title_field = ft.TextField(
            label="标题 *", hint_text="请输入 Incident 标题",
            border_color=COLORS["border"], color=COLORS["text"],
        )
        desc_field = ft.TextField(
            label="描述", multiline=True, min_lines=6,
            hint_text="请输入详细描述", border_color=COLORS["border"], color=COLORS["text"],
        )
        cat_dd = ft.Dropdown(
            label="分类", options=[
                ft.dropdown.Option("Inquiry / Help"),
                ft.dropdown.Option("Incident"),
                ft.dropdown.Option("Service Request"),
            ], value="Inquiry / Help", border_color=COLORS["border"], color=COLORS["text"], width=300,
        )
        self.inc_result_view = ft.Column(visible=False, spacing=8)

        def onSubmit(e):
            if not title_field.value:
                self.toast_error("请输入标题")
                return

            def task():
                try:
                    import requests
                    cfg = get_config()
                    sn = cfg.get('service_now', {})
                    headers = sn.get('headers', {"Accept": "*/*", "Content-type": "application/json"})
                    payload = {
                        "short_description": title_field.value,
                        "description": desc_field.value or "",
                        "category": cat_dd.value,
                        "assignment_group": "",
                    }
                    # 合并模板
                    for cat_key, defaults in sn.get('incident_templates', {}).items():
                        if cat_key.lower() in cat_dd.value.lower() or cat_key.lower() in title_field.value.lower():
                            for k, v in defaults.items():
                                if k not in payload or not payload[k]:
                                    payload[k] = v

                    urls = [sn.get('url_create'), sn.get('url_create_backup')]
                    for url in urls:
                        if not url:
                            continue
                        resp = requests.post(
                            url, headers=headers,
                            auth=(sn.get('username', ''), sn.get('password', '')),
                            json=payload, timeout=30
                        )
                        if resp.status_code in (200, 201):
                            self.page.schedule_update()
                            self.inc_result_view.visible = True
                            self.inc_result_view.controls.clear()
                            self.inc_result_view.controls.append(
                                ft.Container(
                                    ft.Row([
                                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=COLORS["success"]),
                                        ft.Text("Incident 创建成功!", color=COLORS["success"], size=14, weight=ft.FontWeight.BOLD),
                                    ]), padding=12,
                                    bgcolor=ft.Colors.with_opacity(0.1, COLORS["success"]),
                                    border_radius=8,
                                )
                            )
                            self.loading.visible = False
                            self.page.update()
                            return
                    raise Exception(f"所有 URL 均失败")
                except Exception as ex:
                    self.page.schedule_update()
                    self.inc_result_view.visible = True
                    self.inc_result_view.controls.clear()
                    self.inc_result_view.controls.append(
                        ft.Container(
                            ft.Row([
                                ft.Icon(ft.Icons.ERROR, color=COLORS["error"]),
                                ft.Text(f"创建失败: {str(ex)[:200]}", color=COLORS["error"], size=14),
                            ]), padding=12,
                            bgcolor=ft.Colors.with_opacity(0.1, COLORS["error"]),
                            border_radius=8,
                        )
                    )
                    self.loading.visible = False
                    self.page.update()

            self.loading.visible = True
            self.page.update()
            threading.Thread(target=task, daemon=True).start()

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Text("创建 ServiceNow Incident", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ft.Divider(color=COLORS["border"]),
                    title_field,
                    desc_field,
                    cat_dd,
                    ft.FilledButton("创建 Incident", icon=ft.Icons.ADD_CIRCLE, on_click=onSubmit,
                                   style=ft.ButtonStyle(bgcolor=COLORS["accent"])),
                    self.inc_result_view,
                ], spacing=12),
                padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ---------------------------------------------------------------
    #  导出 Excel (缓存)
    # ---------------------------------------------------------------
    def _export_excel_cached(self, source):
        """从缓存导出 Excel"""
        cache_map = {
            "export_data": (self._export_data_cache, "Export_Data"),
            "label": (self._label_data_cache, "Label_History"),
            "date": (self._date_data_cache, "Date_Query"),
        }
        data, prefix = cache_map.get(source, (None, "data"))
        if not data:
            self.toast_error("请先执行查询后再导出")
            return

        def task():
            try:
                if isinstance(data, dict) and data.get('type') == 'inventory_export':
                    tmp_path = export_inventory_to_excel(data.get('data', []), prefix)
                else:
                    rows = data.get('rows', [])
                    fields = data.get('fields', [])
                    if not rows:
                        self.page.schedule_update()
                        self.toast_error("没有数据可导出")
                        self.page.update()
                        return
                    tmp_path = export_to_excel(rows, fields, prefix)

                self.page.schedule_update()
                self.toast(f"Excel 已生成: {tmp_path}")
                # 保存到桌面
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                dst = os.path.join(desktop, f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
                import shutil
                shutil.copy2(tmp_path, dst)
                self.toast(f"文件已保存至桌面: {os.path.basename(dst)}", COLORS["success"])
                self.page.update()
            except Exception as e:
                self.page.schedule_update()
                self.toast_error(str(e))
                self.page.update()

        threading.Thread(target=task, daemon=True).start()

    # ---------------------------------------------------------------
    #  UI 构建
    # ---------------------------------------------------------------
    def _build_ui(self):
        self.page.title = "PS Tool Desktop v" + __version__ + " - 仓储管理系统"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = COLORS["bg"]
        self.page.padding = 0
        self.page.window_width = 1280
        self.page.window_height = 800
        self.page.window_min_width = 900
        self.page.window_min_height = 600

        views = [
            self._build_gi_view(),
            self._build_export_view(),
            self._build_label_view(),
            self._build_date_view(),
            self._build_incident_view(),
        ]

        nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100,
            extended=True,
            bgcolor=COLORS["bg_dark"],
            indicator_color=COLORS["accent"],
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.CHECK_CIRCLE_OUTLINE, selected_icon=ft.Icons.CHECK_CIRCLE,
                    label="GI 状态"),
                ft.NavigationRailDestination(
                    icon=ft.Icons.FILE_DOWNLOAD_OUTLINED, selected_icon=ft.Icons.FILE_DOWNLOAD,
                    label="数据导出"),
                ft.NavigationRailDestination(
                    icon=ft.Icons.LABEL_OUTLINE, selected_icon=ft.Icons.LABEL,
                    label="标签历史"),
                ft.NavigationRailDestination(
                    icon=ft.Icons.DATE_RANGE_OUTLINED, selected_icon=ft.Icons.DATE_RANGE,
                    label="日期查询"),
                ft.NavigationRailDestination(
                    icon=ft.Icons.BUG_REPORT_OUTLINED, selected_icon=ft.Icons.BUG_REPORT,
                    label="创建 Incident"),
            ],
            on_change=lambda e: self._switch_tab(e.control.selected_index, views),
        )

        self.content_container.controls.append(views[0])
        self.content_container.controls.append(self.loading)

        # 顶部栏
        top_bar = ft.Container(
            ft.Row([
                ft.Icon(ft.Icons.WAREHOUSE, color=COLORS["accent"], size=24),
                ft.Text("PS Tool", size=18, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                ft.Container(expand=True),
                ft.Text("v" + __version__, size=11, color=COLORS["text_muted"]),
            ], spacing=8),
            padding=ft.padding.only(left=16, right=16, top=8, bottom=4),
            bgcolor=COLORS["bg_dark"],
        )

        self.page.add(
            ft.Column([
                top_bar,
                ft.Row([
                    nav_rail,
                    ft.VerticalDivider(width=1, color=COLORS["border"]),
                    ft.Container(self.content_container, expand=True),
                ], expand=True),
            ], spacing=0, expand=True)
        )

    def _switch_tab(self, index, views):
        self.content_container.controls.clear()
        self.content_container.controls.append(views[index])
        self.content_container.controls.append(self.loading)
        self.page.update()


def main(page: ft.Page):
    PSToolApp(page)


if __name__ == "__main__":
    ft.app(target=main)
