# PS Tool Web - 仓储管理系统

基于 Web 的仓储管理工具，替代原有 Tkinter 桌面版 PS_tool_v4.py。

## 技术栈

- **后端**：Python + FastAPI + Uvicorn
- **前端**：Vue 3 + Element Plus (CDN, 无构建步骤)
- **数据库**：DB2/iSeries (AS400), pyodbc
- **API**：RESTful, 自动文档 (/docs)

## 快速启动

```bash
cd backend
pip install fastapi uvicorn pyodbc python-multipart openpyxl xlsxwriter pandas
python main.py
```

浏览器打开 http://localhost:8080

## 功能

- GI 状态监控
- Receiving 数据导出 (自动判断条件类型)
- 标签历史查询 (12种查询类型)
- 日期范围查询 (21种查询类型)
- ServiceNow Incident 创建
- 所有结果支持导出 Excel

## 项目结构

```
ps_web/
├── backend/
│   ├── main.py          # FastAPI 入口
│   ├── core.py          # 配置加载 & 数据库管理
│   └── routes/
│       ├── gi_status.py    # GI状态
│       ├── label_history.py # 标签历史
│       ├── export_data.py   # 数据导出
│       ├── date_query.py    # 日期查询
│       └── incident.py      # ServiceNow工单
├── frontend/
│   └── index.html       # 单页 Web 应用
└── config.json          # 数据库 & SQL 配置
```
