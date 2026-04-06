import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TemplateRecord:
    id: str
    name: str
    category: str
    subject: str
    content: str
    is_html: bool
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "subject": self.subject,
            "content": self.content,
            "is_html": self.is_html,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class JsonTemplatesRepository:
    """
    Repository simple sur JSON (source de vérité en local si la BDD n'est pas disponible).
    """

    def __init__(self, templates_file: Path, default_file: Optional[Path] = None):
        self.templates_file = templates_file
        self.default_file = default_file

    def load_templates(self) -> List[Dict[str, Any]]:
        if not self.templates_file.exists():
            return []
        try:
            with open(self.templates_file, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            return data.get("templates", []) or []
        except Exception:
            return []

    def save_templates(self, templates: List[Dict[str, Any]]) -> None:
        payload = {"templates": templates}
        with open(self.templates_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def ensure_default_exists(
        self,
        write_default: bool,
        default_templates: List[Dict[str, Any]],
    ) -> Path:
        if not self.default_file:
            raise ValueError("default_file est requis pour ensure_default_exists().")

        if write_default:
            with open(self.default_file, "w", encoding="utf-8") as f:
                json.dump({"templates": default_templates}, f, ensure_ascii=False, indent=2)
        return self.default_file

    def restore_from_default(self) -> int:
        if not self.default_file:
            raise ValueError("default_file est requis pour restore_from_default().")
        if not self.default_file.exists():
            return 0

        import shutil

        shutil.copy(self.default_file, self.templates_file)
        with open(self.default_file, "r", encoding="utf-8") as f:
            payload = json.load(f) or {}
        return len(payload.get("templates", []) or [])

    @staticmethod
    def now_iso() -> str:
        return datetime.now().isoformat()

