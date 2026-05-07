"""
PS Tool Desktop - Flet 桌面客户端 v2.1
现代化仓储管理工具
"""
import flet as ft
import os
import sys
import tempfile
import json
import shutil
import threading
from datetime import datetime
from functools import partial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (
    DBManager, query_gi_status, query_export_data, query_label_history,
    query_date_range, DATE_QUERY_MAP, export_to_excel, export_inventory_to_excel,
    get_config
)

__version__ = "2.1.0"

# ==================== 主题 ====================
C = {
    "bg": "#1a1a2e", "bg_dark": "#16213e", "bg_card": "#1e293b",
    "accent": "#0ea5e9", "accent_light": "#38bdf8",
    "success": "#22c55e", "warning": "#f59e0b", "error": "#ef4444", "purple": "#a855f7",
    "text": "#f1f5f9", "text_muted": "#94a3b8", "border": "#334155",
}


class PSToolApp:
    """PS Tool 主应用"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.db = DBManager()
        self._export_cache = None
        self._label_cache = None
        self._date_cache = None
        self._loading_visible = False
        self._build_ui()

    # ---------------------------------------------------------------
    #  UI 构建
    # ---------------------------------------------------------------
    def _build_ui(self):
        self.page.title = f"PS Tool Desktop v{__version__}"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = C["bg"]
        self.page.padding = 0
        self.page.window_width = 1280
        self.page.window_height = 800
        self.page.window_min_width = 900
        self.page.window_min_height = 600

        self.loading = ft.ProgressRing(visible=False, width=32, height=32, color=C["accent"])
        self.content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)

        self.nav = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=100, extended=True,
            bgcolor=C["bg_dark"], indicator_color=C["accent"],
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                    selected_icon=ft.Icons.CHECK_CIRCLE, label="GI 状态"),
                ft.NavigationRailDestination(icon=ft.Icons.FILE_DOWNLOAD_OUTLINED,
                    selected_icon=ft.Icons.FILE_DOWNLOAD, label="数据导出"),
                ft.NavigationRailDestination(icon=ft.Icons.LABEL_OUTLINE,
                    selected_icon=ft.Icons.LABEL, label="标签历史"),
                ft.NavigationRailDestination(icon=ft.Icons.DATE_RANGE_OUTLINED,
                    selected_icon=ft.Icons.DATE_RANGE, label="日期查询"),
                ft.NavigationRailDestination(icon=ft.Icons.BUG_REPORT_OUTLINED,
                    selected_icon=ft.Icons.BUG_REPORT, label="创建 Incident"),
            ],
            on_change=self._switch_tab,
        )

        self.views = [
            self._gi_view(),
            self._export_view(),
            self._label_view(),
            self._date_view(),
            self._incident_view(),
        ]
        self.content.controls = [self.views[0], self.loading]

        self.page.add(
            ft.Column([
                ft.Container(
                    ft.Row([
                        ft.Icon(ft.Icons.WAREHOUSE, color=C["accent"], size=22),
                        ft.Text("PS Tool", size=18, weight=ft.FontWeight.BOLD, color=C["text"]),
                        ft.Container(expand=True),
                        self.loading,
                        ft.Text(f"v{__version__}", size=11, color=C["text_muted"]),
                    ], spacing=8),
                    padding=ft.padding.only(left=16, right=16, top=8, bottom=4),
                    bgcolor=C["bg_dark"],
                ),
                ft.Row([
                    self.nav,
                    ft.VerticalDivider(width=1, color=C["border"]),
                    ft.Container(self.content, expand=True),
                ], expand=True),
            ], spacing=0, expand=True)
        )

    def _switch_tab(self, e):
        self.content.controls.clear()
        self.content.controls.append(self.views[e.control.selected_index])
        self.content.controls.append(self.loading)
        self.page.update()

    # ---------------------------------------------------------------
    #  安全更新：加载状态用 update() 直接处理
    # ---------------------------------------------------------------
    def _set_loading(self, v: bool):
        self.loading.visible = v
        self.page.update()

    def toast(self, msg, color=C["success"]):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg, color=ft.Colors.WHITE), bgcolor=color, duration=3000)
        self.page.snack_bar.open = True
        self.page.update()

    def err(self, msg):
        self.toast(str(msg), C["error"])

    def _run_async(self, worker_fn, update_fn):
        """
        在 Flet 的 run_thread 中执行数据库查询。
        run_thread 是 Flet 内置的线程池，会在同一个 session 上下文中运行，
        因此结束后可以直接调用页面方法做 UI 更新。
        """
        self._set_loading(True)

        def work_wrapper():
            try:
                result = worker_fn()
                # 这里仍在 run_thread 中，但 Flet 会正确处理 session 绑定
                update_fn(result)
                self._set_loading(False)
            except Exception as e:
                self.err(str(e))
                self._set_loading(False)

        self.page.run_thread(work_wrapper)

    # ---------------------------------------------------------------
    #  工具：创建表格
    # ---------------------------------------------------------------
    def _table(self, fields, rows, max_rows=50, height=500):
        if not fields or not rows:
            return ft.Container(ft.Text("无数据", color=C["text_muted"]), padding=20)
        cols = [ft.DataColumn(ft.Text(c[:20], size=11, weight=ft.FontWeight.BOLD, color=C["accent"]))
                for c in fields]
        dr = []
        for r in rows[:max_rows]:
            cells = [ft.DataCell(ft.Text(str(r.get(f, ''))[:60], size=11, color=C["text"], selectable=True))
                     for f in fields]
            dr.append(ft.DataRow(cells))
        dt = ft.DataTable(columns=cols, rows=dr, bgcolor=C["bg_card"],
                          border=ft.border.all(1, C["border"]), heading_row_color=C["bg_dark"],
                          column_spacing=16, data_row_max_height=30, heading_row_height=36)
        extra = f" (显示前 {max_rows} 条)" if len(rows) > max_rows else ""
        return ft.Column([
            ft.Text(f"共 {len(rows)} 条记录{extra}", size=12, color=C["text_muted"]),
            ft.Container(dt, height=height),
        ], spacing=4)

    def _card(self, icon, title, content):
        items = []
        if title:
            items.append(ft.Row([
                ft.Icon(icon, color=C["accent"], size=18) if icon else ft.Container(),
                ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=C["text"]),
            ], spacing=8))
        if content:
            items.append(content)
        return ft.Container(ft.Column(items, spacing=8), padding=16,
                           bgcolor=C["bg_card"], border_radius=8, margin=ft.margin.only(bottom=8))

    # ---------------------------------------------------------------
    #  GI 状态
    # ---------------------------------------------------------------
    def _gi_view(self):
        result_view = ft.Column(visible=False, spacing=12)
        refresh_btn = ft.FilledButton("刷新 GI 状态", icon=ft.Icons.REFRESH,
            style=ft.ButtonStyle(bgcolor=C["accent"]))

        def refresh(e):
            self._set_loading(True)
            result_view.visible = False
            result_view.controls.clear()

            def worker():
                return query_gi_status(self.db)

            def updater(data):
                result_view.visible = True
                done = data.get("gi_done", False)
                sc = C["success"] if done else C["error"]
                st = "GI 已完成 ✓" if done else "GI 未完成 ✗"

                result_view.controls.append(
                    ft.Container(ft.Row([
                        ft.Icon(ft.Icons.CHECK_CIRCLE if done else ft.Icons.ERROR, color=sc, size=20),
                        ft.Text(st, size=16, weight=ft.FontWeight.BOLD, color=sc),
                    ], spacing=8), padding=12, bgcolor=ft.Colors.with_opacity(0.1, sc), border_radius=8)
                )

                # 量卡片
                tv = data.get("today_volume", {})
                items = []
                for k, l, c in [("units", "总数", C["accent"]), ("cartons", "箱数", C["success"]),
                                ("dns", "DN", C["warning"]), ("pls", "PL", C["purple"])]:
                    val = str(tv.get(k, 0))
                    items.append(ft.Container(
                        ft.Column([ft.Text(val, size=24, weight=ft.FontWeight.BOLD, color=c),
                                   ft.Text(l, size=11, color=C["text_muted"])],
                                  spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=12, bgcolor=C["bg_card"], border_radius=8, col={"sm": 6, "md": 3},
                    ))
                result_view.controls.append(self._card(ft.Icons.BAR_CHART, "今日量统计", ft.ResponsiveRow(items, spacing=12)))

                # 时间
                result_view.controls.append(self._card(ft.Icons.ACCESS_TIME, "CMR / GI 时间", ft.Row([
                    ft.Column([ft.Text("最后 CMR 时间", size=11, color=C["text_muted"]),
                               ft.Text(str(data.get("max_cmr_time", "N/A")), size=16, weight=ft.FontWeight.BOLD, color=C["text"])]),
                    ft.VerticalDivider(color=C["border"]),
                    ft.Column([ft.Text("最后 GI 时间", size=11, color=C["text_muted"]),
                               ft.Text(str(data.get("max_gi_time", "N/A")), size=16, weight=ft.FontWeight.BOLD, color=C["text"])]),
                ], spacing=24)))

                # STSCODE
                if data.get("summary"):
                    rows = [[str(r.get(k, '')) for k in (data['summary'][0].keys())] for r in data['summary']]
                    hdrs = list(data['summary'][0].keys())
                    result_view.controls.append(self._card(ft.Icons.TABLE_CHART, "STSCODE 汇总",
                        ft.DataTable(
                            columns=[ft.DataColumn(ft.Text(h, size=11, weight=ft.FontWeight.BOLD, color=C["accent"])) for h in hdrs],
                            rows=[ft.DataRow([ft.DataCell(ft.Text(str(c), size=11, color=C["text"])) for c in r]) for r in rows],
                            bgcolor=C["bg_card"], border=ft.border.all(1, C["border"]), heading_row_color=C["bg_dark"],
                            heading_row_height=32, data_row_max_height=28,
                        )
                    ))

                # GI 状态
                if data.get("gi_status"):
                    hdrs = list(data['gi_status'][0].keys())
                    rows = [[str(r.get(k, '')) for k in hdrs] for r in data['gi_status']]
                    result_view.controls.append(self._card(None, "GI 状态统计",
                        ft.DataTable(
                            columns=[ft.DataColumn(ft.Text(h, size=11, weight=ft.FontWeight.BOLD, color=C["accent"])) for h in hdrs],
                            rows=[ft.DataRow([ft.DataCell(ft.Text(str(c), size=11, color=C["text"])) for c in r]) for r in rows],
                            bgcolor=C["bg_card"], border=ft.border.all(1, C["border"]), heading_row_color=C["bg_dark"],
                            heading_row_height=32, data_row_max_height=28,
                        )
                    ))

                # 错误
                if data.get("errors"):
                    hdrs = list(data['errors'][0].keys())
                    rows = [[str(r.get(k, '')) for k in hdrs] for r in data['errors']]
                    result_view.controls.append(self._card(ft.Icons.ERROR, "GI 错误记录",
                        ft.DataTable(
                            columns=[ft.DataColumn(ft.Text(h, size=11, weight=ft.FontWeight.BOLD, color=C["error"])) for h in hdrs],
                            rows=[ft.DataRow([ft.DataCell(ft.Text(str(c), size=11, color=C["error"])) for c in r]) for r in rows],
                            bgcolor=C["bg_card"], border=ft.border.all(1, C["border"]), heading_row_color=C["bg_dark"],
                            heading_row_height=32, data_row_max_height=28,
                        )
                    ))

            self._run_async(worker, updater)

        refresh_btn.on_click = refresh
        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Row([ft.Text("GI 状态监控", size=20, weight=ft.FontWeight.BOLD, color=C["text"]),
                            ft.Container(expand=True), refresh_btn]),
                    ft.Divider(color=C["border"]),
                    result_view,
                ], spacing=12),
                padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ---------------------------------------------------------------
    #  数据导出
    # ---------------------------------------------------------------
    def _export_view(self):
        num_in = ft.TextField(label="数字条件（每行一个）", multiline=True, min_lines=4, max_lines=8,
            hint_text="计划号 / Shipment / Packlist / Run / 箱号\n每行一个", border_color=C["border"], color=C["text"])
        alpha_in = ft.TextField(label="字母条件（每行一个）", multiline=True, min_lines=4, max_lines=8,
            hint_text="物料 / SKU / Access Number\n每行一个", border_color=C["border"], color=C["text"])
        result = ft.Column(spacing=8, visible=False, scroll=ft.ScrollMode.AUTO)

        def qnum(e):
            conds = [c.strip() for c in num_in.value.split('\n') if c.strip()]
            if not conds: return self.err("请输入数字条件")
            self._do_export(conds, 'num', result)

        def qalpha(e):
            conds = [c.strip() for c in alpha_in.value.split('\n') if c.strip()]
            if not conds: return self.err("请输入字母条件")
            self._do_export(conds, 'alpha', result)

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Text("Receiving / 数据导出", size=20, weight=ft.FontWeight.BOLD, color=C["text"]),
                    ft.Divider(color=C["border"]),
                    ft.ResponsiveRow([
                        ft.Container(num_in, col={"sm": 12, "md": 6}),
                        ft.Container(alpha_in, col={"sm": 12, "md": 6}),
                    ]),
                    ft.Row([
                        ft.FilledButton("查询（数字条件）", icon=ft.Icons.SEARCH, on_click=qnum,
                                       style=ft.ButtonStyle(bgcolor=C["accent"])),
                        ft.FilledButton("查询（字母条件）", icon=ft.Icons.TEXT_SNIPPET, on_click=qalpha,
                                       style=ft.ButtonStyle(bgcolor=C["success"])),
                        ft.OutlinedButton("导出 Excel", icon=ft.Icons.DOWNLOAD,
                                        on_click=lambda e: self._save_excel("export"),
                                        style=ft.ButtonStyle(color=C["accent"])),
                    ], spacing=8, wrap=True),
                    result,
                ], spacing=12),
                padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    def _do_export(self, conds, ctype, result):
        self._export_cache = None
        result.visible = False
        result.controls.clear()

        def worker():
            return query_export_data(self.db, conds if ctype == 'num' else [], conds if ctype == 'alpha' else [])

        def updater(data):
            self._export_cache = data
            result.visible = True
            if not data.get('rows'):
                result.controls.append(ft.Text("查询结果为空", color=C["text_muted"]))
                return
            pf = data.get("file_prefix", "data")
            result.controls.append(ft.Row([
                ft.Icon(ft.Icons.INSERT_CHART, color=C["success"]),
                ft.Text(f"{pf} | {len(data['rows'])} 行", size=13, color=C["text"]),
            ], spacing=8))
            result.controls.append(self._table(data['fields'], data['rows'], height=450))

        self._run_async(worker, updater)

    # ---------------------------------------------------------------
    #  标签历史
    # ---------------------------------------------------------------
    def _label_view(self):
        LH = ["查询打印记录", "CHECK OPEN WORK", "CHECK AUDIT WORK",
              "检查SKU是否是AMINUS", "QA解锁?", "SO查询", "NFC",
              "查询包装信息", "RSO", "查询历史库位", "DP_area_info", "Export inventory"]
        dd = ft.Dropdown(label="查询类型", options=[ft.dropdown.Option(t) for t in LH],
                        value=LH[0], border_color=C["border"], color=C["text"], width=300)
        ci = ft.TextField(label="箱号（每行一个）", multiline=True, min_lines=3, max_lines=6,
                          hint_text="每行输入一个箱号", border_color=C["border"], color=C["text"])
        result = ft.Column(spacing=8, visible=False)

        def query(e):
            cartons = [c.strip() for c in ci.value.split('\n') if c.strip()]
            if not cartons: return self.err("请输入箱号")
            result.visible = False; result.controls.clear()

            def worker():
                return query_label_history(self.db, cartons, dd.value)

            def updater(data):
                self._label_cache = data
                result.visible = True
                if data.get('type') == 'inventory_export':
                    result.controls.append(ft.Text(f"Export Inventory - {data.get('carton','')}", size=14, color=C["text"]))
                    tabs = []
                    for sec in data.get('data', []):
                        tabs.append(ft.Tab(text=sec['sheet_name'][:15],
                                           content=self._table(sec['fields'], sec['rows'], height=300)))
                    result.controls.append(ft.Tabs(tabs, selected_index=0))
                else:
                    if not data.get('fields') or not data.get('rows'):
                        result.controls.append(ft.Text("查询结果为空", color=C["text_muted"]))
                        return
                    result.controls.append(ft.Text(f"{data.get('query_type','')} | {data.get('total',0)} 条", size=13, color=C["text"]))
                    result.controls.append(self._table(data['fields'], data['rows'], height=450))

            self._run_async(worker, updater)

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Text("查历史库位 / 标签", size=20, weight=ft.FontWeight.BOLD, color=C["text"]),
                    ft.Divider(color=C["border"]), dd, ci,
                    ft.Row([
                        ft.FilledButton("查询", icon=ft.Icons.SEARCH, on_click=query,
                                       style=ft.ButtonStyle(bgcolor=C["accent"])),
                        ft.OutlinedButton("导出 Excel", icon=ft.Icons.DOWNLOAD,
                                        on_click=lambda e: self._save_excel("label"),
                                        style=ft.ButtonStyle(color=C["accent"])),
                    ], spacing=8),
                    result,
                ], spacing=12), padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ---------------------------------------------------------------
    #  日期查询
    # ---------------------------------------------------------------
    def _date_view(self):
        types = list(DATE_QUERY_MAP.keys())
        dd = ft.Dropdown(label="查询类型", options=[ft.dropdown.Option(t) for t in types],
                        value=types[0], border_color=C["border"], color=C["text"], width=350)
        sd = ft.DatePicker(); ed = ft.DatePicker()
        sf = ft.TextField(label="开始日期", hint_text="点击选择", read_only=True,
                         border_color=C["border"], color=C["text"], width=200)
        efld = ft.TextField(label="结束日期", hint_text="点击选择", read_only=True,
                          border_color=C["border"], color=C["text"], width=200)
        result = ft.Column(spacing=8, visible=False)

        def on_sd(e): self.page.open(sd)
        def on_ed(e): self.page.open(ed)
        def sd_chg(e):
            if sd.value: sf.value = sd.value.strftime("%Y-%m-%d"); self.page.update()
        def ed_chg(e):
            if ed.value: efld.value = ed.value.strftime("%Y-%m-%d"); self.page.update()
        sd.on_change, ed.on_change = sd_chg, ed_chg

        def query(e):
            result.visible = False; result.controls.clear()
            def worker():
                return query_date_range(self.db, dd.value, sd.value, ed.value)
            def updater(data):
                self._date_cache = data
                result.visible = True
                if not data.get('rows'):
                    result.controls.append(ft.Text("查询结果为空", color=C["text_muted"]))
                    return
                pf = data.get("file_prefix", "")
                result.controls.append(ft.Row([
                    ft.Icon(ft.Icons.DATE_RANGE, color=C["accent"]),
                    ft.Text(f"{pf} | {data.get('total',0)} 条", size=13, color=C["text"]),
                ], spacing=8))
                result.controls.append(self._table(data['fields'], data['rows'], height=450))
            self._run_async(worker, updater)

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Text("按日期查询", size=20, weight=ft.FontWeight.BOLD, color=C["text"]),
                    ft.Divider(color=C["border"]), dd,
                    ft.Row([
                        ft.Row([sf, ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=on_sd, icon_color=C["accent"])]),
                        ft.Text("至", color=C["text_muted"]),
                        ft.Row([efld, ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=on_ed, icon_color=C["accent"])]),
                    ], spacing=8, wrap=True),
                    ft.Row([
                        ft.FilledButton("查询", icon=ft.Icons.SEARCH, on_click=query,
                                       style=ft.ButtonStyle(bgcolor=C["accent"])),
                        ft.OutlinedButton("导出 Excel", icon=ft.Icons.DOWNLOAD,
                                        on_click=lambda e: self._save_excel("date"),
                                        style=ft.ButtonStyle(color=C["accent"])),
                    ], spacing=8),
                    result,
                ], spacing=12), padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ---------------------------------------------------------------
    #  Incident
    # ---------------------------------------------------------------
    def _incident_view(self):
        title_f = ft.TextField(label="标题 *", hint_text="请输入 Incident 标题",
                              border_color=C["border"], color=C["text"])
        desc_f = ft.TextField(label="描述", multiline=True, min_lines=6,
                             hint_text="请输入详细描述", border_color=C["border"], color=C["text"])
        cat_dd = ft.Dropdown(label="分类",
            options=[ft.dropdown.Option(t) for t in ["Inquiry / Help", "Incident", "Service Request"]],
            value="Inquiry / Help", border_color=C["border"], color=C["text"], width=300)
        result = ft.Column(spacing=8, visible=False)

        def submit(e):
            if not title_f.value: return self.err("请输入标题")
            result.visible = False; result.controls.clear()

            def worker():
                import requests
                cfg = get_config()
                sn = cfg.get('service_now', {})
                payload = {
                    "short_description": title_f.value,
                    "description": desc_f.value or "",
                    "category": cat_dd.value, "assignment_group": "",
                }
                for ck, defaults in sn.get('incident_templates', {}).items():
                    if ck.lower() in cat_dd.value.lower() or ck.lower() in title_f.value.lower():
                        for k, v in defaults.items():
                            if k not in payload or not payload[k]:
                                payload[k] = v

                urls = [sn.get('url_create'), sn.get('url_create_backup')]
                for url in urls:
                    if not url: continue
                    resp = requests.post(url,
                        headers={"Accept": "*/*", "Content-type": "application/json"},
                        auth=(sn.get('username', ''), sn.get('password', '')),
                        json=payload, timeout=30)
                    if resp.status_code in (200, 201):
                        return {"ok": True, "data": resp.json()}
                raise Exception("所有 ServiceNow URL 均响应失败")

            def updater(ret):
                if isinstance(ret, dict) and ret.get("ok"):
                    result.controls.append(ft.Container(
                        ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, color=C["success"]),
                                ft.Text("Incident 创建成功!", color=C["success"], size=14, weight=ft.FontWeight.BOLD)]),
                        padding=12, bgcolor=ft.Colors.with_opacity(0.1, C["success"]), border_radius=8))
                result.visible = True

            self._run_async(worker, updater)

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Text("创建 ServiceNow Incident", size=20, weight=ft.FontWeight.BOLD, color=C["text"]),
                    ft.Divider(color=C["border"]), title_f, desc_f, cat_dd,
                    ft.FilledButton("创建 Incident", icon=ft.Icons.ADD_CIRCLE, on_click=submit,
                                   style=ft.ButtonStyle(bgcolor=C["accent"])),
                    result,
                ], spacing=12), padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ---------------------------------------------------------------
    #  导出 Excel
    # ---------------------------------------------------------------
    def _save_excel(self, source):
        cache = {"export": self._export_cache, "label": self._label_cache, "date": self._date_cache}.get(source)
        if not cache: return self.err("请先执行查询")

        def worker():
            if isinstance(cache, dict) and cache.get('type') == 'inventory_export':
                tmp = export_inventory_to_excel(cache.get('data', []), "Inventory")
            else:
                rows = cache.get('rows', [])
                fields = cache.get('fields', [])
                if not rows: raise Exception("没有数据可导出")
                tmp = export_to_excel(rows, fields, source)
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            os.makedirs(desktop, exist_ok=True)
            dst = os.path.join(desktop, f"PS_Tool_{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            shutil.copy2(tmp, dst)
            return dst

        def updater(path):
            self.toast(f"✅ Excel 已保存至桌面: {os.path.basename(path)}")

        self._run_async(worker, updater)


def main(page: ft.Page):
    PSToolApp(page)


if __name__ == "__main__":
    ft.app(target=main)
