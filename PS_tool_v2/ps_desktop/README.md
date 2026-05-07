# PS Tool Desktop - Flet 客户端

基于 Flet (Flutter) 的现代化桌面客户端，替代原有 Tkinter 版 PS_tool_v4.py。

## 功能

- GI 状态监控
- 数据导出（自动条件识别，14种SQL类型）
- 标签历史查询（16种查询类型 + Inventory导出）
- 日期范围查询（21种查询类型）
- ServiceNow Incident 创建

## 启动

```bash
cd backend && python main.py
```
```bash
cd ps_desktop && python ps_tool.py
```

## 依赖

```bash
pip install flet pyodbc openpyxl xlsxwriter pandas
```
