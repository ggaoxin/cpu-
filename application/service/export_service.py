"""结果导出服务：统一生成 JSON、CSV、XML、RDF 与可阅读报告。"""
from __future__ import annotations

import csv
import json
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from config.settings import settings
from config.tool_contracts import get_contract
from infrastructure.database.resource_repository import DatabaseResourceRepository, resource_repository
from infrastructure.database.task_repository import DatabaseTaskRepository, task_repository


CONTENT_TYPES = {
    "json": "application/json; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "xml": "application/xml; charset=utf-8",
    "rdf": "application/n-triples; charset=utf-8",
    "report": "text/markdown; charset=utf-8",
    "database": "application/json; charset=utf-8",
}

# CSV 公式注入防护（2026-11-24 漏洞修复）：以 = + - @ TAB CR 开头的单元格
# 会被 Excel/WPS 当作公式解释（=cmd|'/C calc'!A0 触发 DDE、=HYPERLINK 钓鱼），
# 统一加 ' 前缀使其成为纯文本。' 本身对正常数据无副作用（Excel 打开时不可见）。
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: Any) -> Any:
    """单元格值以公式触发字符开头时加 ' 前缀转义（CSV injection 防护）。

    纯数值（含负数，如情感极性 -0.8）不转义，保持 Excel 数值语义——
    数值单元格不可能构成公式；"-1+1|cmd" 这类混合串 float() 解析失败仍会转义。
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    if text.startswith(_FORMULA_PREFIXES):
        try:
            float(text)
            return text  # 数字串（如 "-0.8"）：保持数值语义
        except ValueError:
            return "'" + text
    return value


class ExportService:
    def __init__(
        self,
        task_repo: Optional[DatabaseTaskRepository] = None,
        resource_repo: Optional[DatabaseResourceRepository] = None,
    ) -> None:
        self.task_repo = task_repo or task_repository
        self.resource_repo = resource_repo or resource_repository
        self.export_dir = settings.PROJECT_ROOT / "runtime" / "exports"

    def create(self, result_record_id: str, export_format: str,
               expected_workspace: Optional[str] = None) -> Dict[str, Any]:
        record = self.task_repo.get_result(result_record_id)
        if not record:
            raise ValueError("结果记录不存在")
        export_format = export_format.lower().strip()
        contract = get_contract(record["tool_id"])
        if export_format not in contract.export_formats:
            raise ValueError(f"{contract.name} 不支持 {export_format} 导出")
        task = self.task_repo.get_task(record["task_id"])
        # 属主校验（2026-11-24 漏洞修复 V1 第二层）：他人结果不许导出
        if expected_workspace and task and task.get("workspace_id") \
                and str(task.get("workspace_id")) != str(expected_workspace):
            raise ValueError("结果记录不存在或无权导出")
        export_id = f"exp_{uuid.uuid4().hex}"
        extension = "md" if export_format == "report" else "json" if export_format == "database" else export_format
        self.export_dir.mkdir(parents=True, exist_ok=True)
        path = self.export_dir / f"{export_id}.{extension}"
        self._write(path, export_format, record, task or {})
        # 下载链接时效（2026-11-24 漏洞修复）：默认 30 天，之前无过期概念、
        # 链接永久有效；EXPORT_TTL_DAYS=0 可关回旧行为。
        expires_at = None
        if settings.EXPORT_TTL_DAYS > 0:
            expires_at = (datetime.now(ZoneInfo("Asia/Shanghai"))
                          + timedelta(days=settings.EXPORT_TTL_DAYS)).isoformat()
        saved = self.resource_repo.create_export({
            "id": export_id,
            "workspace_id": (task or {}).get("workspace_id", settings.DEFAULT_WORKSPACE_ID),
            "task_id": record["task_id"],
            "result_record_id": result_record_id,
            "format": export_format,
            "status": "succeeded",
            "object_key": str(path),
            "expires_at": expires_at,
        })
        return {
            **saved,
            "file_name": path.name,
            "content_type": CONTENT_TYPES[export_format],
            "download_url": f"/api/v1/exports/{export_id}/download",
        }

    def get(self, export_id: str) -> Optional[Dict[str, Any]]:
        value = self.resource_repo.get_export(export_id)
        if not value:
            return None
        # 过期强制生效（2026-11-24 漏洞修复）：过期导出视同不存在（下载/详情均 404）。
        expires_at = value.get("expires_at")
        if expires_at:
            try:
                if datetime.fromisoformat(str(expires_at)) < datetime.now(ZoneInfo("Asia/Shanghai")):
                    return None
            except ValueError:
                pass
        path = Path(value.get("object_key") or "")
        if not path.is_file() or self.export_dir.resolve() not in path.resolve().parents:
            return None
        return {**value, "path": path, "content_type": CONTENT_TYPES.get(value["format"], "application/octet-stream")}

    def _write(self, path: Path, export_format: str, record: Dict[str, Any], task: Dict[str, Any]) -> None:
        envelope = {
            "schema_version": record.get("schema_version", "1.0"),
            "tool_id": record["tool_id"],
            "task_id": record["task_id"],
            "record_id": record["id"],
            "created_at": record["created_at"],
            "result": record["result"],
        }
        if export_format in {"json", "database"}:
            path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        elif export_format == "csv":
            self._write_csv(path, record["result"])
        elif export_format == "xml":
            root = ET.Element("semanticResult", {"toolId": record["tool_id"], "recordId": record["id"]})
            self._xml_value(root, "result", record["result"])
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        elif export_format == "rdf":
            path.write_text(self._rdf(record), encoding="utf-8")
        elif export_format == "report":
            path.write_text(self._report(record, task), encoding="utf-8")

    @staticmethod
    def _rows(result: Any) -> List[Dict[str, Any]]:
        if isinstance(result, list):
            return [item if isinstance(item, dict) else {"value": item} for item in result]
        if isinstance(result, dict):
            rows: List[Dict[str, Any]] = []
            for section, value in result.items():
                if isinstance(value, list):
                    for item in value:
                        rows.append({"section": section, **(item if isinstance(item, dict) else {"value": item})})
            return rows or [{key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in result.items()}]
        return [{"value": result}]

    def _write_csv(self, path: Path, result: Any) -> None:
        rows = self._rows(result)
        fields: List[str] = []
        for row in rows:
            fields.extend(key for key in row if key not in fields)

        def _cell(value: Any) -> Any:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            return _csv_safe(value)

        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields or ["value"], extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                # 公式注入防护：单元格值经 _csv_safe 转义（2026-11-24）
                writer.writerow({key: _cell(value) for key, value in row.items()})

    @classmethod
    def _xml_value(cls, parent: ET.Element, name: str, value: Any) -> None:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", str(name)) or "item"
        element = ET.SubElement(parent, safe_name)
        if isinstance(value, dict):
            for key, child in value.items():
                cls._xml_value(element, key, child)
        elif isinstance(value, list):
            for child in value:
                cls._xml_value(element, "item", child)
        elif value is not None:
            element.text = str(value)

    @staticmethod
    def _escape_rdf(value: Any) -> str:
        return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def _rdf(self, record: Dict[str, Any]) -> str:
        triples = record["result"].get("triples", []) if isinstance(record["result"], dict) else []
        lines: List[str] = []
        base = "https://semantic-toolkit.local/resource/"
        for index, triple in enumerate(triples):
            subject = self._escape_rdf(triple.get("subject") or triple.get("head") or "")
            predicate = self._escape_rdf(triple.get("predicate") or triple.get("relation") or "relatedTo")
            obj = self._escape_rdf(triple.get("object") or triple.get("tail") or "")
            node = f"<{base}{record['id']}/triple/{index + 1}>"
            lines.extend([
                f'{node} <{base}subject> "{subject}" .',
                f'{node} <{base}predicate> "{predicate}" .',
                f'{node} <{base}object> "{obj}" .',
            ])
        return "\n".join(lines) + ("\n" if lines else "")

    @staticmethod
    def _report(record: Dict[str, Any], task: Dict[str, Any]) -> str:
        result = record["result"]
        return "\n".join([
            f"# {get_contract(record['tool_id']).name}结果报告",
            "",
            f"- 任务编号：{record['task_id']}",
            f"- 结果编号：{record['id']}",
            f"- 完成时间：{record['created_at']}",
            f"- 模型版本：{task.get('model_version') or '-'}",
            "",
            "## 结构化结果",
            "",
            "```json",
            json.dumps(result, ensure_ascii=False, indent=2),
            "```",
            "",
        ])


export_service = ExportService()
