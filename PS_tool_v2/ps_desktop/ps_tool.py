"""
PS Tool Desktop v2.2 - Flet 桌面客户端
"""
import flet as ft
import os, sys, shutil, tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (
    DBManager, query_gi_status, query_export_data, query_label_history,
    query_date_range, DATE_QUERY_MAP, export_to_excel, export_inventory_to_excel,
    get_config
)

C = {
    "bg": "#1a1a2e", "bg_dark": "#16213e", "bg_card": "#1e293b",
    "accent": "#0ea5e9", "success": "#22c55e", "warning": "#f59e0b",
    "error": "#ef4444", "purple": "#a855f7",
    "text": "#f1f5f9", "text_muted": "#94a3b8", "border": "#334155",
}


class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self.db = DBManager()
        self._cache = {}
        self._build()

    # ==================== 构建 UI ====================
    def _build(self):
        self.page.title = "PS Tool Desktop v2.2"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = C["bg"]
        self.page.padding = 0
        self.page.window_width = 1280
        self.page.window_height = 800

        self.loading = ft.ProgressRing(visible=False, width=32, height=32, color=C["accent"])
        self.main = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)

        nav = ft.NavigationRail(
            selected_index=0, label_type=ft.NavigationRailLabelType.ALL,
            min_width=100, extended=True, bgcolor=C["bg_dark"], indicator_color=C["accent"],
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.CHECK_CIRCLE_OUTLINE, selected_icon=ft.Icons.CHECK_CIRCLE, label="GI 状态"),
                ft.NavigationRailDestination(icon=ft.Icons.FILE_DOWNLOAD_OUTLINED, selected_icon=ft.Icons.FILE_DOWNLOAD, label="数据导出"),
                ft.NavigationRailDestination(icon=ft.Icons.LABEL_OUTLINE, selected_icon=ft.Icons.LABEL, label="标签历史"),
                ft.NavigationRailDestination(icon=ft.Icons.DATE_RANGE_OUTLINED, selected_icon=ft.Icons.DATE_RANGE, label="日期查询"),
                ft.NavigationRailDestination(icon=ft.Icons.BUG_REPORT_OUTLINED, selected_icon=ft.Icons.BUG_REPORT, label="创建 Incident"),
            ],
            on_change=self._switch,
        )

        self.views = [self._gi(), self._export(), self._label(), self._date(), self._incident()]
        self.main.controls = [self.views[0], self.loading]

        self.page.add(
            ft.Column([
                ft.Container(
                    ft.Row([
                        ft.Icon(ft.Icons.WAREHOUSE, color=C["accent"], size=22),
                        ft.Text("PS Tool", size=18, weight=ft.FontWeight.BOLD, color=C["text"]),
                        ft.Container(expand=True),
                        self.loading,
                    ], spacing=8),
                    padding=ft.padding.only(left=16, right=16, top=8, bottom=4),
                    bgcolor=C["bg_dark"],
                ),
                ft.Row([nav, ft.VerticalDivider(width=1, color=C["border"]),
                        ft.Container(self.main, expand=True)], expand=True),
            ], spacing=0, expand=True)
        )

    def _switch(self, e):
        self.main.controls.clear()
        self.main.controls.append(self.views[e.control.selected_index])
        self.main.controls.append(self.loading)
        self.page.update()

    def _loader(self, v: bool):
        self.loading.visible = v
        self.page.update()

    def toast(self, msg, c=C["success"]):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg, color=ft.Colors.WHITE), bgcolor=c, duration=3000)
        self.page.snack_bar.open = True
        self.page.update()

    def err(self, msg): self.toast(str(msg), C["error"])

    def _run(self, work, update):
        """使用 run_thread 执行后台任务。run_thread 是 Flet 官方线程安全 API。"""
        self._loader(True)
        def wrapper():
            try:
                result = work()
                # run_thread 已绑定 session 上下文，可直接更新 UI
                update(result)
            except Exception as e:
                self.err(str(e))
            finally:
                # 清除加载状态
                if self.loading.visible:
                    self.loading.visible = False
                    self.page.update()
        self.page.run_thread(wrapper)

    # ==================== 表格工具 ====================
    def _tbl(self, fields, rows, h=500):
        if not fields or not rows:
            return ft.Container(ft.Text("无数据", color=C["text_muted"]), padding=20)
        cols = [ft.DataColumn(ft.Text(c[:20], size=11, weight=ft.FontWeight.BOLD, color=C["accent"])) for c in fields]
        dr = []
        for r in rows[:100]:
            dr.append(ft.DataRow([
                ft.DataCell(ft.Text(str(r.get(f, ''))[:60], size=11, color=C["text"], selectable=True))
                for f in fields
            ]))
        extra = f" (显示前 100 条，共 {len(rows)} 条)" if len(rows) > 100 else f"共 {len(rows)} 条"
        return ft.Column([
            ft.Text(extra, size=12, color=C["text_muted"]),
            ft.Container(ft.DataTable(
                columns=cols, rows=dr, bgcolor=C["bg_card"],
                border=ft.border.all(1, C["border"]), heading_row_color=C["bg_dark"],
                column_spacing=16, data_row_max_height=30, heading_row_height=36,
            ), height=h),
        ], spacing=4)

    def _card(self, icon, title, body):
        return ft.Container(
            ft.Column(spacing=8, controls=[
                ft.Row([ft.Icon(icon, color=C["accent"], size=18) if icon else ft.Container(),
                        ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=C["text"])], spacing=8)
            ] + ([body] if body else [])),
            padding=16, bgcolor=C["bg_card"], border_radius=8, margin=ft.margin.only(bottom=8),
        )

    def _stat_cards(self, items, cols=4):
        """items: [(值, 标签, 颜色), ...]"""
        return ft.ResponsiveRow([
            ft.Container(
                ft.Column([
                    ft.Text(str(v), size=24, weight=ft.FontWeight.BOLD, color=c),
                    ft.Text(l, size=11, color=C["text_muted"]),
                ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=12, bgcolor=C["bg_card"], border_radius=8, col={"sm": 12//cols, "md": 12//cols},
            ) for v, l, c in items
        ], spacing=12)

    def _simple_table(self, headers, rows, err=False):
        tc = C["error"] if err else C["accent"]
        dt = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(h, size=11, weight=ft.FontWeight.BOLD, color=tc)) for h in headers],
            rows=[ft.DataRow([ft.DataCell(ft.Text(str(c), size=11, color=C["text"])) for c in r]) for r in rows],
            bgcolor=C["bg_card"], border=ft.border.all(1, C["border"]), heading_row_color=C["bg_dark"],
            heading_row_height=32, data_row_max_height=28,
        )
        return dt

    # ==================== GI 状态 ====================
    def _gi(self):
        rv = ft.Column(spacing=12, visible=False)
        def refresh(e):
            rv.visible = False
            rv.controls.clear()
            def work():
                return query_gi_status(self.db)
            def up(data):
                rv.visible = True
                done = data.get("gi_done", False)
                c = C["success"] if done else C["error"]
                t = "GI 已完成 ✓" if done else "GI 未完成 ✗"
                rv.controls.append(ft.Container(
                    ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE if done else ft.Icons.ERROR, color=c, size=20),
                            ft.Text(t, size=16, weight=ft.FontWeight.BOLD, color=c)], spacing=8),
                    padding=12, bgcolor=ft.Colors.with_opacity(0.1, c), border_radius=8,
                ))
                tv = data.get("today_volume", {})
                rv.controls.append(self._card(ft.Icons.BAR_CHART, "今日量统计",
                    self._stat_cards([
                        (tv.get("units", 0), "总数量", C["accent"]),
                        (tv.get("cartons", 0), "箱数", C["success"]),
                        (tv.get("dns", 0), "DN", C["warning"]),
                        (tv.get("pls", 0), "PL", C["purple"]),
                    ])))
                rv.controls.append(self._card(ft.Icons.ACCESS_TIME, "CMR / GI 时间", ft.Row([
                    ft.Column([ft.Text("最后 CMR 时间", size=11, color=C["text_muted"]),
                              ft.Text(str(data.get("max_cmr_time", "N/A")), size=16, weight=ft.FontWeight.BOLD, color=C["text"])]),
                    ft.VerticalDivider(color=C["border"]),
                    ft.Column([ft.Text("最后 GI 时间", size=11, color=C["text_muted"]),
                              ft.Text(str(data.get("max_gi_time", "N/A")), size=16, weight=ft.FontWeight.BOLD, color=C["text"])]),
                ], spacing=24)))
                if data.get("summary"):
                    h = list(data['summary'][0].keys())
                    r = [[str(rr.get(k, '')) for k in h] for rr in data['summary']]
                    rv.controls.append(self._card(ft.Icons.TABLE_CHART, "STSCODE 汇总", self._simple_table(h, r)))
                if data.get("gi_status"):
                    h = list(data['gi_status'][0].keys())
                    r = [[str(rr.get(k, '')) for k in h] for rr in data['gi_status']]
                    rv.controls.append(self._card(None, "GI 状态统计", self._simple_table(h, r)))
                if data.get("errors"):
                    h = list(data['errors'][0].keys())
                    r = [[str(rr.get(k, '')) for k in h] for rr in data['errors']]
                    rv.controls.append(self._card(ft.Icons.ERROR, "GI 错误记录", self._simple_table(h, r, err=True)))
            self._run(work, up)
        return ft.Column([
            ft.Container(ft.Column([
                ft.Row([ft.Text("GI 状态监控", size=20, weight=ft.FontWeight.BOLD, color=C["text"]),
                        ft.Container(expand=True),
                        ft.FilledButton("刷新", icon=ft.Icons.REFRESH, on_click=refresh,
                                       style=ft.ButtonStyle(bgcolor=C["accent"]))]),
                ft.Divider(color=C["border"]), rv,
            ], spacing=12), padding=24, expand=True),
        ], scroll=ft.ScrollMode.AUTO)

    # ==================== 数据导出 ====================
    def _export(self):
        ni = ft.TextField(label="数字条件（每行一个）", multiline=True, min_lines=4, max_lines=8,
                         hint_text="计划号 / Shipment / Packlist / Run / 箱号", border_color=C["border"], color=C["text"])
        ai = ft.TextField(label="字母条件（每行一个）", multiline=True, min_lines=4, max_lines=8,
                         hint_text="物料 / SKU / Access Number", border_color=C["border"], color=C["text"])
        rv = ft.Column(spacing=8, visible=False, scroll=ft.ScrollMode.AUTO)
        def q_num(e):
            c = [x.strip() for x in ni.value.split('\n') if x.strip()]
            if not c: return self.err("请输入数字条件")
            self._do_export(c, 'num', rv)
        def q_alpha(e):
            c = [x.strip() for x in ai.value.split('\n') if x.strip()]
            if not c: return self.err("请输入字母条件")
            self._do_export(c, 'alpha', rv)
        return ft.Column([
            ft.Container(ft.Column([
                ft.Text("数据导出", size=20, weight=ft.FontWeight.BOLD, color=C["text"]),
                ft.Divider(color=C["border"]),
                ft.ResponsiveRow([ft.Container(ni, col={"sm":12,"md":6}), ft.Container(ai, col={"sm":12,"md":6})]),
                ft.Row([
                    ft.FilledButton("数字查询", icon=ft.Icons.SEARCH, on_click=q_num, style=ft.ButtonStyle(bgcolor=C["accent"])),
                    ft.FilledButton("字母查询", icon=ft.Icons.TEXT_SNIPPET, on_click=q_alpha, style=ft.ButtonStyle(bgcolor=C["success"])),
                    ft.OutlinedButton("导出 Excel", icon=ft.Icons.DOWNLOAD,
                                    on_click=lambda e: self._save("export"),
                                    style=ft.ButtonStyle(color=C["accent"])),
                ], spacing=8, wrap=True), rv,
            ], spacing=12), padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    def _do_export(self, conds, ct, rv):
        self._cache['export'] = None; rv.visible = False; rv.controls.clear()
        def work():
            from core import query_export_data
            return query_export_data(self.db, conds if ct == 'num' else [], conds if ct == 'alpha' else [])
        def up(data):
            self._cache['export'] = data; rv.visible = True
            if not data.get('rows'): rv.controls.append(ft.Text("无数据", color=C["text_muted"]))
            else:
                pf = data.get('file_prefix','')
                rv.controls.append(ft.Row([ft.Icon(ft.Icons.INSERT_CHART,color=C["success"]),
                                           ft.Text(f"{pf} | {len(data['rows'])} 行", size=13, color=C["text"])]))
                rv.controls.append(self._tbl(data['fields'], data['rows']))
        self._run(work, up)

    # ==================== 标签历史 ====================
    def _label(self):
        LH = ["查询打印记录","CHECK OPEN WORK","CHECK AUDIT WORK","检查SKU是否是AMINUS",
              "QA解锁?","SO查询","NFC","查询包装信息","RSO","查询历史库位","DP_area_info","Export inventory"]
        dd = ft.Dropdown(label="查询类型", options=[ft.dropdown.Option(t) for t in LH],
                        value=LH[0], border_color=C["border"], color=C["text"], width=300)
        ci = ft.TextField(label="箱号（每行一个）", multiline=True, min_lines=3, max_lines=6,
                         hint_text="每行一个箱号", border_color=C["border"], color=C["text"])
        rv = ft.Column(spacing=8, visible=False)

        def q(e):
            c = [x.strip() for x in ci.value.split('\n') if x.strip()]
            if not c: return self.err("请输入箱号")
            rv.visible = False; rv.controls.clear()
            def work():
                from core import query_label_history
                return query_label_history(self.db, c, dd.value)
            def up(data):
                self._cache['label'] = data; rv.visible = True
                if data.get('type') == 'inventory_export':
                    rv.controls.append(ft.Text(f"Export - {data.get('carton','')}", size=14, color=C["text"]))
                    tabs = [ft.Tab(text=s.get('sheet_name','')[:15], content=self._tbl(s['fields'], s['rows']))
                            for s in data.get('data',[])]
                    rv.controls.append(ft.Tabs(tabs, selected_index=0))
                else:
                    if not data.get('fields') or not data.get('rows'):
                        rv.controls.append(ft.Text("无数据", color=C["text_muted"]))
                        return
                    rv.controls.append(ft.Text(f"{data.get('query_type','')} | {data.get('total',0)} 条", size=13, color=C["text"]))
                    rv.controls.append(self._tbl(data['fields'], data['rows']))
            self._run(work, up)

        return ft.Column([
            ft.Container(ft.Column([
                ft.Text("标签历史", size=20, weight=ft.FontWeight.BOLD, color=C["text"]),
                ft.Divider(color=C["border"]), dd, ci,
                ft.Row([
                    ft.FilledButton("查询", icon=ft.Icons.SEARCH, on_click=q, style=ft.ButtonStyle(bgcolor=C["accent"])),
                    ft.OutlinedButton("导出 Excel", icon=ft.Icons.DOWNLOAD,
                                    on_click=lambda e: self._save("label"),
                                    style=ft.ButtonStyle(color=C["accent"])),
                ], spacing=8), rv,
            ], spacing=12), padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ==================== 日期查询 ====================
    def _date(self):
        types = list(DATE_QUERY_MAP.keys())
        dd = ft.Dropdown(label="查询类型", options=[ft.dropdown.Option(t) for t in types],
                        value=types[0], border_color=C["border"], color=C["text"], width=350)
        sp = ft.DatePicker(); ep = ft.DatePicker()
        sf = ft.TextField(label="开始日期", hint_text="点击选择", read_only=True,
                         border_color=C["border"], color=C["text"], width=200)
        ef = ft.TextField(label="结束日期", hint_text="点击选择", read_only=True,
                         border_color=C["border"], color=C["text"], width=200)
        rv = ft.Column(spacing=8, visible=False)

        def ps(e): self.page.open(sp)
        def pe(e): self.page.open(ep)
        sp.on_change = lambda e: setattr(sf, 'value', sp.value.strftime("%Y-%m-%d")) or self.page.update() if sp.value else None
        ep.on_change = lambda e: setattr(ef, 'value', ep.value.strftime("%Y-%m-%d")) or self.page.update() if ep.value else None

        def q(e):
            rv.visible = False; rv.controls.clear()
            def work():
                from core import query_date_range
                return query_date_range(self.db, dd.value, sp.value, ep.value)
            def up(data):
                self._cache['date'] = data; rv.visible = True
                if not data.get('rows'): rv.controls.append(ft.Text("无数据", color=C["text_muted"]))
                else:
                    pf = data.get('file_prefix','')
                    rv.controls.append(ft.Row([ft.Icon(ft.Icons.DATE_RANGE,color=C["accent"]),
                                               ft.Text(f"{pf} | {data.get('total',0)} 条")]))
                    rv.controls.append(self._tbl(data['fields'], data['rows']))
            self._run(work, up)

        return ft.Column([
            ft.Container(ft.Column([
                ft.Text("按日期查询", size=20, weight=ft.FontWeight.BOLD, color=C["text"]),
                ft.Divider(color=C["border"]), dd,
                ft.Row([
                    ft.Row([sf, ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=ps, icon_color=C["accent"])]),
                    ft.Text("至", color=C["text_muted"]),
                    ft.Row([ef, ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=pe, icon_color=C["accent"])]),
                ], spacing=8, wrap=True),
                ft.Row([
                    ft.FilledButton("查询", icon=ft.Icons.SEARCH, on_click=q, style=ft.ButtonStyle(bgcolor=C["accent"])),
                    ft.OutlinedButton("导出 Excel", icon=ft.Icons.DOWNLOAD,
                                    on_click=lambda e: self._save("date"),
                                    style=ft.ButtonStyle(color=C["accent"])),
                ], spacing=8), rv,
            ], spacing=12), padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ==================== Incident ====================
    def _incident(self):
        tf = ft.TextField(label="标题 *", hint_text="输入标题", border_color=C["border"], color=C["text"])
        df = ft.TextField(label="描述", multiline=True, min_lines=6, hint_text="详细描述",
                         border_color=C["border"], color=C["text"])
        cd = ft.Dropdown(label="分类",
            options=[ft.dropdown.Option(t) for t in ["Inquiry / Help","Incident","Service Request"]],
            value="Inquiry / Help", border_color=C["border"], color=C["text"], width=300)
        rv = ft.Column(spacing=8, visible=False)

        def sub(e):
            if not tf.value: return self.err("请输入标题")
            rv.visible = False; rv.controls.clear()
            def work():
                import requests
                cfg = get_config()
                sn = cfg.get('service_now', {})
                payload = {
                    "short_description": tf.value,
                    "description": df.value or "",
                    "category": cd.value, "assignment_group": "",
                }
                for ck, defaults in sn.get('incident_templates', {}).items():
                    if ck.lower() in cd.value.lower() or ck.lower() in tf.value.lower():
                        for k, v in defaults.items():
                            if k not in payload or not payload[k]: payload[k] = v
                urls = [sn.get('url_create'), sn.get('url_create_backup')]
                for url in urls:
                    if not url: continue
                    r = requests.post(url,
                        headers={"Accept":"*/*","Content-type":"application/json"},
                        auth=(sn.get('username',''), sn.get('password','')),
                        json=payload, timeout=30)
                    if r.status_code in (200, 201): return {"ok":True}
                raise Exception("ServiceNow 响应失败")
            def up(ret):
                if ret.get("ok"):
                    rv.controls.append(ft.Container(
                        ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE,color=C["success"]),
                                ft.Text("创建成功!",color=C["success"],size=14,weight=ft.FontWeight.BOLD)]),
                        padding=12, bgcolor=ft.Colors.with_opacity(0.1,C["success"]), border_radius=8))
                rv.visible = True
            self._run(work, up)

        return ft.Column([
            ft.Container(ft.Column([
                ft.Text("创建 Incident", size=20, weight=ft.FontWeight.BOLD, color=C["text"]),
                ft.Divider(color=C["border"]), tf, df, cd,
                ft.FilledButton("提交", icon=ft.Icons.ADD_CIRCLE, on_click=sub,
                              style=ft.ButtonStyle(bgcolor=C["accent"])), rv,
            ], spacing=12), padding=24, expand=True,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ==================== 导出 ====================
    def _save(self, key):
        data = self._cache.get(key)
        if not data: return self.err("请先查询")
        def work():
            if isinstance(data, dict) and data.get('type') == 'inventory_export':
                tmp = export_inventory_to_excel(data.get('data',[]), "Inventory")
            else:
                rows, fields = data.get('rows',[]), data.get('fields',[])
                if not rows: raise Exception("无数据")
                tmp = export_to_excel(rows, fields, key)
            ds = os.path.join(os.path.expanduser("~"), "Desktop")
            os.makedirs(ds, exist_ok=True)
            dst = os.path.join(ds, f"PS_Tool_{key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            shutil.copy2(tmp, dst)
            return dst
        def up(p):
            self.toast(f"✅ 已保存: {os.path.basename(p)}")
        self._run(work, up)


def main(page: ft.Page):
    App(page)


if __name__ == "__main__":
    ft.app(target=main)
