# PS Tool Desktop - Flet 桌面客户端任务

## 目标
将 /home/mzh205/.openclaw/workspace/temp_refactor/review_check/PS_tool_v4.py 重写为 Flet 桌面客户端。

## 核心规则
1. **保留所有功能** - 不能删减任何功能
2. **配置驱动** - SQL 从 config.json 读取，不要硬编码
3. **参数化查询** - 防止 SQL 注入
4. **Flet 作为前端** - 使用最新的 Flet 0.84+
5. **漂亮的 UI** - 暗色主题，现代化布局

## 技术架构

```
ps_desktop/
  ps_tool.py        # 主入口 & UI (Flet)
  core.py           # 核心模块 (配置加载、DB连接、数据工具)
  backend_api.py    # 后端 API 层 (调用 core.py)
```

## 需要实现的功能模块

### 1. GI Status (GI_status 函数)
- 点击按钮查询 GI 状态
- 显示 STSCODE 汇总表格
- 显示 GI 状态统计
- 显示错误列表
- 显示今日量统计卡片
- 显示 CMR/GI 时间
- 自动判断 GI 是否完成

### 2. 数据导出 (export_data 函数)
- 数字条件输入框（多行文本框）
- 字母条件输入框（多行文本框）
- "查询(数字条件)"和"查询(字母条件)"按钮
- 结果表格展示
- 导出 Excel 按钮
- 自动条件判断逻辑：
  - <=4位数字 → ap_shipping → fw_shipping → replenishment (顺序执行)
  - 10位数字 → shipment_info → plan_info_by_por → delay_info
  - 6位数字 → plan_info_by_ibrc
  - 6+10位数字 → plan_info_by_both
  - 8位 → packlist_info
  - 20位 → fs_info → trailer_info
  - 字母10位 → data_by_sku
  - 字母9位 → trailer_info_by_csn
  - 其他字母 → inventory_by_sku

### 3. 标签历史 (Lable_His 函数)
- 查询类型下拉选择（12种 + Export inventory）
- 箱号输入（多行文本框）
- 查询按钮
- 结果表格（可分页）
- 导出 Excel 按钮
- 特殊处理: Export inventory 生成4个sheet的Excel

### 4. 按日期查询 (query_and_export 函数)
- 查询类型下拉选择（21种）
- 开始日期/结束日期选择器
- 查询按钮
- 结果表格展示
- 导出 Excel 按钮
- 日期 SQL = 参数化查询
- 无日期 SQL = 直接查询

### 5. 创建 Incident (create_incident / on_submit 函数)
- 标题输入
- 描述输入（多行）
- 分类下拉选择
- 提交按钮
- 结果反馈

## config.json 位置
/home/mzh205/.openclaw/workspace/temp_refactor/review_check/config.json

## UI 设计要求
- 左侧导航栏（功能模块列表）
- 右侧主内容区（当前选中模块）
- 亮色/暗色主题（默认暗色）
- 现代 Material Design 风格
- 响应式布局
- 使用 Flet 的 DataTable、Tabs、NavigationRail、TextField、Dropdown、DatePicker 等组件
- 动画过渡效果

## 实现步骤
1. 解析 config.json 加载所有配置
2. 实现 core.py（配置+DB连接+数据清洗）
3. 实现 ps_tool.py（完整 Flet UI）
4. 测试每个功能的正确性

## 约束
- 使用 pyodbc 连接数据库（连接字符串从 config.json 读取）
- 所有 SQL 从 config.json 的 sql_queries 中读取
- Excel 导出使用 openpyxl
- 数据清洗使用 pandas

开始编码。输出文件到 /home/mzh205/.openclaw/workspace/ps_desktop/
