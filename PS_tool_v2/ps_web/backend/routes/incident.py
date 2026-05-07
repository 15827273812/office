"""
Incident 路由 - 创建 ServiceNow Incident
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core import get_config
import requests
import json

router = APIRouter()


class IncidentCreate(BaseModel):
    short_description: str
    description: str = ""
    assignment_group: str = ""
    category: str = "Inquiry / Help"


@router.post("/incident/create")
def create_incident(incident: IncidentCreate):
    """
    在 ServiceNow 创建 Incident
    """
    try:
        cfg = get_config()
        sn = cfg.get('service_now', {})

        if not sn.get('url_create') or not sn.get('password'):
            raise HTTPException(status_code=400, detail="ServiceNow 未配置")

        headers = sn.get('headers', {
            "Accept": "*/*",
            "Content-type": "application/json"
        })

        payload = {
            "short_description": incident.short_description,
            "description": incident.description,
            "assignment_group": incident.assignment_group,
            "category": incident.category,
        }

        # 如果有模板配置，应用默认值
        templates = sn.get('incident_templates', {})
        if templates:
            for cat, defaults in templates.items():
                if cat.lower() in incident.category.lower() or cat.lower() in incident.short_description.lower():
                    for k, v in defaults.items():
                        if k not in payload or not payload[k]:
                            payload[k] = v

        # 使用 Basic Auth
        username = sn.get('username', '')
        password = sn.get('password', '')

        # 尝试主 URL，如果失败则使用备用
        urls = [sn.get('url_create'), sn.get('url_create_backup')]
        last_error = ""

        for url in urls:
            if not url:
                continue
            try:
                resp = requests.post(
                    url,
                    headers=headers,
                    auth=(username, password),
                    json=payload,
                    timeout=30
                )
                if resp.status_code in (200, 201):
                    return {
                        "success": True,
                        "status_code": resp.status_code,
                        "response": resp.json()
                    }
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except requests.RequestException as e:
                last_error = str(e)
                continue

        raise Exception(f"所有 URL 都失败: {last_error}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
