"""
PS Tool Web - FastAPI 后端入口
启动: cd backend && python main.py
或: uvicorn backend.main:app --host 0.0.0.0 --port 8080
"""
import os
import sys

# 添加 backend 目录的父目录到 path，以便能从 backend 包内导入
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routes import gi_status, label_history, export_data, date_query, incident
from core import get_config

app = FastAPI(title="PS Tool Web", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gi_status.router, prefix="/api", tags=["GI Status"])
app.include_router(label_history.router, prefix="/api", tags=["Label History"])
app.include_router(export_data.router, prefix="/api", tags=["Export Data"])
app.include_router(date_query.router, prefix="/api", tags=["Date Query"])
app.include_router(incident.router, prefix="/api", tags=["Incident"])


@app.get("/api/config/info")
def get_config_info():
    cfg = get_config()
    return {
        "gi_status_queries": len(cfg['sql_queries'].get('gi_status', {})),
        "label_history_queries": len(cfg['sql_queries'].get('label_history', {})),
        "export_data_queries": len(cfg['sql_queries'].get('export_data', {})),
        "date_query_queries": len(cfg['sql_queries'].get('date_query', {})),
        "service_now_configured": bool(cfg.get('service_now', {})),
        "voice_console_configured": bool(cfg.get('voice_console', {})),
    }


@app.get("/health")
def health():
    return {"status": "ok", "app": "PS Tool Web", "version": "2.0.0"}


# 挂载前端
frontend_dir = os.path.join(PROJECT_ROOT, 'frontend')
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
