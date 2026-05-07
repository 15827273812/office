"""
PS Tool Desktop v2.3 - Flet 桌面客户端
完整功能版：清屏、格式化SQL、GI status check、Delete Voice user、Health Check、Add Voice user + 自动全屏
"""
import flet as ft
import os, sys, re, time, json, tempfile, threading, math
import shutil, subprocess, pathlib
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import DBManager, get_config

C = {
    "bg": "#1a1a2e", "bg_dark": "#16213e", "bg_card": "#1e293b",
    "accent": "#0ea5e9", "success": "#22c55e", "warning": "#f59e0b",
    "error": "#ef4444", "purple": "#a855f7",
    "orange": "#f97316",
    "text": "#f1f5f9", "text_muted": "#94a3b8", "border": "#334155",
}

class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self.db = DBManager()
        self._cfg = get_config()
        self._cache = {}
        self._gi_data = {}
        self._build()

    def _build(self):
        self.page.title = "PS Tool Desktop v2.3"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = C["bg"]
        self.page.padding = 0
        self.page.window_width = 1280
        self.page.window_height = 800
        self.loading = ft.ProgressRing(visible=False, width=32, height=32, color=C["accent"])
        self.status_text = ft.Text("就绪", size=12, color=C["text_muted"])
        self.main = ft.Column(expand=True, spacing=0)
        nav = ft.NavigationRail(
            selected_index=0, label_type=ft.NavigationRailLabelType.ALL,
            min_width=100, extended=True, bgcolor=C["bg_dark"], indicator_color=C["accent"],
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.TERMINAL, selected_icon=ft.Icons.TERMINAL, label="工作台"),
                ft.NavigationRailDestination(icon=ft.Icons.CHECK_CIRCLE_OUTLINE, selected_icon=ft.Icons.CHECK_CIRCLE, label="GI 状态"),
                ft.NavigationRailDestination(icon=ft.Icons.FILE_DOWNLOAD_OUTLINED, selected_icon=ft.Icons.FILE_DOWNLOAD, label="数据导出"),
                ft.NavigationRailDestination(icon=ft.Icons.LABEL_OUTLINE, selected_icon=ft.Icons.LABEL, label="标签历史"),
                ft.NavigationRailDestination(icon=ft.Icons.DATE_RANGE_OUTLINED, selected_icon=ft.Icons.DATE_RANGE, label="日期查询"),
                ft.NavigationRailDestination(icon=ft.Icons.BUG_REPORT_OUTLINED, selected_icon=ft.Icons.BUG_REPORT, label="Incident"),
            ],
            on_change=self._switch,
        )
        self.views = [self._workbench(), self._gi(), self._export(), self._label(), self._date(), self._incident()]
        self.main.controls = [self.views[0]]
        self.page.add(ft.Column([
            ft.Container(
                ft.Row([
                    ft.Icon(ft.Icons.WAREHOUSE, color=C["accent"], size=22),
                    ft.Text("PS Tool v2.3", size=18, weight=ft.FontWeight.BOLD, color=C["text"]),
                    ft.Container(expand=True),
                    self.loading,
                    self.status_text,
                ], spacing=8),
                padding=ft.padding.only(left=16, right=16, top=8, bottom=4),
                bgcolor=C["bg_dark"],
            ),
            ft.Row([nav, ft.VerticalDivider(width=1, color=C["border"]),
                    ft.Container(self.main, expand=True)], expand=True),
        ], spacing=0, expand=True))

    def _switch(self, e):
        idx = e.control.selected_index
        self.main.controls.clear()
        self.main.controls.append(self.views[idx])
        self.page.update()

    def toast(self, msg, c=C["success"]):
        self.page.snack_bar = ft.SnackBar(ft.Text(msg, color=ft.Colors.WHITE), bgcolor=c, duration=3000)
        self.page.snack_bar.open = True
        self.page.update()

    def err(self, msg):
        self.toast(str(msg), C["error"])

    def _run(self, work, after=None):
        self.loading.visible = True
        self._set_status("处理中...")
        def wrapper():
            try:
                res = work()
                if after:
                    self.page.run_thread(lambda r=res: after(r))
            except Exception as err:
                _err = err
                self.page.run_thread(lambda e=_err: self.err(f"{type(e).__name__}: {e}"))
            finally:
                self.page.run_thread(lambda: setattr(self.loading, "visible", False))
                self.page.run_thread(lambda: self._set_status("就绪") if self.status_text.value == "处理中..." else None)
        threading.Thread(target=wrapper, daemon=True).start()

    def _set_status(self, s):
        self.status_text.value = s
        self.page.update()

    def _card(self, icon, title, body):
        return ft.Container(
            ft.Column(spacing=8, controls=[
                ft.Row([ft.Icon(icon, color=C["accent"], size=18) if icon else ft.Container(),
                        ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=C["text"])], spacing=8)
            ] + ([body] if body else [])),
            padding=16, bgcolor=C["bg_card"], border_radius=8, margin=ft.margin.only(bottom=8),
        )

    def _stat_card(self, container, fields, rows, title, total):
        col_count = len(fields)
        col_width = max(120, 600 // col_count)
        PAGE_SZ = 10
        total_rows = len(rows)
        pn = max(1, (total_rows + PAGE_SZ - 1) // PAGE_SZ)
        page = [0]; start = 0; end = min(PAGE_SZ, total_rows)
        header_row = ft.Row(
            [ft.Container(ft.Text(h, size=11, weight=ft.FontWeight.BOLD, color=C["text_muted"],
                    text_align=ft.TextAlign.CENTER), width=col_width, padding=5)
             for h in fields],
            spacing=2, alignment=ft.MainAxisAlignment.CENTER
        )
        def make_rows(s, e):
            return [ft.Row(
                [ft.Container(ft.Text(str(r.get(h, "")), size=12, color=C["text"], weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER), width=col_width, padding=5)
                 for h in fields],
                spacing=2, alignment=ft.MainAxisAlignment.CENTER
            ) for r in rows[s:e]]
        body = ft.Column([header_row] + make_rows(0, end), spacing=4)
        pi = ft.Text(f"第1页/共{pn}页  {start+1}-{end}条/共{total_rows}条", size=11, color=C["text_muted"])
        btn_prev = ft.IconButton(ft.Icons.NAVIGATE_BEFORE, icon_size=16, tooltip="上一页",
            on_click=lambda e: go(-1), disabled=True)
        btn_next = ft.IconButton(ft.Icons.NAVIGATE_NEXT, icon_size=16, tooltip="下一页",
            on_click=lambda e: go(1), disabled=(end>=total_rows))
        def go(delta):
            page[0] += delta
            s = page[0] * PAGE_SZ; e = min(s + PAGE_SZ, total_rows)
            body.controls = [header_row] + make_rows(s, e)
            pi.value = f"第{page[0]+1}页/共{pn}页  {s+1}-{e}条/共{total_rows}条"
            btn_prev.disabled = (page[0] == 0); btn_next.disabled = (e >= total_rows)
            pi.update(); btn_prev.update(); btn_next.update(); body.update()
        card = ft.Container(
            ft.Column([
                ft.Row([ft.Container(expand=True), ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=C["text"])]),
                ft.Row([pi, ft.Container(expand=True), btn_prev, btn_next], spacing=4),
                body,
            ], spacing=6),
            bgcolor=C["bg_card"], border=ft.border.all(1, C["border"]),
            border_radius=10, padding=12, margin=ft.margin.only(bottom=6))
        container.controls.append(card)

    PAGE_SIZE = 10

    def _tbl_widget(self, fields, rows, h=300):
        if not fields or not rows:
            return ft.Container(ft.Text("无数据", color=C["text_muted"]), padding=10)
        total = len(rows)
        PAGE_SZ = self.PAGE_SIZE
        page = [0]
        pn = max(1, (total + PAGE_SZ - 1) // PAGE_SZ)
        start = 0; end = min(PAGE_SZ, total)
        cols = [ft.DataColumn(ft.Text(c[:15], size=10, weight=ft.FontWeight.BOLD, color=C["accent"])) for c in fields]

        def make_dt(s, e):
            dr = [ft.DataRow([ft.DataCell(ft.Text(str(r.get(f,""))[:40], size=10, color=C["text"])) for f in fields]) for r in rows[s:e]]
            return ft.DataTable(columns=cols, rows=dr, bgcolor=C["bg_card"], border=ft.border.all(1,C["border"]),
                heading_row_color=C["bg_dark"], heading_row_height=28, data_row_max_height=22)

        dt = make_dt(0, end)
        pi = ft.Text(f"第1页/共{pn}页  {start+1}-{end}条/共{total}条", size=11, color=C["text_muted"])
        btn_prev = ft.IconButton(ft.Icons.NAVIGATE_BEFORE, icon_size=16, tooltip="上一页",
            on_click=lambda e: go(-1), disabled=True)
        btn_next = ft.IconButton(ft.Icons.NAVIGATE_NEXT, icon_size=16, tooltip="下一页",
            on_click=lambda e: go(1), disabled=(end>=total))

        def go(delta):
            page[0] += delta
            s = page[0] * PAGE_SZ
            e = min(s + PAGE_SZ, total)
            dt2 = make_dt(s, e)
            dt.columns = dt2.columns; dt.rows = dt2.rows
            pi.value = f"第{page[0]+1}页/共{pn}页  {s+1}-{e}条/共{total}条"
            btn_prev.disabled = (page[0] == 0)
            btn_next.disabled = (e >= total)
            pi.update(); btn_prev.update(); btn_next.update(); dt.update()

        return ft.Column([
            ft.Row([pi, ft.Container(expand=True), btn_prev, btn_next], spacing=4),
            ft.Container(dt, height=h, expand=True),
        ], spacing=2)

    def _save(self, key):
        data = self._cache.get(key)
        if not data:
            return self.err("请先查询数据")
        def work():
            from core import export_to_excel, export_inventory_to_excel
            items = data if isinstance(data, list) else [data]
            saved = []
            for item in items:
                if isinstance(item, dict) and item.get("type") == "inventory_export":
                    tmp = export_inventory_to_excel(item.get("data", []), "Inventory")
                else:
                    rows, fields = item.get("rows", []), item.get("fields", [])
                    if not rows: continue
                    tmp = export_to_excel(rows, fields, item.get('file_prefix', key))
                prefix = item.get("file_prefix", key)
                ds = os.path.join(os.path.expanduser("~"), "Desktop")
                os.makedirs(ds, exist_ok=True)
                dst = os.path.join(ds, f"{prefix}.xlsx")
                shutil.copy2(tmp, dst)
                saved.append(os.path.basename(dst))
            if not saved: raise Exception("无数据")
            return saved
        def done(p):
            fnames = ', '.join(p)
            self.toast(f"已保存: {fnames}")
        self._run(work, done)

    # ==================== GI 状态 Tab ====================
    def _gi(self):
        rv = ft.Column(spacing=8, visible=False, scroll=ft.ScrollMode.AUTO)
        refresh_btn = ft.FilledButton("刷新", icon=ft.Icons.REFRESH, style=ft.ButtonStyle(bgcolor=C["accent"]))

        def render(data):
            if not data: return
            rv.controls.clear(); rv.visible = True
            done = data.get("gi_done", False)
            c = C["success"] if done else C["error"]
            t = f"GI {'已完成' if done else '未完成'}"
            ico = ft.Icons.CHECK_CIRCLE if done else ft.Icons.ERROR
            rv.controls.append(ft.Container(
                ft.Row([ft.Icon(ico, color=c), ft.Text(t, size=16, weight=ft.FontWeight.BOLD, color=c)], spacing=8),
                padding=10, bgcolor=ft.Colors.with_opacity(0.1,c), border_radius=8))
            tv = data.get("today_volume", {})
            stats = ft.ResponsiveRow([
                ft.Container(ft.Column([ft.Text(str(tv.get(k,0)),size=20,weight=ft.FontWeight.BOLD,color=cl),
                    ft.Text(lb,size=11,color=C["text_muted"])],spacing=2,horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=10,bgcolor=C["bg_card"],border_radius=8,col={"sm":3})
                for k,lb,cl in [("units","数量",C["accent"]),("cartons","箱数",C["success"]),
                                ("dns","DN",C["warning"]),("pls","PL",C["purple"])]
            ], spacing=8)
            rv.controls.append(self._card(ft.Icons.BAR_CHART, "今日量", stats))
            rv.controls.append(self._card(ft.Icons.ACCESS_TIME, "CMR / GI 时间",
                ft.Row([
                    ft.Column([ft.Text("最后 CMR",size=11,color=C["text_muted"]),
                        ft.Text(str(data.get('max_cmr_time','N/A')),size=14,weight=ft.FontWeight.BOLD,color=C["text"])]),
                    ft.VerticalDivider(color=C["border"]),
                    ft.Column([ft.Text("最后 GI",size=11,color=C["text_muted"]),
                        ft.Text(str(data.get('max_gi_time','N/A')),size=14,weight=ft.FontWeight.BOLD,color=C["text"])]),
                ], spacing=24)))

            def make_stat_table(hd, rs, ec=False, show_pagination=True):
                tc = C["error"] if ec else C["text"]
                col_count = len(hd)
                col_width = max(120, 600 // col_count)
                total = len(rs)
                page = [0]
                PAGE_SZ = 10
                pn = max(1, (total + PAGE_SZ - 1) // PAGE_SZ)
                start = 0; end = min(PAGE_SZ, total)
                header_row = ft.Row(
                    [ft.Container(ft.Text(h, size=11, weight=ft.FontWeight.BOLD, color=C["text_muted"],
                            text_align=ft.TextAlign.CENTER), width=col_width, padding=5)
                     for h in hd],
                    spacing=2, alignment=ft.MainAxisAlignment.CENTER
                )

                def make_rows(s, e):
                    return [ft.Row(
                        [ft.Container(ft.Text(str(r.get(h, "")), size=12, color=tc, weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER), width=col_width, padding=5)
                         for h in hd],
                        spacing=2, alignment=ft.MainAxisAlignment.CENTER
                    ) for r in rs[s:e]]

                body = ft.Column([header_row] + make_rows(0, end), spacing=4)

                if not show_pagination:
                    return ft.Column([header_row] + make_rows(0, total), spacing=4)

                pi = ft.Text(f"第1页/共{pn}页  {start+1}-{end}条/共{total}条", size=11, color=C["text_muted"])
                btn_prev = ft.IconButton(ft.Icons.NAVIGATE_BEFORE, icon_size=16, tooltip="上一页",
                    on_click=lambda e: go(-1), disabled=True)
                btn_next = ft.IconButton(ft.Icons.NAVIGATE_NEXT, icon_size=16, tooltip="下一页",
                    on_click=lambda e: go(1), disabled=(end>=total))

                def go(delta):
                    page[0] += delta
                    s = page[0] * PAGE_SZ
                    e = min(s + PAGE_SZ, total)
                    new_rows = make_rows(s, e)
                    body.controls = [header_row] + new_rows
                    pi.value = f"第{page[0]+1}页/共{pn}页  {s+1}-{e}条/共{total}条"
                    btn_prev.disabled = (page[0] == 0)
                    btn_next.disabled = (e >= total)
                    pi.update(); btn_prev.update(); btn_next.update(); body.update()

                return ft.Column([
                    ft.Row([pi, ft.Container(expand=True), btn_prev, btn_next], spacing=4),
                    body,
                ], spacing=2)
            for k, icon, title, ec in [("summary",ft.Icons.TABLE_CHART,"STSCODE 汇总",False),
                                        ("gi_status",None,"GI 状态统计",False),
                                        ("errors",ft.Icons.ERROR,"GI 错误",True)]:
                rs = data.get(k)
                if rs:
                    h = list(rs[0].keys())
                    rv.controls.append(self._card(icon, title, make_stat_table(h, rs, ec)))

        def refresh(e=None):
            rv.visible = False; rv.controls.clear()
            self._set_status("查询 GI 状态...")
            self.page.update()
            def work():
                from core import query_gi_status
                return query_gi_status(self.db)
            def done(data):
                self._gi_data = data
                render(data)
                self.page.update()
            self._run(work, done)

        refresh_btn.on_click = refresh
        return ft.Column([
            ft.Container(
                ft.Row([ft.Text("GI 状态监控",size=20,weight=ft.FontWeight.BOLD,color=C["text"]),
                        ft.Container(expand=True),refresh_btn]),
                padding=ft.padding.only(left=24, right=24, top=24),
            ),
            ft.Divider(color=C["border"]),
            ft.Container(rv, expand=True, padding=24),
        ], spacing=0, expand=True)
    # ==================== 数据导出 Tab ====================
    def _export(self):
        from core import query_export_data
        ni = ft.TextField(label="数字条件（每行一个）",multiline=True,min_lines=4,max_lines=8,
            hint_text="计划号 / Shipment / Packlist / Run / 箱号", border_color=C["border"], color=C["text"])
        ai = ft.TextField(label="字母条件（每行一个）",multiline=True,min_lines=4,max_lines=8,
            hint_text="物料 / SKU / Access Number", border_color=C["border"], color=C["text"])
        rv = ft.Column(spacing=4, visible=False, scroll=ft.ScrollMode.AUTO)

        def make_card_table(hd, rs, title):
                col_count = len(hd)
                col_width = max(120, 600 // col_count)
                total = len(rs)
                page = [0]
                PAGE_SZ = 10
                pn = max(1, (total + PAGE_SZ - 1) // PAGE_SZ)
                start = 0; end = min(PAGE_SZ, total)
                header_row = ft.Row(
                    [ft.Container(ft.Text(h, size=11, weight=ft.FontWeight.BOLD, color=C["text_muted"],
                            text_align=ft.TextAlign.CENTER), width=col_width, padding=5)
                     for h in hd],
                    spacing=2, alignment=ft.MainAxisAlignment.CENTER
                )

                def make_data_rows(s, e):
                    return [ft.Row(
                        [ft.Container(ft.Text(str(r.get(h, "")), size=12, color=C["text"], weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER), width=col_width, padding=5)
                         for h in hd],
                        spacing=2, alignment=ft.MainAxisAlignment.CENTER
                    ) for r in rs[s:e]]

                data_rows = make_data_rows(0, end)
                pi = ft.Text(f"第1页/共{pn}页  {start+1}-{end}条/共{total}条", size=11, color=C["text_muted"])
                btn_prev = ft.IconButton(ft.Icons.NAVIGATE_BEFORE, icon_size=16, tooltip="上一页",
                    on_click=lambda e: go(-1), disabled=True)
                btn_next = ft.IconButton(ft.Icons.NAVIGATE_NEXT, icon_size=16, tooltip="下一页",
                    on_click=lambda e: go(1), disabled=(end>=total))
                body = ft.Column([header_row] + data_rows, spacing=4)

                def go(delta):
                    nonlocal end
                    page[0] += delta
                    start2 = page[0] * PAGE_SZ
                    end2 = min(start2 + PAGE_SZ, total)
                    new_rows = make_data_rows(start2, end2)
                    body.controls = [header_row] + new_rows
                    pi.value = f"第{page[0]+1}页/共{pn}页  {start2+1}-{end2}条/共{total}条"
                    btn_prev.disabled = (page[0] == 0)
                    btn_next.disabled = (end2 >= total)
                    pi.update(); btn_prev.update(); btn_next.update(); body.update()

                return self._card(None, title, ft.Column([
                    ft.Row([pi, ft.Container(expand=True), btn_prev, btn_next], spacing=4),
                    body,
                ], spacing=2))

        def show(data):
            self._cache['export'] = data; rv.controls.clear(); rv.visible = True
            # data 可能是 list（多结果）或 dict（单结果，向后兼容）
            items = data if isinstance(data, list) else [data]
            has_data = False
            for item in items:
                if item.get("rows"):
                    has_data = True
                    rv.controls.append(make_card_table(item['fields'], item['rows'], item['file_prefix']))
            if not has_data:
                rv.controls.append(ft.Text("无数据", color=C["text_muted"]))
            self.page.update()

        def qn(e):
            c=[x.strip() for x in ni.value.split("\n") if x.strip()]
            if not c: return self.err("请输入数字条件")
            _req_id[0] += 1; rid = _req_id[0]
            rv.visible=False; rv.controls.clear()
            self._run(lambda: query_export_data(self.db, c, []), lambda d: show(d, rid))

        def qa(e):
            c=[x.strip() for x in ai.value.split("\n") if x.strip()]
            if not c: return self.err("请输入字母条件")
            _req_id[0] += 1; rid = _req_id[0]
            rv.visible=False; rv.controls.clear()
            self._run(lambda: query_export_data(self.db, [], c), lambda d: show(d, rid))

        query_area = ft.Column([
            ft.Text("数据导出",size=20,weight=ft.FontWeight.BOLD,color=C["text"]),
            ft.Divider(color=C["border"]),
            ft.ResponsiveRow([ft.Container(ni,col={"sm":12,"md":6}),ft.Container(ai,col={"sm":12,"md":6})]),
            ft.Row([
                ft.FilledButton("数字查询",icon=ft.Icons.SEARCH,on_click=qn,style=ft.ButtonStyle(bgcolor=C["accent"])),
                ft.FilledButton("字母查询",icon=ft.Icons.TEXT_SNIPPET,on_click=qa,style=ft.ButtonStyle(bgcolor=C["success"])),
                ft.OutlinedButton("导出 Excel",icon=ft.Icons.DOWNLOAD,on_click=lambda e:self._save("export"),style=ft.ButtonStyle(color=C["accent"])),
            ], spacing=8, wrap=True),
        ], spacing=12)
        return ft.Column([
            ft.Container(query_area, padding=ft.padding.only(left=24, right=24, top=24)),
            ft.Divider(color=C["border"]),
            ft.Container(rv, expand=True, padding=ft.padding.only(left=24, right=24, bottom=24)),
        ], spacing=0, expand=True)

    # ==================== 标签历史 Tab ====================
    def _label(self):
        from core import query_label_history
        LH = ["查询打印记录","CHECK OPEN WORK","CHECK AUDIT WORK","检查SKU是否是AMINUS",
              "QA解锁?","SO查询","NFC","查询包装信息","RSO","查询历史库位","DP_area_info","Export inventory"]
        dd = ft.Dropdown(label="查询类型", options=[ft.dropdown.Option(t) for t in LH],
                         value=LH[0], border_color=C["border"], color=C["text"], width=300)
        ci = ft.TextField(label="箱号（每行一个）",multiline=True,min_lines=3,max_lines=6,
                          hint_text="每行一个箱号", border_color=C["border"], color=C["text"])
        rv = ft.Column(spacing=4, visible=False, scroll=ft.ScrollMode.AUTO)

        _req_id = [0]
        def show(data, req_id):
            if req_id != _req_id[0]: return
            self._cache['label'] = data; rv.controls.clear(); rv.visible = True
            if data.get("type") == "inventory_export":
                rv.controls.append(ft.Text(f"Export - {data.get('carton','')}", size=14, color=C["text"]))
                tabs=[ft.Tab(text=s.get('sheet_name','')[:15],content=self._tbl_widget(s['fields'],s['rows'])) for s in data.get("data",[])]
                rv.controls.append(ft.Tabs(tabs, selected_index=0))
            else:
                if not data.get("fields") or not data.get("rows"):
                    rv.controls.append(ft.Text("无数据", color=C["text_muted"]))
                else:
                    self._stat_card(rv, data.get('fields',[]), data.get('rows',[]),
                        data.get('query_type',''), data.get('total',0))
            self.page.update()

        def q(e):
            c=[x.strip() for x in ci.value.split("\n") if x.strip()]
            if not c: return self.err("请输入箱号")
            rv.visible=False; rv.controls.clear()
            _req_id[0] += 1; rid = _req_id[0]
            self._run(lambda: query_label_history(self.db, c, dd.value), lambda d: show(d, rid))

        return ft.Column([ft.Container(ft.Column([
            ft.Text("标签历史",size=20,weight=ft.FontWeight.BOLD,color=C["text"]),
            ft.Divider(color=C["border"]), dd, ci,
            ft.Row([
                ft.FilledButton("查询",icon=ft.Icons.SEARCH,on_click=q,style=ft.ButtonStyle(bgcolor=C["accent"])),
                ft.OutlinedButton("导出 Excel",icon=ft.Icons.DOWNLOAD,on_click=lambda e:self._save("label"),style=ft.ButtonStyle(color=C["accent"])),
            ], spacing=8), rv,
        ], spacing=12), padding=24, expand=True)], scroll=ft.ScrollMode.AUTO)

    # ==================== 日期查询 Tab ====================
    def _date(self):
        from core import DATE_QUERY_MAP, query_date_range
        types = list(DATE_QUERY_MAP.keys())
        dd = ft.Dropdown(label="查询类型", options=[ft.dropdown.Option(t) for t in types],
                         value=types[0], border_color=C["border"], color=C["text"], width=350)
        sp = ft.DatePicker(); ep = ft.DatePicker()
        sf = ft.TextField(label="开始日期", hint_text="格式: YYYY-MM-DD",
            border_color=C["border"], color=C["text"], width=200,
            on_change=lambda e: None)
        ef = ft.TextField(label="结束日期", hint_text="格式: YYYY-MM-DD",
            border_color=C["border"], color=C["text"], width=200,
            on_change=lambda e: None)
        rv = ft.Column(spacing=4, visible=False, scroll=ft.ScrollMode.AUTO)

        def ps(e):
            self.page.open(sp)
            # After picker closes, fill in text field
            if sp.value:
                sf.value = sp.value.strftime("%Y-%m-%d")
                self.page.update()
        def pe(e):
            self.page.open(ep)
            if ep.value:
                ef.value = ep.value.strftime("%Y-%m-%d")
                self.page.update()

        _req_id = [0]
        def show(data, req_id):
            if req_id != _req_id[0]: return
            self._cache['date'] = data; rv.controls.clear(); rv.visible = True
            if not data.get("rows"):
                rv.controls.append(ft.Text("无数据", color=C["text_muted"]))
            else:
                self._stat_card(rv, data.get('fields',[]), data.get('rows',[]),
                    data.get('file_prefix',''), data.get('total',0))
            self.page.update()

        def q(e):
            rv.visible=False; rv.controls.clear()
            _req_id[0] += 1; rid = _req_id[0]
            # 直接传字符串，参考初版代码
            s = (sf.value.strip() if sf.value else "") or ""
            e = (ef.value.strip() if ef.value else "") or ""
            query_type = dd.value
            self._run(lambda: query_date_range(self.db, query_type, s, e), lambda d: show(d, rid))

        return ft.Column([ft.Container(ft.Column([
            ft.Text("按日期查询",size=20,weight=ft.FontWeight.BOLD,color=C["text"]),
            ft.Divider(color=C["border"]), dd,
            ft.Row([
                ft.Row([sf,ft.IconButton(ft.Icons.CALENDAR_MONTH,icon_size=20,
                    on_click=ps,icon_color=C["accent"],tooltip="点击选择日期")]),
                ft.Text("至",color=C["text_muted"]),
                ft.Row([ef,ft.IconButton(ft.Icons.CALENDAR_MONTH,icon_size=20,
                    on_click=pe,icon_color=C["accent"],tooltip="点击选择日期")]),
            ], spacing=8, wrap=True),
            ft.Row([
                ft.FilledButton("查询",icon=ft.Icons.SEARCH,on_click=q,style=ft.ButtonStyle(bgcolor=C["accent"])),
                ft.OutlinedButton("导出 Excel",icon=ft.Icons.DOWNLOAD,on_click=lambda e:self._save("date"),style=ft.ButtonStyle(color=C["accent"])),
            ], spacing=8), rv,
        ], spacing=12), padding=24, expand=True)], scroll=ft.ScrollMode.AUTO)

    # ==================== Incident Tab ====================
    def _incident(self):
        tf = ft.TextField(label="标题 *", hint_text="输入标题", border_color=C["border"], color=C["text"])
        df = ft.TextField(label="描述", multiline=True, min_lines=6, hint_text="详细描述", border_color=C["border"], color=C["text"])
        itpl = self._cfg.get("service_now", {}).get("incident_templates", {})
        cats = list(itpl.keys()) if itpl else ["Inquiry / Help", "Incident", "Service Request"]
        cd = ft.Dropdown(label="分类", options=[ft.dropdown.Option(t) for t in cats],
                         value=cats[0] if cats else "Inquiry / Help", border_color=C["border"], color=C["text"], width=300)

        def on_cat_change(e):
            """选择分类时自动填充标题和描述"""
            sn = self._cfg.get("service_now", {})
            tv = cd.value
            if not tv: return
            itmpl = sn.get("incident_templates", {}).get(tv, {})
            if itmpl.get("short_description"):
                tf.value = itmpl["short_description"]
            lines = []
            for k, v in itmpl.items():
                if v and k not in ("access_key",):
                    lines.append(f"{k}: {v}")
            df.value = "\n".join(lines)
            self.page.update()

        cd.on_change = on_cat_change
        rv = ft.Column(spacing=4, visible=False, scroll=ft.ScrollMode.AUTO)

        def sub(e):
            if not tf.value: return self.err("请输入标题")
            rv.controls.clear(); rv.visible = False
            def work():
                import requests
                sn = self._cfg.get("service_now", {})
                payload = {"short_description": tf.value, "description": df.value or "","category": cd.value, "assignment_group": ""}
                for ck, defaults in sn.get("incident_templates", {}).items():
                    if ck.lower() in cd.value.lower() or ck.lower() in tf.value.lower():
                        for k,v in defaults.items():
                            if k not in payload or not payload[k]: payload[k]=v
                for url in [sn.get("url_create"), sn.get("url_create_backup")]:
                    if not url: continue
                    r = requests.post(url, headers={"Accept":"*/*","Content-type":"application/json"},
                                      auth=(sn.get('username',''),sn.get('password','')),
                                      json=payload, timeout=30)
                    if r.status_code in (200,201):
                        return {"ok": True, "num": r.json().get('number','N/A')}
                raise Exception("ServiceNow 所有URL均失败")
            def done(ret):
                rv.controls.append(ft.Container(
                    ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE,color=C["success"]),
                            ft.Text(f"✅ {ret.get('num','')} 创建成功!",color=C["success"],size=14)]),
                    padding=12, bgcolor=ft.Colors.with_opacity(0.1,C["success"]), border_radius=8))
                rv.visible = True; self.page.update()
            self._run(work, done)

        return ft.Column([ft.Container(ft.Column([
            ft.Text("创建 Incident",size=20,weight=ft.FontWeight.BOLD,color=C["text"]),
            ft.Divider(color=C["border"]), tf, df, cd,
            ft.FilledButton("提交",icon=ft.Icons.ADD_CIRCLE,on_click=sub,style=ft.ButtonStyle(bgcolor=C["accent"])), rv,
        ], spacing=12), padding=24, expand=True)], scroll=ft.ScrollMode.AUTO)
    # ==================== 工作台 Tab ====================
    def _workbench(self):
        sql_input = ft.TextField(
            label="SQL 输入 / 用户条件（每行一个）", multiline=True, min_lines=8, max_lines=16,
            hint_text="在此输入 SQL 语句 或 要删除/添加的用户条件...", border_color=C["border"], color=C["text"], expand=True,
        )
        log_view = ft.Column(controls=[], spacing=1, scroll=ft.ScrollMode.AUTO)
        log_box = ft.Container(log_view, height=200, bgcolor="#0f172a", border_radius=4, padding=8)

        def wb_log(msg, c=C["text"]):
            log_view.controls.append(ft.Row([
                ft.Text(f"[{datetime.now().strftime('%H:%M:%S')}]", size=10, color=C["text_muted"]),
                ft.Text(str(msg), size=11, color=c, selectable=True),
            ], spacing=4))
            if len(log_view.controls) > 100:
                log_view.controls = log_view.controls[-50:]
            self.page.update()

        def txt(): return sql_input.value or ""

        # === 1. 清屏 ===
        def cmd_clear(e):
            sql_input.value = ""; sql_input.update()
            wb_log("清屏完成", C["success"])

        # === 2. 格式化SQL ===
        def cmd_format(e):
            t = txt()
            if not t.strip(): return wb_log("SQL 为空", C["warning"])
            pattern = r"\b(?<![ctxprwdta.])\w{2}[rRwW]\w{3}\b"
            result = re.sub(pattern, lambda m: "ctxprwdta." + m.group(0), t)
            sql_input.value = result; sql_input.update()
            wb_log("格式化完成 (已添加 ctxprwdta. 前缀)", C["success"])



        # === 4. Delete Voice User (Selenium) ===
        def cmd_delete(e):
            vals = [x.strip() for x in txt().split("\n") if x.strip()]
            if not vals: return wb_log("输入用户条件（每行一个）", C["warning"])
            wb_log(f"删除 {len(vals)} 个用户...", C["accent"])
            def work():
                try:
                    from selenium import webdriver
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.support.ui import WebDriverWait
                    from selenium.webdriver.support import expected_conditions as EC
                    from selenium.webdriver.common.keys import Keys
                    vc = self._cfg.get("voice_console", {})
                    ops = webdriver.ChromeOptions()
                    ops.add_experimental_option("prefs", {"credentials_enable_service":False})
                    ops.add_argument("--disable-blink-features=AutomationControlled")
                    ops.add_experimental_option("excludeSwitches", ['enable-automation'])
                    ops.add_argument("--no-sandbox")
                    drv = webdriver.Chrome(options=ops)
                    drv.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    w = WebDriverWait(drv, 10)
                    drv.get("http://tcgiapp1wapp013:9090/VoiceConsole/login.action")
                    drv.maximize_window()
                    # 定位登录表单元素 (原版 pattern)
                    username = w.until(EC.presence_of_element_located((By.NAME, "j_username")))
                    password = w.until(EC.presence_of_element_located((By.NAME, "j_password")))
                    username.send_keys(vc.get("username", ""))
                    password.send_keys(vc.get("password", ""))
                    password.submit()
                    time.sleep(1)
                    drv.get("http://tcgiapp1wapp013:9090/VoiceConsole/core/search/result.action")
                    time.sleep(1)
                    ok = 0
                    for i, v in enumerate(vals):
                        try:
                            inp = drv.find_element(By.CSS_SELECTOR, "input[type='text']")
                            inp.clear(); inp.send_keys(v); inp.send_keys(Keys.RETURN)
                            time.sleep(0.8)
                            body = drv.find_element(By.TAG_NAME,"body").text
                            if "没有得到任何结果" in body:
                                wb_log(f"  [{i+1}/{len(vals)}] {v} -> 无结果")
                                continue
                            for t in ["a","span","div","td"]:
                                els = drv.find_elements(By.XPATH,f"//{t}[contains(text(),'{v}')]")
                                for el in els:
                                    try:
                                        if el.is_displayed(): el.click(); break
                                    except: continue
                                else: continue
                                break
                            time.sleep(0.3)
                            delete_found = False
                            for s in ["//*[contains(text(),'删除此操作员')]","//button[contains(text(),'删除')]","//a[contains(text(),'删除')]"]:
                                try:
                                    b = drv.find_element(By.XPATH,s)
                                    if b.is_displayed(): b.click(); delete_found = True; break
                                except: continue
                            if not delete_found:
                                wb_log(f"  [{i+1}/{len(vals)}] {v} -> 无法找到删除按钮", C["error"])
                                continue
                            time.sleep(0.2)
                            confirmed = False
                            for s in ["//*[contains(text(),'是，删除操作员')]","//button[contains(text(),'是')]"]:
                                try:
                                    b = drv.find_element(By.XPATH,s)
                                    if b.is_displayed(): b.click(); confirmed = True; break
                                except: continue
                            time.sleep(0.4)
                            if confirmed:
                                ok += 1
                                wb_log(f"  [{i+1}/{len(vals)}] {v} -> ok", C["success"])
                            else:
                                wb_log(f"  [{i+1}/{len(vals)}] {v} -> 无法找到确认删除按钮", C["error"])
                        except Exception as ex:
                            wb_log(f"  [{i+1}/{len(vals)}] {v} -> fail: {ex}", C["error"])
                    drv.quit()
                    return {"ok": ok, "total": len(vals)}
                except ImportError:
                    return {"error": "需要安装 selenium"}
                except Exception as ex:
                    return {"error": str(ex)}
            def done(ret):
                if "error" in ret:
                    wb_log(f"错误: {ret['error']}", C["error"])
                else:
                    wb_log(f"ok: {ret['ok']}/{ret['total']} 已删除", C["success"])
            self._run(work, done)
        # === 5. Health Check (初版代码) ===
        def cmd_health(e):
            wb_log("Health Check 启动...", C["accent"])
            wb_log("请确保已切换到 AS400 5250 终端窗口", C["warning"])
            def work():
                try:
                    import pyautogui, pyperclip, docx
                    from PIL import Image
                    import easygui
                    import glob, shutil, tempfile
                    hc = self._cfg.get("health_check", {})
                    choice = easygui.buttonbox(
                        msg="请切换到AS400 Command Entry界面并确认翻页快捷键已设置!!",
                        title="确认", choices=["OK", "Cancel"])
                    if choice == "Cancel" or choice is None:
                        return {"msg": "用户取消"}
                    time.sleep(2)
                    # create pictures folder
                    def create_pictures_folder():
                        # 创建 pictures 文件夹（如果不存在）
                        if not os.path.exists('pictures'):
                            os.makedirs('pictures')
                        else:
                            files = glob.glob('pictures/*')
                            for f in files:
                                if os.path.isfile(f):
                                    os.remove(f)

                    # copy_page_text
                    def copy_page_text():
                        # 全选并复制当前页面的文字
                        pyautogui.hotkey('ctrl', 'a')
                        pyautogui.hotkey('ctrl', 'c')
                        # 获取剪贴板上的文本
                        clipboard_text = pyperclip.paste()
                        # 将文本写入临时文件
                        with tempfile.NamedTemporaryFile(mode='w+', delete=False,encoding="utf - 8") as temp_file:
                            temp_file.write(clipboard_text)
                            temp_file.flush()
                            # 返回临时文件的名称
                            return temp_file.name
                    # add_screenshot_to_word
                    def add_screenshot_to_word(screenshot_path, doc):
                        # 将图片添加到 Word 文档中
                        doc.add_picture(screenshot_path, width=docx.shared.Inches(4.9),height =docx.shared.Inches(3.0))

                    # create_screenshots
                    def create_screenshots(job_name,page,doc=None): 
                            global should_copy_text           
                            # 初始化 job 的起始位置和结束位置
                            job_start_y = 100  # 假设 job 起始于屏幕顶部
                            job_height = 980   # 假设每个 job 高度为 100 像素
                            sheet_name = job_name.replace(' ', '_')[:31]  # Excel 工作表名不能超过 31 个字符     
                            # 复制当前页面的文字
                            if should_copy_text:
                                temp_file_name = copy_page_text()
                                with open(temp_file_name, 'r',encoding="utf - 8") as temp_file:
                                     temp_file.read()
                                # 删除临时文件
                                os.remove(temp_file_name)
                            # 截取 job 区域并调整大小后保存到 Excel
                            screenshot = pyautogui.screenshot(region=(0, job_start_y, pyautogui.size().width, job_height))
                            # 调整图片大小
                            screenshot = screenshot.resize((screenshot.width // 2, screenshot.height // 2), Image.Resampling.LANCZOS)
                            screenshot_path = os.path.join('pictures', f'screenshot_{sheet_name}_{page}.png')
                            # 保存图片时设置质量
                            screenshot.save(screenshot_path, optimize=True, quality=60)  # 优化并设置质量
                            # 将图片添加到 Word 文档中
                            if doc is not None:
                                add_screenshot_to_word(screenshot_path, doc)
                            time.sleep(1)


                    # take_screenshots
                    def take_screenshots(jobs):
                        for job_name in jobs:
                            page = 1

                            if job_name=='STRSQL':
                                #输入命令
                                pyautogui.press('tab')
                                pyautogui.typewrite(job_name)
                                pyautogui.press('enter')

                                #输入F14=Confirm
                                pyautogui.keyDown('shift')
                                pyautogui.press('f2')
                                pyautogui.press('tab')
                                pyautogui.keyUp('shift')
                                #截图并退到命令行界面
                                doc.add_paragraph(f"1.check if system can login or not (both job role menu and STRSQL menu)两张")
                                time.sleep(0.5)
                                create_screenshots(job_name,page,doc)
                                pyautogui.press('f12')
                                pyautogui.press('enter')

                            if job_name=='XPDS CTXPR':
                                #输入命令并进到JOBROLE界面
                                pyautogui.press('tab')
                                pyautogui.typewrite(job_name)
                                pyautogui.press('enter')
                                pyautogui.press('enter')

                                #截图并退到命令行界面
                                time.sleep(0.5)
                                create_screenshots(job_name,page,doc)
                                pyautogui.press('f3')

                            if job_name=='WRKMQM':
                                #输入命令
                                pyautogui.press('tab')
                                pyautogui.typewrite(job_name)
                                pyautogui.press('enter')

                                #截图并退到命令行界面
                                doc.add_paragraph(f"4.check MQ 第一页(WRKMQM)")
                                time.sleep(0.5)
                                create_screenshots(job_name,page,doc)
                                pyautogui.press('f3')

                            if job_name=='WRKACTJOB SBS(CTXPRCDC)':
                                #输入命令
                                pyautogui.press('tab')
                                pyautogui.typewrite(job_name)
                                pyautogui.press('enter')
                                pyautogui.press('f7')
                                pyautogui.typewrite('XPDSN')
                                pyautogui.press('enter')
                                time.sleep(0.5)
                                #截图并退到命令行界面
                                doc.add_paragraph(f"WRKACTJOB SBS(CTXPRCDC):")
                                time.sleep(0.5)
                                create_screenshots(job_name,page,doc)
                                pyautogui.press('f3')

                            if job_name=='DSPFD FILE(SVSDLNA)':
                                #输入命令
                                pyautogui.press('tab')
                                pyautogui.typewrite(job_name)
                                pyautogui.press('enter')

                                #输入B到最后一页
                                pyautogui.typewrite("B")
                                pyautogui.press('enter')
                                time.sleep(1)

                                #截图并退到命令行界面
                                doc.add_paragraph(f"7.DSPFD FILE(SVSDLNA) 最后一页")
                                time.sleep(0.5)
                                create_screenshots(job_name,page,doc)
                                pyautogui.press('f3')

                            if job_name=='DSPMSG MSGQ(*SYSOPR) SEV(99)':
                                #输入命令            
                                pyautogui.press('tab')
                                pyautogui.typewrite(job_name)
                                pyautogui.press('enter')
                                time.sleep(2)

                                #截图并退到命令行界面
                                doc.add_paragraph(f"9.DSPMSG MSGQ(*SYSOPR) SEV(99):")
                                time.sleep(0.5)
                                create_screenshots("SYSOPR",page,doc)
                                pyautogui.press('f3')

                            if job_name=='DSPMSG MSGQ(CTXPRWSCD) SEV(99)':
                                #输入命令
                                pyautogui.press('tab')
                                pyautogui.typewrite(job_name)
                                pyautogui.press('enter')
                                time.sleep(5)

                                #截图并退到命令行界面
                                doc.add_paragraph(f"DSPMSG MSGQ(CTXPRWSCD) SEV(99)")
                                time.sleep(0.5)
                                create_screenshots("CTXPRWSCD",page,doc)
                                pyautogui.press('f3')

                            if job_name=='WRKLNK':
                                #输入命令WRKLNK
                                pyautogui.press('tab')
                                pyautogui.typewrite(job_name)
                                pyautogui.press('enter')
                                time.sleep(0.5)

                                #查找home行并输入5=display
                                for _ in range(7):
                                    pyautogui.press('down')
                                pyautogui.typewrite("5")
                                pyautogui.press('enter')
                                time.sleep(0.5)

                                #查找CHINA行并输入5=display
                                pyautogui.keyDown('ctrl')
                                pyautogui.press('q')
                                pyautogui.keyUp('ctrl')
                                pyautogui.press('down')    
                                pyautogui.typewrite("5")
                                pyautogui.press('enter')
                                time.sleep(0.5)

                                #查找PRD行并输入5=display
                                pyautogui.press('down')    
                                pyautogui.press('down')    
                                pyautogui.typewrite("5")
                                pyautogui.press('enter')
                                time.sleep(0.5)

                                #截图并退到命令行界面
                                doc.add_paragraph(f"8.WRKLNK/home/CHINA/PRD")
                                time.sleep(0.5)
                                create_screenshots(job_name,page,doc)
                                pyautogui.press('f3')
                                pyautogui.press('enter')

                            if job_name=='General Link':
                                #输入命令进入到JOBROLE界面
                                pyautogui.press('tab')
                                pyautogui.typewrite("XPDS CTXPR")
                                pyautogui.press('enter')
                                pyautogui.press('enter')

                                #进入LINK界面
                                pyautogui.typewrite("60")
                                pyautogui.press('enter')
                                pyautogui.typewrite("10")
                                pyautogui.press('enter')
                                pyautogui.typewrite("60")
                                pyautogui.press('enter')
                                pyautogui.typewrite("50")
                                pyautogui.press('enter')
                                pyautogui.typewrite("10")
                                pyautogui.press('enter')
                                #STATUS行输入F
                                for _ in range(3):
                                    pyautogui.press('tab')
                                pyautogui.typewrite("F")
                                time.sleep(0.5)
                                #清空日期和时间并进入结果画面
                                pyautogui.press('tab')
                                pyautogui.press('tab')
                                for _ in range(16):
                                    pyautogui.press('space')
                                pyautogui.press('enter')

                                #截图并退到命令行界面
                                doc.add_paragraph(f"3.check general link have F status or not:")
                                time.sleep(0.5)
                                create_screenshots(job_name,page,doc)
                                pyautogui.press('f3')
                                pyautogui.press('f3')
                                pyautogui.press('enter')

                            if job_name=='WRKACTJOB':

                                #输入命令进入到一览界面
                                pyautogui.press('tab')
                                pyautogui.typewrite(job_name)
                                pyautogui.press('enter')

                                #到达STATUS列并排序
                                for _ in range(63):
                                    pyautogui.press('right')
                                pyautogui.keyDown('shift')
                                pyautogui.press('f4')
                                pyautogui.keyUp('shift')

                                #查找ROBOTREACT
                                pyautogui.press('f7')
                                pyautogui.typewrite("MSGW")
                                pyautogui.press('tab')
                                pyautogui.typewrite("*STS")
                                pyautogui.press('enter')
                                paragraph = doc.add_paragraph()
                                paragraph.add_run(f"6.wrkactjob check MSGW job\nWRKACTJOB:")
                                time.sleep(0.5)
                                create_screenshots(job_name,page,doc)
                                page += 1

                                pyautogui.press('f3')

                            if job_name=='WATCHDOG':
                                #输入命令进入JOBROLE界面
                                pyautogui.press('tab')
                                pyautogui.typewrite("XPDS CTXPR")
                                pyautogui.press('enter')
                                pyautogui.press('enter')

                                #进入WATCHDOG界面
                                pyautogui.typewrite("60")
                                pyautogui.press('enter')
                                pyautogui.typewrite("110")
                                pyautogui.press('enter')
                                pyautogui.typewrite("20")
                                pyautogui.press('enter')
                                pyautogui.typewrite("50")
                                pyautogui.press('enter')

                                #对象DOG输入13
                                pyautogui.press('tab')
                                pyautogui.typewrite("13")
                                pyautogui.press('tab')
                                pyautogui.press('tab')
                                for _ in range(6):
                                    pyautogui.typewrite("13")
                                pyautogui.press('enter')

                                #截图
                                page_down_count = 0
                                f12_count = 1
                                first_screenshot_after_f12 = True
                                for page_down_count in range(0,14):
                                    #第一页截图
                                    if page_down_count == 0:
                                       doc.add_paragraph(f"2.check WD CTXPRILM:两张")
                                       time.sleep(0.5)
                                       create_screenshots(job_name,page,doc)
                                       page += 1

                                    #判读是否能翻页
                                    if page_down_count <=14:
                                        pyautogui.keyDown('ctrl')
                                        pyautogui.press('q')
                                        pyautogui.keyUp('ctrl')
                                        page_down_count += 1

                                    #翻页后如果是截图界面则截图
                                    if page_down_count in [1 , 3 , 7 , 8 , 13 , 14] :
                                        time.sleep(0.5)
                                        create_screenshots(job_name,page,doc)
                                        page += 1

                                    #判断翻页后是否可以按F12跳转到下一个WATCHDOG
                                    if page_down_count in [1 , 3 , 8 , 13 , 14] :
                                        pyautogui.press('f12')
                                        if first_screenshot_after_f12:
                                            # 根据 f12_count 添加不同的文字
                                            if f12_count == 1:
                                                doc.add_paragraph(f"CTXPRIML:2张")
                                            elif f12_count == 2:
                                                doc.add_paragraph(f"CTXPRIMM:3张,第一和最后两张")
                                            elif f12_count == 3:
                                                doc.add_paragraph(f"CTXPRIMP:2张(第一和最后一张)")
                                            elif f12_count == 4:
                                                doc.add_paragraph(f"CTXPRIMS:2张")
                                            elif f12_count == 5:
                                                doc.add_paragraph(f"CTXPRIMV:第一页")
                                            first_screenshot_after_f12 = False
                                        #F12跳转后截图并判断是否是最后一个WATCHDOG
                                        if (f12_count <= 5):
                                            first_screenshot_after_f12 = True
                                            time.sleep(0.5)
                                            create_screenshots(job_name,page,doc)
                                            page += 1
                                            f12_count += 1

                                        if (f12_count == 6):
                                            pyautogui.press('f12')
                                            doc.add_paragraph(f"CTXPRWMO 1张") 
                                            time.sleep(0.5)
                                            create_screenshots(job_name,page,doc)

                                pyautogui.press('f3')
                                pyautogui.press('f3')

                            if job_name=='RBM':

                                #进入RBM界面
                                pyautogui.typewrite(job_name)
                                pyautogui.press('enter')
                                pyautogui.typewrite("1")
                                pyautogui.press('enter')
                                time.sleep(0.5)

                                today = datetime.datetime.now()
                                weekday_num = today.weekday()

                                # #如果当天是周一，则对#WSUN截图
                                # if weekday_num in [0]:
                                #    pyautogui.typewrite("#WSUN")
                                #    pyautogui.press('enter')
                                #    pyautogui.typewrite("11")
                                #    pyautogui.press('enter')
                                #    time.sleep(0.5)
                                #    paragraph = doc.add_paragraph()
                                #    paragraph.add_run(f"5.check daily/weekly/sunday/monthly/CDC job is complete or not\n#WSUN:")
                                #    time.sleep(0.5)
                                #    create_screenshots(job_name,page,doc)
                                #    page += 1
                                #    pyautogui.press('f3')

                                #如果当天是周二到周六，则对#DAILYPR截图
                                if weekday_num in [0,1,2,3,4,5,6]:
                                   pyautogui.typewrite("#DAILYPR")
                                   pyautogui.press('enter')
                                   pyautogui.typewrite("11")
                                   pyautogui.press('enter')
                                   time.sleep(0.5)
                                   paragraph = doc.add_paragraph()
                                   paragraph.add_run(f"5.check daily/weekly/sunday/monthly/CDC job is complete or not\n#DAILYPR:")
                                   time.sleep(0.5)
                                   create_screenshots(job_name,page,doc)
                                   page += 1
                                   pyautogui.press('f3')

                                # #如果当天是周日，则对#WKLY2~5截图
                                # if weekday_num in [6]:
                                #    for var_name in range(2,6):
                                #        pyautogui.typewrite(f"#WKLY{var_name}")
                                #        pyautogui.press('enter')
                                #        time.sleep(0.5)

                                #        pyautogui.typewrite("11")
                                #        pyautogui.press('enter')
                                #        time.sleep(0.5)
                                #        paragraph = doc.add_paragraph()
                                #        paragraph.add_run(f"5.check daily/weekly/sunday/monthly/CDC job is complete or not\n#WKLY{var_name}")
                                #        time.sleep(0.5)
                                #        create_screenshots(job_name,page,doc)
                                #        page += 1
                                #        pyautogui.press('f3')

                                #        pyautogui.press('f3')
                                #        pyautogui.typewrite("1")
                                #        pyautogui.press('enter')
                                #        time.sleep(0.5)

                                #CTXPRG_STR截图
                                pyautogui.press('f3')
                                pyautogui.typewrite("1")
                                pyautogui.press('enter')
                                pyautogui.typewrite("CTXPRG_STR")
                                pyautogui.press('enter')
                                pyautogui.typewrite("11")
                                pyautogui.press('enter')
                                time.sleep(0.5)
                                doc.add_paragraph(f"CTXPRG_STR:")
                                time.sleep(0.5) 
                                create_screenshots(job_name,page,doc)
                                pyautogui.press('f3')

                                pyautogui.press('f3')
                                pyautogui.press('f3')

                    # open_and_screenshot
                    def open_and_screenshot():
                        # 设置浏览器选项 - 提高性能
                          options = webdriver.ChromeOptions()
                          options.add_experimental_option("prefs", {
                          # 禁用密码保存提示
                          "credentials_enable_service": False,
                          "profile.password_manager_enabled": False,
                          })
                          options.add_argument('--disable-blink-features=AutomationControlled')
                          options.add_experimental_option("excludeSwitches", ["enable-automation"])
                          options.add_experimental_option('useAutomationExtension', False)
                          options.add_argument('--disable-extensions')
                          options.add_argument('--no-sandbox')
                          options.add_argument('--disable-dev-shm-usage')
                          options.add_argument('--disable-gpu')

                          # 设置浏览器驱动
                          driver_path=None
                          if driver_path:
                               driver = webdriver.Chrome(executable_path=driver_path, options=options)
                          else:
                               driver = webdriver.Chrome(options=options)

                      # 隐藏自动化特征
                          driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                          global should_copy_text
                          should_copy_text = False
                          try:
                              # 打开指定网址
                              driver.maximize_window()
                              driver.get("http://tcgiapp1wapp013:9090/VoiceConsole/login.action")
                              # 使用显式等待替代固定等待
                              wait = WebDriverWait(driver, 10)
                              # 定位登录表单元素
                              username = wait.until(EC.presence_of_element_located((By.NAME, "j_username")))  # 根据实际元素属性修改
                              password = wait.until(EC.presence_of_element_located((By.NAME, "j_password")))  # 根据实际元素属性修改

                              # 直接使用Selenium输入
                              username.send_keys("admin")
                              password.send_keys("admin")
                              password.submit()  # 自动提交表单
                              # 等待页面加载
                              time.sleep(3)
                              # 获取页面截图
                              paragraph = doc.add_paragraph()
                              paragraph.add_run(f"10.check Voice web\nhttp://tcgiapp1wapp013:9090/VoiceConsole/login.action")
                              time.sleep(0.5)
                              create_screenshots("Honeywell",1,doc)

                              driver.get("https://techops-clcps.nike.com/#/dashboard")
                              time.sleep(1)
                               # 定位新网站的登录元素
                              nike_user = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@class='el-input__inner' and @placeholder='用户名 / 手机 / 邮箱']")))

                            # 根据实际元素属性修改
                              nike_pass = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@class='el-input__inner' and @placeholder='请输入密码']")))
                      # 根据实际元素属性修改
                              nike_user.send_keys("PS1")
                              nike_pass.send_keys("Pspspsps1")
                              wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='登录']/ancestor::button[contains(@class,'el-button--primary')]"))).click()
                              time.sleep(3)
                              # 获取页面截图
                              paragraph = doc.add_paragraph()
                              paragraph.add_run(f"11.check EPS server(first lic server TCGWMSP1WEPS003)\n远程用户/密码\nEe*GC7qz\n\nTCGWMSP1WEPS003\n\n12.https://techops-clcps.nike.com/#/dashboard")
                              time.sleep(0.5)
                              create_screenshots("dashboard",1,doc)

                              x, y = 900, 700
                              pyautogui.moveTo(x, y, duration=3)
                              time.sleep(0.5)
                              pyautogui.click()
                              time.sleep(2)
                              # 获取页面截图
                              time.sleep(0.5)
                              create_screenshots("dashboard",2,doc)
                          except Exception:
                              print("we can't open this path")
                          finally:
                            # 关闭浏览器
                            driver.close()

                          try:
                              path = r"\\tcpsappd1ap01\deploy\backend\log-app.log"
                              os.startfile(path)
                              time.sleep(5)
                              pyautogui.hotkey('ctrl','end')
                              time.sleep(3)
                              paragraph = doc.add_paragraph()
                              paragraph.add_run(f"13.\\tcpsappd1ap01\deploy\ backend\log-app.log\n查看这个log文件内容是否是最近5分钟之内更新的")
                              time.sleep(0.5)
                              create_screenshots("log",1,doc)
                              time.sleep(3)
                              pyautogui.hotkey('ctrl','W')
                          except Exception:
                              print("we can't open this path")
                          easygui.msgbox("截图结束！请检查结果！！！")

                    should_copy_text = True
                    current_date = dt.now().strftime("%m%d")
                    word_doc_path = f"{current_date}.docx"
                    doc = docx.Document()


                    # Global vars + call health_check
                    should_copy_text = True
                    current_date = datetime.now().strftime("%m%d")
                    word_doc_path = os.path.join(os.path.expanduser("~"), "Desktop", f"{current_date}.docx")
                    doc = docx.Document()
                    def health_check():
                        choice = easygui.buttonbox(
                            msg="请切换到AS400 Command Entry界面并确认翻页快捷键已设置!!",
                            title="确认",
                            choices=["OK", "Cancel"]
                        )

                        # 如果用户点击了 Cancel 或关闭了弹窗，则终止函数
                        if choice == "Cancel" or choice is None:
                            return

                        time.sleep(2)
                        jobs = [
                            "STRSQL",
                            "XPDS CTXPR",
                            "WATCHDOG",
                            "General Link",
                            "WRKMQM",
                            "RBM",
                            "WRKACTJOB SBS(CTXPRCDC)",
                            "WRKACTJOB",
                            "DSPFD FILE(SVSDLNA)",
                            "WRKLNK",
                            "DSPMSG MSGQ(*SYSOPR) SEV(99)",
                            "DSPMSG MSGQ(CTXPRWSCD) SEV(99)"
                        ]
                        # AS400截图
                        # 创建pictures文件夹
                        create_pictures_folder()  
                        take_screenshots(jobs)
                        # 网页截图
                        open_and_screenshot()  
                        # 关闭DOC
                        doc.save(word_doc_path)
                        shutil.rmtree('pictures')

                    doc.save(word_doc_path)
                    shutil.rmtree("pictures", ignore_errors=True)
                    easygui.msgbox("截图结束！请检查结果！！！")
                    return {"msg": f"已完成, 报告: {word_doc_path}"}
                except ImportError as ex:
                    return {"error": f"需要安装依赖: {ex}. pip install pyautogui pyperclip python-docx Pillow easygui selenium"}
                except Exception as ex:
                    import traceback; return {"error": str(ex) + "\n" + traceback.format_exc()}
            def done(ret):
                if "error" in ret:
                    wb_log(f"Health Check 错误: {ret['error']}", C["error"])
                elif "msg" in ret:
                    wb_log(f"Health Check {ret['msg']}", C["success"])
            self._run(work, done)        # === 6. Add Voice User (Selenium + Excel) ===
        def cmd_add(e):
            wb_log("Add Voice User: 从 data.xlsx 读取...", C["accent"])
            def work():
                try:
                    import pandas as pd
                    from selenium import webdriver
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.support.ui import WebDriverWait, Select
                    from selenium.webdriver.support import expected_conditions as EC
                    vc = self._cfg.get("voice_console", {})
                    xp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.xlsx")
                    if not os.path.exists(xp):
                        return {"error": f"data.xlsx 不存在（放程序同目录）: {xp}"}
                    df = pd.read_excel(xp, header=None)
                    recs = []
                    for _, row in df.iterrows():
                        if len(row)>=2:
                            c1=str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
                            c2=str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
                            if c1 and c2: recs.append([c1,c2])
                    if not recs:
                        return {"error": "Excel 空或格式不对"}
                    wb_log(f"  读取 {len(recs)} 条")
                    ops = webdriver.ChromeOptions()
                    ops.add_experimental_option("prefs",{"credentials_enable_service":False})
                    ops.add_argument("--disable-blink-features=AutomationControlled")
                    drv = webdriver.Chrome(options=ops)
                    drv.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    drv.get("http://tcgiapp1wapp013:9090/VoiceConsole/login.action")
                    drv.maximize_window()
                    w = WebDriverWait(drv, 10)
                    username = w.until(EC.presence_of_element_located((By.NAME, "j_username")))
                    password = w.until(EC.presence_of_element_located((By.NAME, "j_password")))
                    username.send_keys(vc.get("username", ""))
                    password.send_keys(vc.get("password", ""))
                    password.submit()
                    time.sleep(1)
                    drv.get("http://tcgiapp1wapp013:9090/VoiceConsole/core/operator/list.action")
                    time.sleep(1)
                    create_btn = w.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'创建新操作员')]")))
                    create_btn.click()
                    time.sleep(1)
                    ok = dup = err = 0
                    for idx, rec in enumerate(recs):
                        name, oid = rec[0], rec[1]
                        try:
                            name_f = w.until(EC.presence_of_element_located((By.NAME,"operator.name")))
                            name_f.clear(); name_f.send_keys(str(name))
                            drv.find_element(By.NAME,"operator.operatorFuncId").clear();
                            drv.find_element(By.NAME,"operator.operatorFuncId").send_keys(str(oid))
                            drv.find_element(By.NAME,"operator.spokenName").clear();
                            drv.find_element(By.NAME,"operator.spokenName").send_keys(str(oid))
                            try:
                                cb = drv.find_element(By.XPATH,"//input[@type='checkbox' and @value='DEFAULT']")
                                if not cb.is_selected(): cb.click()
                            except: pass
                            drv.find_element(By.XPATH,"//button[@type='submit']").click()
                            time.sleep(1)
                            body = drv.find_element(By.TAG_NAME,"body").text
                            if "已经存在" in body or "already exists" in body.lower():
                                dup += 1
                                wb_log(f"  [{idx+1}/{len(recs)}] {name}({oid}) -> 已存在", C["warning"])
                            else:
                                ok += 1
                                wb_log(f"  [{idx+1}/{len(recs)}] {name}({oid}) -> ok", C["success"])
                            drv.get("http://tcgiapp1wapp013:9090/VoiceConsole/core/operator/list.action")
                            time.sleep(1)
                            w.until(EC.element_to_be_clickable((By.XPATH,"//a[contains(text(),'创建新操作员')]"))).click()
                            time.sleep(1)
                        except Exception as ex:
                            err += 1
                            wb_log(f"  [{idx+1}/{len(recs)}] {name}({oid}) -> fail: {ex}", C["error"])
                    drv.quit()
                    return {"ok": ok, "dup": dup, "err": err, "total": len(recs)}
                except ImportError:
                    return {"error": "需要安装 selenium pandas"}
                except Exception as ex:
                    return {"error": str(ex)}
            def done(ret):
                if "error" in ret:
                    wb_log(f"错误: {ret['error']}", C["error"])
                else:
                    wb_log(f"ok: {ret['ok']} ok / {ret['dup']} dup / {ret['err']} err (共{ret['total']})", C["success"])
            self._run(work, done)
        # Button bar
        btn_row = ft.Row(spacing=6, wrap=True, controls=[
            ft.FilledButton("清屏", icon=ft.Icons.CLEAR_ALL, on_click=cmd_clear, style=ft.ButtonStyle(bgcolor=C["accent"])),
            ft.OutlinedButton("格式化SQL", icon=ft.Icons.CODE, on_click=cmd_format, style=ft.ButtonStyle(color=C["accent"])),
            ft.OutlinedButton("Delete Voice", icon=ft.Icons.PERSON_REMOVE, on_click=cmd_delete, style=ft.ButtonStyle(color=C["error"])),
            ft.OutlinedButton("Health Check", icon=ft.Icons.MEDICAL_SERVICES, on_click=cmd_health, style=ft.ButtonStyle(color=C["purple"])),
            ft.OutlinedButton("Add Voice", icon=ft.Icons.PERSON_ADD, on_click=cmd_add, style=ft.ButtonStyle(color=C["orange"])),
        ])

        return ft.Column([ft.Container(ft.Column([
            ft.Text("工作台", size=20, weight=ft.FontWeight.BOLD, color=C["text"]),
            ft.Divider(color=C["border"]),
            sql_input,
            btn_row,
            ft.Divider(color=C["border"]),
            ft.Text("日志", size=13, weight=ft.FontWeight.BOLD, color=C["text_muted"]),
            log_box,
        ], spacing=8), padding=24, expand=True)], scroll=ft.ScrollMode.AUTO)


def main(page: ft.Page):
    App(page)


if __name__ == "__main__":
    ft.app(target=main)