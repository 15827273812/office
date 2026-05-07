"""
PS Tool Desktop - Flet 桌面客户端
现代化仓储管理工具
"""
import flet as ft
import threading
import os
import sys

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import (
    DBManager, query_gi_status, query_export_data, query_label_history,
    query_date_range, DATE_QUERY_MAP, export_to_excel, export_inventory_to_excel,
    get_config
)

# 主题颜色
COLORS = {
    "bg": "#1a1a2e",
    "bg_dark": "#16213e",
    "bg_card": "#1e293b",
    "accent": "#0ea5e9",
    "accent_light": "#38bdf8",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "text": "#f1f5f9",
    "text_muted": "#94a3b8",
    "border": "#334155",
}


def main(page: ft.Page):
    page.title = "PS Tool Desktop - 仓储管理系统"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = COLORS["bg"]
    page.padding = 0
    page.window_width = 1280
    page.window_height = 800
    page.window_min_width = 900
    page.window_min_height = 600

    # 初始化数据库管理器
    db = DBManager()

    # 当前选中的导航项
    selected_index = 0

    # ==================== 工具函数 ====================
    def show_snack(msg, color=COLORS["success"]):
        page.snack_bar = ft.SnackBar(
            ft.Text(msg, color=ft.Colors.WHITE),
            bgcolor=color,
            duration=3000,
        )
        page.snack_bar.open = True
        page.update()

    def show_error(msg):
        show_snack(str(msg), COLORS["error"])

    def safe_run(func, *args, **kwargs):
        """在后台线程运行数据库操作"""
        def task():
            try:
                result = func(*args, **kwargs)
                page.schedule_task(lambda: on_result(result))
            except Exception as e:
                page.schedule_task(lambda: on_error(str(e)))
        
        # 显示加载
        loading.visible = True
        page.update()
        threading.Thread(target=task, daemon=True).start()

    def on_result(result):
        loading.visible = False
        page.update()

    def on_error(msg):
        loading.visible = False
        show_error(msg)

    # 加载遮罩
    loading = ft.Container(
        ft.Column([
            ft.ProgressRing(width=48, height=48, color=COLORS["accent"]),
            ft.Text("加载中...", color=COLORS["text_muted"], size=14),
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
        alignment=ft.alignment.center,
        bgcolor=ft.Colors.with_opacity(0.7, COLORS["bg_dark"]),
        visible=False,
        expand=True,
    )

    # ==================== 主导航栏 ====================
    nav_items = [
        ft.NavigationRailDestination(
            icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
            selected_icon=ft.Icons.CHECK_CIRCLE,
            label="GI 状态",
        ),
        ft.NavigationRailDestination(
            icon=ft.Icons.FILE_DOWNLOAD_OUTLINED,
            selected_icon=ft.Icons.FILE_DOWNLOAD,
            label="数据导出",
        ),
        ft.NavigationRailDestination(
            icon=ft.Icons.LABEL_OUTLINE,
            selected_icon=ft.Icons.LABEL,
            label="标签历史",
        ),
        ft.NavigationRailDestination(
            icon=ft.Icons.DATE_RANGE_OUTLINED,
            selected_icon=ft.Icons.DATE_RANGE,
            label="日期查询",
        ),
        ft.NavigationRailDestination(
            icon=ft.Icons.BUG_REPORT_OUTLINED,
            selected_icon=ft.Icons.BUG_REPORT,
            label="创建 Incident",
        ),
    ]

    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        extended=True,
        bgcolor=COLORS["bg_dark"],
        indicator_color=COLORS["accent"],
        destinations=nav_items,
        on_change=lambda e: switch_tab(e.control.selected_index),
    )

    # ==================== 内容区域容器 ====================
    content_container = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=0)

    # ==================== GI Status ====================
    gi_summary_table = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(c, size=12)) for c in ["STSCODE", "流程类型", "箱数"]],
        rows=[],
        bgcolor=COLORS["bg_card"],
        border=ft.border.all(1, COLORS["border"]),
        heading_row_color=COLORS["bg_dark"],
    )
    gi_status_table = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(c, size=12)) for c in ["状态", "数量"]],
        rows=[],
        bgcolor=COLORS["bg_card"],
        border=ft.border.all(1, COLORS["border"]),
        heading_row_color=COLORS["bg_dark"],
    )
    gi_errors_table = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(c, size=12)) for c in ["日期", "时间", "LNK", "消息"]],
        rows=[],
        bgcolor=COLORS["bg_card"],
        border=ft.border.all(1, COLORS["border"]),
        heading_row_color=COLORS["bg_dark"],
    )
    gi_status_badge = ft.Container(visible=False)
    gi_volume_row = ft.Row(spacing=12, wrap=True, visible=False)
    gi_time_info = ft.Row(spacing=24, visible=False)

    def build_gi_view():
        """构建GI状态页面"""
        result_view = ft.Column(visible=False, spacing=12)
        
        def on_query_gi(e):
            def task():
                try:
                    data = query_gi_status(db)
                    page.schedule_task(lambda: update_gi_view(data, result_view))
                except Exception as ex:
                    page.schedule_task(lambda: on_error(str(ex)))
            loading.visible = True
            page.update()
            threading.Thread(target=task, daemon=True).start()
        
        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Row([
                        ft.Text("GI 状态监控", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                        ft.Container(expand=True),
                        ft.FilledButton(
                            "查询 GI 状态",
                            icon=ft.Icons.REFRESH,
                            on_click=on_query_gi,
                            style=ft.ButtonStyle(bgcolor=COLORS["accent"]),
                        ),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(color=COLORS["border"]),
                    result_view,
                ], spacing=12),
                padding=24,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    def update_gi_view(data, container):
        """更新GI状态视图"""
        container.visible = True
        container.controls.clear()

        # 状态徽章
        status_color = COLORS["success"] if data["gi_done"] else COLORS["error"]
        status_text = "GI 已完成 ✓" if data["gi_done"] else "GI 未完成 ✗"
        
        container.controls.extend([
            ft.Container(
                ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE if data["gi_done"] else ft.Icons.ERROR,
                           color=status_color, size=20),
                    ft.Text(status_text, size=16, weight=ft.FontWeight.BOLD, color=status_color),
                ], spacing=8),
                padding=12,
                bgcolor=ft.Colors.with_opacity(0.1, status_color),
                border_radius=8,
            ),
            # 今日量统计
            ft.Container(
                ft.Column([
                    ft.Text("今日量统计", size=14, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ft.ResponsiveRow([
                        ft.Container(
                            ft.Column([
                                ft.Text(data['today_volume']['units'], size=24, weight=ft.FontWeight.BOLD, color=COLORS["accent"]),
                                ft.Text("总数量", size=11, color=COLORS["text_muted"]),
                            ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=12, bgcolor=COLORS["bg_card"], border_radius=8,
                            col={"sm": 6, "md": 3},
                        ),
                        ft.Container(
                            ft.Column([
                                ft.Text(data['today_volume']['cartons'], size=24, weight=ft.FontWeight.BOLD, color=COLORS["success"]),
                                ft.Text("箱数", size=11, color=COLORS["text_muted"]),
                            ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=12, bgcolor=COLORS["bg_card"], border_radius=8,
                            col={"sm": 6, "md": 3},
                        ),
                        ft.Container(
                            ft.Column([
                                ft.Text(data['today_volume']['dns'], size=24, weight=ft.FontWeight.BOLD, color=COLORS["warning"]),
                                ft.Text("DN 数量", size=11, color=COLORS["text_muted"]),
                            ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=12, bgcolor=COLORS["bg_card"], border_radius=8,
                            col={"sm": 6, "md": 3},
                        ),
                        ft.Container(
                            ft.Column([
                                ft.Text(data['today_volume']['pls'], size=24, weight=ft.FontWeight.BOLD, color="#a855f7"),
                                ft.Text("PL 数量", size=11, color=COLORS["text_muted"]),
                            ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=12, bgcolor=COLORS["bg_card"], border_radius=8,
                            col={"sm": 6, "md": 3},
                        ),
                    ], spacing=12),
                ], spacing=8),
                padding=16, bgcolor=COLORS["bg_card"], border_radius=8,
            ),
            # 时间信息
            ft.Container(
                ft.Row([
                    ft.Column([
                        ft.Text("最后 CMR 时间", size=11, color=COLORS["text_muted"]),
                        ft.Text(data['max_cmr_time'], size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ]),
                    ft.VerticalDivider(color=COLORS["border"]),
                    ft.Column([
                        ft.Text("最后 GI 时间", size=11, color=COLORS["text_muted"]),
                        ft.Text(data['max_gi_time'], size=16, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ]),
                ], spacing=24),
                padding=16, bgcolor=COLORS["bg_card"], border_radius=8,
            ),
        ])

        # STSCODE汇总表
        if data['summary']:
            rows = []
            for r in data['summary']:
                rows.append(ft.DataRow([
                    ft.DataCell(ft.Text(str(r.get('STSCODE', '')), size=12, color=COLORS["text"])),
                    ft.DataCell(ft.Text(str(r.get('FLOW_TYPE', '')), size=12, color=COLORS["text"])),
                    ft.DataCell(ft.Text(str(r.get('CARTONS', 0)), size=12, color=COLORS["text"])),
                ]))
            gi_summary_table.rows = rows
            container.controls.append(ft.Container(
                ft.Column([
                    ft.Text("STSCODE 汇总", size=14, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    gi_summary_table,
                ], spacing=8),
                padding=16, bgcolor=COLORS["bg_card"], border_radius=8,
            ))

        # GI状态表
        if data['gi_status']:
            rows = []
            for r in data['gi_status']:
                rows.append(ft.DataRow([
                    ft.DataCell(ft.Text(str(r.get('SHGISFLG', '')), size=12, color=COLORS["text"])),
                    ft.DataCell(ft.Text(str(r.get('COUNT', 0)), size=12, color=COLORS["text"])),
                ]))
            gi_status_table.rows = rows
            container.controls.append(ft.Container(
                ft.Column([
                    ft.Text("GI 状态统计", size=14, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    gi_status_table,
                ], spacing=8),
                padding=16, bgcolor=COLORS["bg_card"], border_radius=8,
            ))

        # 错误表
        if data['errors']:
            rows = []
            for r in data['errors']:
                rows.append(ft.DataRow([
                    ft.DataCell(ft.Text(str(r.get('DATE', '')), size=12, color=COLORS["error"])),
                    ft.DataCell(ft.Text(str(r.get('TIME', '')), size=12, color=COLORS["error"])),
                    ft.DataCell(ft.Text(str(r.get('LNK', '')), size=12, color=COLORS["error"])),
                    ft.DataCell(ft.Text(str(r.get('MSG', '')), size=12, color=COLORS["error"])),
                ]))
            gi_errors_table.rows = rows
            container.controls.append(ft.Container(
                ft.Column([
                    ft.Text("GI 错误记录", size=14, weight=ft.FontWeight.BOLD, color=COLORS["error"]),
                    gi_errors_table,
                ], spacing=8),
                padding=16, bgcolor=COLORS["bg_card"], border_radius=8,
            ))

        loading.visible = False
        page.update()

    # ==================== 数据导出 ====================
    def build_export_view():
        num_input = ft.TextField(
            label="数字条件（每行一个）",
            multiline=True,
            min_lines=5,
            max_lines=10,
            hint_text="计划号/Shipment/Packlist/Run/箱号\n每行一个",
            border_color=COLORS["border"],
            color=COLORS["text"],
        )
        alpha_input = ft.TextField(
            label="字母条件（每行一个）",
            multiline=True,
            min_lines=5,
            max_lines=10,
            hint_text="物料/SKU/Access Number\n每行一个",
            border_color=COLORS["border"],
            color=COLORS["text"],
        )
        export_result_table = ft.DataTable(
            columns=[],
            rows=[],
            bgcolor=COLORS["bg_card"],
            border=ft.border.all(1, COLORS["border"]),
            heading_row_color=COLORS["bg_dark"],
            column_spacing=20,
        )
        result_info = ft.Text("", size=13, color=COLORS["text_muted"], visible=False)
        file_prefix_tag = ft.Container(visible=False)

        export_data_container = ft.Column(visible=False, spacing=8, scroll=ft.ScrollMode.AUTO)

        def on_query_num(e):
            conditions = [c.strip() for c in num_input.value.split('\n') if c.strip()]
            if not conditions:
                show_error("请输入条件")
                return
            run_export_query(conditions, 'num', export_data_container, export_result_table, result_info, file_prefix_tag)

        def on_query_alpha(e):
            conditions = [c.strip() for c in alpha_input.value.split('\n') if c.strip()]
            if not conditions:
                show_error("请输入条件")
                return
            run_export_query(conditions, 'alpha', export_data_container, export_result_table, result_info, file_prefix_tag)

        def run_export_query(conditions, ctype, container, table, info, tag):
            def task():
                try:
                    data = query_export_data(db, conditions if ctype == 'num' else [], 
                                              conditions if ctype == 'alpha' else [])
                    page.schedule_task(lambda: update_export_result(data, container, table, info, tag))
                except Exception as ex:
                    page.schedule_task(lambda: on_error(str(ex)))
            loading.visible = True
            page.update()
            threading.Thread(target=task, daemon=True).start()

        def update_export_result(data, container, table, info, tag):
            container.visible = True
            container.controls.clear()
            
            if not data['rows']:
                info.value = "查询结果为空"
                info.visible = True
                tag.visible = False
                table.columns = []
                table.rows = []
                loading.visible = False
                page.update()
                return
            
            # 更新表头
            cols = [ft.DataColumn(ft.Text(c, size=12, weight=ft.FontWeight.BOLD, color=COLORS["accent"]))
                    for c in data['fields']]
            table.columns = cols
            
            # 更新数据行
            rows = []
            for r in data['rows']:
                cells = []
                for f in data['fields']:
                    cells.append(ft.DataCell(ft.Text(str(r.get(f, '')), size=12, color=COLORS["text"])))
                rows.append(ft.DataRow(cells))
            table.rows = rows
            
            info.value = f"共 {len(data['rows'])} 条记录"
            info.visible = True
            
            table.update()
            container.controls.append(table)
            
            loading.visible = False
            page.update()

        def on_export_excel(e):
            """导出当前结果到Excel"""
            # 从导出结果回传
            show_snack("导出功能: 点击查询后可在结果中导出")

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Text("Receiving / 数据导出", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ft.Divider(color=COLORS["border"]),
                    ft.ResponsiveRow([
                        ft.Container(num_input, col={"sm": 12, "md": 6}, padding=ft.padding.only(right=6)),
                        ft.Container(alpha_input, col={"sm": 12, "md": 6}, padding=ft.padding.only(left=6)),
                    ], spacing=12),
                    ft.Row([
                        ft.FilledButton("查询（数字条件）", icon=ft.Icons.SEARCH, on_click=on_query_num,
                                      style=ft.ButtonStyle(bgcolor=COLORS["accent"])),
                        ft.FilledButton("查询（字母条件）", icon=ft.Icons.SEARCH, on_click=on_query_alpha,
                                      style=ft.ButtonStyle(bgcolor=COLORS["success"])),
                        ft.OutlinedButton("导出Excel", icon=ft.Icons.DOWNLOAD, on_click=on_export_excel,
                                        style=ft.ButtonStyle(color=COLORS["accent"])),
                    ], spacing=8, wrap=True),
                    ft.Container(
                        ft.Column([
                            result_info,
                            ft.Stack([
                                ft.Container(
                                    ft.Column([export_data_container], scroll=ft.ScrollMode.AUTO),
                                    height=500,
                                ),
                            ]),
                        ], spacing=8),
                        visible=True,
                    ),
                ], spacing=12),
                padding=24,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ==================== 标签历史 ====================
    def build_label_view():
        LH_QUERY_TYPES = [
            "查询打印记录", "CHECK OPEN WORK", "CHECK AUDIT WORK",
            "检查SKU是否是AMINUS", "QA解锁?", "SO查询", "NFC",
            "查询包装信息", "RSO", "查询历史库位", "DP_area_info",
            "Export inventory",
        ]
        
        query_type_dd = ft.Dropdown(
            label="查询类型",
            options=[ft.dropdown.Option(t) for t in LH_QUERY_TYPES],
            value=LH_QUERY_TYPES[0],
            border_color=COLORS["border"],
            color=COLORS["text"],
            width=300,
        )
        carton_input = ft.TextField(
            label="箱号（每行一个）",
            multiline=True,
            min_lines=4,
            max_lines=8,
            hint_text="每行输入一个箱号",
            border_color=COLORS["border"],
            color=COLORS["text"],
        )
        label_table = ft.DataTable(
            columns=[],
            rows=[],
            bgcolor=COLORS["bg_card"],
            border=ft.border.all(1, COLORS["border"]),
            heading_row_color=COLORS["bg_dark"],
        )
        label_result_info = ft.Text("", size=13, color=COLORS["text_muted"], visible=False)
        inventory_tabs = ft.Tabs(visible=False, tabs=[])

        def on_query_label(e):
            cartons = [c.strip() for c in carton_input.value.split('\n') if c.strip()]
            if not cartons:
                show_error("请输入箱号")
                return
            qt = query_type_dd.value

            def task():
                try:
                    data = query_label_history(db, cartons, qt)
                    page.schedule_task(lambda: update_label_result(data))
                except Exception as ex:
                    page.schedule_task(lambda: on_error(str(ex)))
            loading.visible = True
            page.update()
            threading.Thread(target=task, daemon=True).start()

        def update_label_result(data):
            loading.visible = False
            
            if data['type'] == 'inventory_export':
                # 多sheet显示
                label_table.visible = False
                inventory_tabs.visible = True
                tabs = []
                for section in data['data']:
                    cols = [ft.DataColumn(ft.Text(c, size=11, color=COLORS["accent"]))
                           for c in section['fields']]
                    rows = []
                    for r in section['rows']:
                        cells = [ft.DataCell(ft.Text(str(r.get(f, '')), size=11, color=COLORS["text"]))
                                for f in section['fields']]
                        rows.append(ft.DataRow(cells))
                    
                    dt = ft.DataTable(columns=cols, rows=rows,
                                     bgcolor=COLORS["bg_card"],
                                     border=ft.border.all(1, COLORS["border"]),
                                     heading_row_color=COLORS["bg_dark"])
                    tabs.append(ft.Tab(text=section['sheet_name'], content=ft.Container(dt, padding=8)))
                
                inventory_tabs.tabs = tabs
                label_result_info.value = f"导出库存 - 箱号: {data['carton']}"
                label_result_info.visible = True
            else:
                inventory_tabs.visible = False
                label_table.visible = True
                if not data['fields']:
                    label_result_info.value = "查询结果为空"
                    label_result_info.visible = True
                    page.update()
                    return
                
                cols = [ft.DataColumn(ft.Text(c, size=11, color=COLORS["accent"]))
                       for c in data['fields']]
                rows = []
                for r in data['rows']:
                    cells = [ft.DataCell(ft.Text(str(r.get(f, '')), size=11, color=COLORS["text"]))
                            for f in data['fields']]
                    rows.append(ft.DataRow(cells))
                label_table.columns = cols
                label_table.rows = rows
                label_result_info.value = f"共 {data['total']} 条记录"
                label_result_info.visible = True
            
            page.update()

        def on_export_label(e):
            show_snack("导出功能已就绪（需先查询）")

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Text("查历史库位 / 标签", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ft.Divider(color=COLORS["border"]),
                    ft.Row([query_type_dd, ft.Container(expand=True)], spacing=12),
                    carton_input,
                    ft.Row([
                        ft.FilledButton("查询", icon=ft.Icons.SEARCH, on_click=on_query_label,
                                      style=ft.ButtonStyle(bgcolor=COLORS["accent"])),
                        ft.OutlinedButton("导出Excel", icon=ft.Icons.DOWNLOAD, on_click=on_export_label,
                                        style=ft.ButtonStyle(color=COLORS["accent"])),
                    ], spacing=8, wrap=True),
                    ft.Container(
                        ft.Column([
                            label_result_info,
                            label_table,
                            inventory_tabs,
                        ], spacing=8),
                        margin=ft.margin.only(top=12),
                    ),
                ], spacing=12),
                padding=24,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ==================== 日期查询 ====================
    def build_date_view():
        date_query_types = list(DATE_QUERY_MAP.keys())
        
        date_query_dd = ft.Dropdown(
            label="查询类型",
            options=[ft.dropdown.Option(t) for t in date_query_types],
            value=date_query_types[0],
            border_color=COLORS["border"],
            color=COLORS["text"],
            width=350,
        )
        start_date_picker = ft.DatePicker()
        end_date_picker = ft.DatePicker()
        start_date_field = ft.TextField(
            label="开始日期",
            hint_text="点击选择日期",
            read_only=True,
            border_color=COLORS["border"],
            color=COLORS["text"],
            width=200,
        )
        end_date_field = ft.TextField(
            label="结束日期",
            hint_text="点击选择日期",
            read_only=True,
            border_color=COLORS["border"],
            color=COLORS["text"],
            width=200,
        )
        date_result_table = ft.DataTable(
            columns=[],
            rows=[],
            bgcolor=COLORS["bg_card"],
            border=ft.border.all(1, COLORS["border"]),
            heading_row_color=COLORS["bg_dark"],
        )
        date_result_info = ft.Text("", size=13, color=COLORS["text_muted"], visible=False)

        def pick_start(e):
            page.open(start_date_picker)

        def pick_end(e):
            page.open(end_date_picker)

        def on_start_date(e):
            if start_date_picker.value:
                start_date_field.value = start_date_picker.value.strftime("%Y-%m-%d")
                page.update()

        def on_end_date(e):
            if end_date_picker.value:
                end_date_field.value = end_date_picker.value.strftime("%Y-%m-%d")
                page.update()

        start_date_picker.on_change = on_start_date
        end_date_picker.on_change = on_end_date

        def on_query_date(e):
            qt = date_query_dd.value
            sd = start_date_picker.value
            ed = end_date_picker.value

            def task():
                try:
                    data = query_date_range(db, qt, sd, ed)
                    page.schedule_task(lambda: update_date_result(data))
                except Exception as ex:
                    page.schedule_task(lambda: on_error(str(ex)))
            loading.visible = True
            page.update()
            threading.Thread(target=task, daemon=True).start()

        def update_date_result(data):
            loading.visible = False
            if not data['rows']:
                date_result_info.value = "查询结果为空"
                date_result_info.visible = True
                page.update()
                return
            
            cols = [ft.DataColumn(ft.Text(c, size=11, color=COLORS["accent"]))
                   for c in data['fields']]
            rows = []
            for r in data['rows']:
                cells = [ft.DataCell(ft.Text(str(r.get(f, '')), size=11, color=COLORS["text"]))
                        for f in data['fields']]
                rows.append(ft.DataRow(cells))
            
            date_result_table.columns = cols
            date_result_table.rows = rows
            date_result_info.value = f"共 {data['total']} 条记录  |  类型: {data['file_prefix']}"
            date_result_info.visible = True
            page.update()

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Text("按日期查询", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ft.Divider(color=COLORS["border"]),
                    ft.Row([date_query_dd, ft.Container(expand=True)], spacing=12, wrap=True),
                    ft.Row([
                        ft.Row([
                            start_date_field,
                            ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=pick_start,
                                        icon_color=COLORS["accent"]),
                        ]),
                        ft.Text("至", color=COLORS["text_muted"]),
                        ft.Row([
                            end_date_field,
                            ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=pick_end,
                                        icon_color=COLORS["accent"]),
                        ]),
                    ], spacing=8, wrap=True),
                    ft.Row([
                        ft.FilledButton("查询", icon=ft.Icons.SEARCH, on_click=on_query_date,
                                      style=ft.ButtonStyle(bgcolor=COLORS["accent"])),
                        ft.OutlinedButton("导出Excel", icon=ft.Icons.DOWNLOAD,
                                        style=ft.ButtonStyle(color=COLORS["accent"])),
                    ], spacing=8),
                    ft.Container(
                        ft.Column([
                            date_result_info,
                            ft.Container(date_result_table, height=500),
                        ], spacing=8),
                        margin=ft.margin.only(top=12),
                    ),
                ], spacing=12),
                padding=24,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ==================== 创建 Incident ====================
    def build_incident_view():
        inc_title = ft.TextField(
            label="标题 *",
            hint_text="请输入 Incident 标题",
            border_color=COLORS["border"],
            color=COLORS["text"],
        )
        inc_desc = ft.TextField(
            label="描述",
            multiline=True,
            min_lines=6,
            hint_text="请输入详细描述",
            border_color=COLORS["border"],
            color=COLORS["text"],
        )
        inc_category = ft.Dropdown(
            label="分类",
            options=[
                ft.dropdown.Option("Inquiry / Help"),
                ft.dropdown.Option("Incident"),
                ft.dropdown.Option("Service Request"),
            ],
            value="Inquiry / Help",
            border_color=COLORS["border"],
            color=COLORS["text"],
            width=300,
        )
        inc_result = ft.Container(visible=False)

        def on_create_incident(e):
            if not inc_title.value:
                show_error("请输入标题")
                return
            
            cfg = get_config()
            sn = cfg.get('service_now', {})
            
            if not sn.get('url_create'):
                show_error("ServiceNow 未配置")
                return

            # 使用 requests 调用 ServiceNow API
            def task():
                try:
                    import requests
                    headers = sn.get('headers', {"Accept": "*/*", "Content-type": "application/json"})
                    payload = {
                        "short_description": inc_title.value,
                        "description": inc_desc.value,
                        "category": inc_category.value,
                        "assignment_group": "",
                    }
                    
                    templates = sn.get('incident_templates', {})
                    for cat, defaults in templates.items():
                        if cat.lower() in inc_category.value.lower() or cat.lower() in inc_title.value.lower():
                            for k, v in defaults.items():
                                if k not in payload or not payload[k]:
                                    payload[k] = v
                    
                    urls = [sn.get('url_create'), sn.get('url_create_backup')]
                    last_error = ""
                    
                    for url in urls:
                        if not url:
                            continue
                        try:
                            resp = requests.post(
                                url, headers=headers,
                                auth=(sn['username'], sn['password']),
                                json=payload, timeout=30
                            )
                            if resp.status_code in (200, 201):
                                page.schedule_task(lambda: show_incident_result(True, resp.json()))
                                return
                            last_error = f"HTTP {resp.status_code}: {resp.text[:100]}"
                        except Exception as ex:
                            last_error = str(ex)
                    
                    page.schedule_task(lambda: show_incident_result(False, last_error))
                except Exception as ex:
                    page.schedule_task(lambda: on_error(str(ex)))
            
            loading.visible = True
            page.update()
            threading.Thread(target=task, daemon=True).start()

        def show_incident_result(success, data):
            loading.visible = False
            if success:
                inc_result.content = ft.Container(
                    ft.Row([
                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=COLORS["success"]),
                        ft.Text("Incident 创建成功!", color=COLORS["success"], size=14, weight=ft.FontWeight.BOLD),
                    ]),
                    padding=12, bgcolor=ft.Colors.with_opacity(0.1, COLORS["success"]), border_radius=8,
                )
            else:
                inc_result.content = ft.Container(
                    ft.Row([
                        ft.Icon(ft.Icons.ERROR, color=COLORS["error"]),
                        ft.Text(f"创建失败: {data}", color=COLORS["error"], size=14),
                    ]),
                    padding=12, bgcolor=ft.Colors.with_opacity(0.1, COLORS["error"]), border_radius=8,
                )
            inc_result.visible = True
            page.update()

        return ft.Column([
            ft.Container(
                ft.Column([
                    ft.Text("创建 ServiceNow Incident", size=20, weight=ft.FontWeight.BOLD, color=COLORS["text"]),
                    ft.Divider(color=COLORS["border"]),
                    inc_title,
                    inc_desc,
                    inc_category,
                    ft.Row([
                        ft.FilledButton("创建 Incident", icon=ft.Icons.ADD_CIRCLE,
                                      on_click=on_create_incident,
                                      style=ft.ButtonStyle(bgcolor=COLORS["accent"])),
                    ]),
                    inc_result,
                ], spacing=12),
                padding=24,
            ),
        ], scroll=ft.ScrollMode.AUTO)

    # ==================== Tab 切换 ====================
    views = [
        build_gi_view(),
        build_export_view(),
        build_label_view(),
        build_date_view(),
        build_incident_view(),
    ]

    def switch_tab(index):
        nav_rail.selected_index = index
        content_container.controls.clear()
        content_container.controls.append(views[index])
        content_container.controls.append(loading)
        page.update()

    # ==================== 初始化布局 ====================
    content_container.controls.append(views[0])
    content_container.controls.append(loading)

    page.add(
        ft.Row(
            [nav_rail, ft.VerticalDivider(width=1, color=COLORS["border"]), 
             ft.Container(content_container, expand=True)],
            expand=True,
        )
    )
    
    page.update()


# ==================== 入口 ====================
if __name__ == "__main__":
    ft.app(target=main)
