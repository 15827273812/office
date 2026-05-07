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
                ft.NavigationRailDestination(icon=ft.Icons.CHECK_CIRCLE_OUTLINE, selected_icon=ft.Icons.CHECK_CIRCLE, label="GI 状态"),
                ft.NavigationRailDestination(icon=ft.Icons.FILE_DOWNLOAD_OUTLINED, selected_icon=ft.Icons.FILE_DOWNLOAD, label="数据导出"),
                ft.NavigationRailDestination(icon=ft.Icons.LABEL_OUTLINE, selected_icon=ft.Icons.LABEL, label="标签历史"),
                ft.NavigationRailDestination(icon=ft.Icons.DATE_RANGE_OUTLINED, selected_icon=ft.Icons.DATE_RANGE, label="日期查询"),
                ft.NavigationRailDestination(icon=ft.Icons.BUG_REPORT_OUTLINED, selected_icon=ft.Icons.BUG_REPORT, label="Incident"),
                ft.NavigationRailDestination(icon=ft.Icons.TERMINAL, selected_icon=ft.Icons.TERMINAL, label="工作台"),
            ],
            on_change=self._switch,
        )
        self.views = [self._gi(), self._export(), self._label(), self._date(), self._incident(), self._workbench()]
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
                    self.page.run_thread(lambda: after(res))
            except Exception as e:
                self.page.run_thread(lambda: self.err(f"{type(e).__name__}: {e}"))
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

    def _tbl_widget(self, fields, rows, h=300):
        if not fields or not rows:
            return ft.Container(ft.Text("无数据", color=C["text_muted"]), padding=10)
        cols = [ft.DataColumn(ft.Text(c[:15], size=10, weight=ft.FontWeight.BOLD, color=C["accent"])) for c in fields]
        dr = [ft.DataRow([ft.DataCell(ft.Text(str(r.get(f,""))[:40], size=10, color=C["text"])) for f in fields]) for r in rows[:100]]
        extra = f"前100条/共{len(rows)}条" if len(rows) > 100 else f"共{len(rows)}条"
        return ft.Column([
            ft.Text(extra, size=11, color=C["text_muted"]),
            ft.Container(ft.DataTable(columns=cols, rows=dr, bgcolor=C["bg_card"],
                border=ft.border.all(1,C["border"]), heading_row_color=C["bg_dark"],
                heading_row_height=28, data_row_max_height=22), height=h, expand=True),
        ], spacing=2)

    def _save(self, key):
        data = self._cache.get(key)
        if not data:
            return self.err("请先查询数据")
        def work():
            from core import export_to_excel, export_inventory_to_excel
            if isinstance(data, dict) and data.get("type") == "inventory_export":
                tmp = export_inventory_to_excel(data.get("data", []), "Inventory")
            else:
                rows, fields = data.get("rows", []), data.get("fields", [])
                if not rows: raise Exception("无数据")
                tmp = export_to_excel(rows, fields, key)
            # 使用 file_prefix 作为文件名，不加时间戳，直接覆盖
            prefix = data.get("file_prefix", key)
            ds = os.path.join(os.path.expanduser("~"), "Desktop")
            os.makedirs(ds, exist_ok=True)
            dst = os.path.join(ds, f"{prefix}.xlsx")
            shutil.copy2(tmp, dst)
            return dst
        def done(p):
            self.toast(f"已保存: {os.path.basename(p)}")
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
            rv.controls.append(self._card(ft.Icons.ACCESS_TIME, "CMR / GI 时间", ft.Row([
                ft.Column([ft.Text("最后 CMR",size=11,color=C["text_muted"]),
                    ft.Text(str(data.get('max_cmr_time','N/A')),size=14,weight=ft.FontWeight.BOLD,color=C["text"])]),
                ft.VerticalDivider(color=C["border"]),
                ft.Column([ft.Text("最后 GI",size=11,color=C["text_muted"]),
                    ft.Text(str(data.get('max_gi_time','N/A')),size=14,weight=ft.FontWeight.BOLD,color=C["text"])]),
            ], spacing=24)))

            def make_stat_table(hd, rs, ec=False):
                tc = C["error"] if ec else C["text"]
                rows_widgets = []
                for r in rs:
                    row_items = []
                    for h in hd:
                        v = str(r.get(h, ""))
                        row_items.append(
                            ft.Row([
                                ft.Container(ft.Text(h, size=11, color=C["text_muted"], weight=ft.FontWeight.W_500),
                                             width=140, padding=ft.padding.only(right=8)),
                                ft.Container(ft.Text(v, size=12, color=tc, weight=ft.FontWeight.BOLD),
                                             expand=True),
                            ], spacing=0, alignment=ft.MainAxisAlignment.START)
                        )
                    rows_widgets.extend(row_items)
                    rows_widgets.append(ft.Divider(height=1, color=C["border"]))
                if rows_widgets:
                    rows_widgets.pop()  # 去掉最后一个分隔线
                return ft.Column(rows_widgets, spacing=6)
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
        ni = ft.TextField(label="数字条件（每行一个）",multiline=True,min_lines=4,max_lines=8,
            hint_text="计划号 / Shipment / Packlist / Run / 箱号", border_color=C["border"], color=C["text"])
        ai = ft.TextField(label="字母条件（每行一个）",multiline=True,min_lines=4,max_lines=8,
            hint_text="物料 / SKU / Access Number", border_color=C["border"], color=C["text"])
        rv = ft.Column(spacing=4, visible=False, scroll=ft.ScrollMode.AUTO)

        def show(data):
            self._cache['export'] = data; rv.controls.clear(); rv.visible = True
            if not data.get("rows"):
                rv.controls.append(ft.Text("无数据", color=C["text_muted"]))
            else:
                rv.controls.append(ft.Row([ft.Icon(ft.Icons.INSERT_CHART,color=C["success"]),
                    ft.Text(f"{data['file_prefix']} | {len(data['rows'])} 行",size=13,color=C["text"])]))
                rv.controls.append(self._tbl_widget(data['fields'], data['rows']))
            self.page.update()

        def qn(e):
            c=[x.strip() for x in ni.value.split("\n") if x.strip()]
            if not c: return self.err("请输入数字条件")
            rv.visible=False; rv.controls.clear()
            self._run(lambda: query_export_data(self.db, c, []), lambda d: show(d))

        def qa(e):
            c=[x.strip() for x in ai.value.split("\n") if x.strip()]
            if not c: return self.err("请输入字母条件")
            rv.visible=False; rv.controls.clear()
            self._run(lambda: query_export_data(self.db, [], c), lambda d: show(d))

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

        def show(data):
            self._cache['label'] = data; rv.controls.clear(); rv.visible = True
            if data.get("type") == "inventory_export":
                rv.controls.append(ft.Text(f"Export - {data.get('carton','')}", size=14, color=C["text"]))
                tabs=[ft.Tab(text=s.get('sheet_name','')[:15],content=self._tbl_widget(s['fields'],s['rows'])) for s in data.get("data",[])]
                rv.controls.append(ft.Tabs(tabs, selected_index=0))
            else:
                if not data.get("fields") or not data.get("rows"):
                    rv.controls.append(ft.Text("无数据", color=C["text_muted"]))
                else:
                    rv.controls.append(ft.Text(f"{data.get('query_type','')} | {data.get('total',0)} 条",size=13,color=C["text"]))
                    rv.controls.append(self._tbl_widget(data['fields'], data['rows']))
            self.page.update()

        def q(e):
            c=[x.strip() for x in ci.value.split("\n") if x.strip()]
            if not c: return self.err("请输入箱号")
            rv.visible=False; rv.controls.clear()
            self._run(lambda: query_label_history(self.db, c, dd.value), lambda d: show(d))

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
        sf = ft.TextField(label="开始日期", hint_text="点击选择", read_only=True,
                          border_color=C["border"], color=C["text"], width=200)
        ef = ft.TextField(label="结束日期", hint_text="点击选择", read_only=True,
                          border_color=C["border"], color=C["text"], width=200)
        rv = ft.Column(spacing=4, visible=False, scroll=ft.ScrollMode.AUTO)

        def ps(e): self.page.open(sp)
        def pe(e): self.page.open(ep)
        sp.on_change = lambda e: (setattr(sf,"value",sp.value.strftime("%Y-%m-%d")) or self.page.update()) if sp.value else None
        ep.on_change = lambda e: (setattr(ef,"value",ep.value.strftime("%Y-%m-%d")) or self.page.update()) if ep.value else None

        def show(data):
            self._cache['date'] = data; rv.controls.clear(); rv.visible = True
            if not data.get("rows"):
                rv.controls.append(ft.Text("无数据", color=C["text_muted"]))
            else:
                rv.controls.append(ft.Row([ft.Icon(ft.Icons.DATE_RANGE,color=C["accent"]),
                    ft.Text(f"{data.get('file_prefix','')} | {data.get('total',0)} 条")]))
                rv.controls.append(self._tbl_widget(data['fields'], data['rows']))
            self.page.update()

        def q(e):
            rv.visible=False; rv.controls.clear()
            self._run(lambda: query_date_range(self.db, dd.value, sp.value, ep.value), lambda d: show(d))

        return ft.Column([ft.Container(ft.Column([
            ft.Text("按日期查询",size=20,weight=ft.FontWeight.BOLD,color=C["text"]),
            ft.Divider(color=C["border"]), dd,
            ft.Row([
                ft.Row([sf,ft.IconButton(ft.Icons.CALENDAR_MONTH,on_click=ps,icon_color=C["accent"])]),
                ft.Text("至",color=C["text_muted"]),
                ft.Row([ef,ft.IconButton(ft.Icons.CALENDAR_MONTH,on_click=pe,icon_color=C["accent"])]),
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
        # === 5. Health Check (AS400 + pyautogui + docx) ===
        def cmd_health(e):
            wb_log("Health Check 启动...", C["accent"])
            wb_log("请确保已切换到 AS400 5250 终端窗口", C["warning"])
            def work():
                try:
                    import pyautogui, pyperclip, docx
                    from PIL import Image
                    import easygui
                    cfg = self._cfg.get("health_check", {})
                    choice = easygui.buttonbox(
                        msg="请切换到AS400 Command Entry界面\n并确认翻页快捷键已设置!!",
                        title="AS400 Health Check", choices=["OK", "Cancel"])
                    if choice != "OK":
                        return {"msg": "用户取消"}
                    time.sleep(2)
                    pics_dir = "pictures"
                    os.makedirs(pics_dir, exist_ok=True)
                    current_date = datetime.now().strftime("%m%d")
                    word_path = os.path.join(os.path.expanduser("~"), "Desktop", f"{current_date}.docx")
                    doc = docx.Document()
                    def create_screenshots(name, d):
                        shot = pyautogui.screenshot(region=(0,0,1920,1080))
                        pic = os.path.join(pics_dir, f"{current_date}_{name}.png")
                        shot.save(pic)
                        d.add_picture(pic, width=docx.shared.Inches(6))
                        d.add_page_break()
                    d = doc.add_paragraph(f"AS400 Health Check Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                    d.add_run("\n")
                    doc.save(word_path)
                    pyautogui.hotkey("ctrl", "a")
                    pyautogui.hotkey("ctrl", "c")
                    time.sleep(0.5)
                    pyautogui.typewrite("WATCHDOG")
                    time.sleep(0.3)
                    pyautogui.press("enter")
                    time.sleep(3)
                    pyautogui.hotkey("ctrl", "a")
                    time.sleep(0.5)
                    pyautogui.hotkey("ctrl", "c")
                    time.sleep(0.5)
                    try:
                        clip = pyperclip.paste()
                        if "WATCHDOG" in clip:
                            create_screenshots("watchdog", doc)
                    except: pass
                    for i in range(3):
                        pyautogui.press("pagedown")
                        time.sleep(2)
                        try:
                            pyautogui.hotkey("ctrl","a"); time.sleep(0.3)
                            pyautogui.hotkey("ctrl","c"); time.sleep(0.3)
                        except: pass
                        create_screenshots(f"watchdog_pg{i+1}", doc)
                    doc.save(word_path)
                    # STRSQL
                    pyautogui.hotkey("ctrl","a"); time.sleep(0.3)
                    pyautogui.typewrite("STRSQL")
                    time.sleep(0.3); pyautogui.press("enter"); time.sleep(5)
                    create_screenshots("strsql", doc)
                    pyautogui.typewrite("60"); pyautogui.press("enter"); time.sleep(3)
                    create_screenshots("strsql_60", doc)
                    # Return + RBM
                    pyautogui.hotkey("ctrl","a"); time.sleep(0.3)
                    pyautogui.typewrite("110"); pyautogui.press("enter"); time.sleep(2)
                    create_screenshots("rbm_110", doc)
                    pyautogui.hotkey("ctrl","a"); time.sleep(0.3)
                    pyautogui.typewrite("20"); pyautogui.press("enter"); time.sleep(2)
                    create_screenshots("20", doc)
                    pyautogui.hotkey("ctrl","a"); time.sleep(0.3)
                    pyautogui.typewrite("50"); pyautogui.press("enter"); time.sleep(2)
                    create_screenshots("50", doc)
                    pyautogui.hotkey("ctrl","a"); time.sleep(0.3)
                    pyautogui.typewrite("13"); pyautogui.press("enter"); time.sleep(2)
                    create_screenshots("13", doc)
                    doc.save(word_path)
                    return {"msg": f"已完成, 报告: {word_path}"}
                except ImportError as ex:
                    return {"error": f"需要安装依赖: {ex}. pip install pyautogui pyperclip python-docx Pillow easygui"}
                except Exception as ex:
                    return {"error": str(ex)}
            def done(ret):
                if "error" in ret:
                    wb_log(f"Health Check 错误: {ret['error']}", C["error"])
                elif "msg" in ret:
                    wb_log(f"Health Check {ret['msg']}", C["success"])
            self._run(work, done)
        # === 6. Add Voice User (Selenium + Excel) ===
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