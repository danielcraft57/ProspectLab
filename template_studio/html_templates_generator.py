from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .template_repo import JsonTemplatesRepository


@dataclass(frozen=True)
class HtmlSpec:
    id: str
    name: str
    subject: str


class HtmlTemplatesGenerator:
    """
    Génère/maintient templates_data*.json à partir :
    - d'une liste de specs (id, name, subject)
    - d'un provider de contenu HTML par id (string HTML déjà "finale" avec placeholders)
    """

    def __init__(
        self,
        repo: JsonTemplatesRepository,
        html_specs: Sequence[Dict[str, Any]],
        get_html_content_by_id: Callable[[str], str],
    ):
        self.repo = repo
        self.html_specs = list(html_specs)
        self.get_html_content_by_id = get_html_content_by_id

    def build_html_template_record(self, spec: Dict[str, Any], content: str, now_iso: str) -> Dict[str, Any]:
        return {
            "id": spec["id"],
            "name": spec["name"],
            "category": "html_email",
            "subject": spec["subject"],
            "content": content,
            "is_html": True,
            "created_at": now_iso,
            "updated_at": now_iso,
        }

    def write_default_html_only(self) -> int:
        now_iso = self.repo.now_iso()
        default_templates: List[Dict[str, Any]] = []
        for spec in self.html_specs:
            content = self.get_html_content_by_id(spec["id"])
            default_templates.append(self.build_html_template_record(spec, content, now_iso))
        self.repo.ensure_default_exists(write_default=True, default_templates=default_templates)
        return len(default_templates)

    def restore_from_default(self) -> int:
        return self.repo.restore_from_default()

    def upsert_missing_templates(self) -> int:
        """
        Ajoute les templates HTML manquants dans templates_data.json, sans écraser les existants.
        """
        now_iso = self.repo.now_iso()
        data = {"templates": self.repo.load_templates()}
        templates = data.get("templates", []) or []

        existing_ids = {t.get("id") for t in templates}
        added = 0
        for spec in self.html_specs:
            tpl_id = spec["id"]
            if tpl_id in existing_ids:
                continue
            content = self.get_html_content_by_id(tpl_id)
            templates.append(self.build_html_template_record(spec, content, now_iso))
            added += 1

        self.repo.save_templates(templates)
        return added

    def upsert_templates_by_ids(self, template_ids: Sequence[str]) -> int:
        """
        Régénère uniquement les IDs demandés depuis les sources HTML et les fusionne
        dans templates_data.json (et dans templates_data.default.json s'il existe),
        sans toucher aux autres entrées.
        """
        now_iso = self.repo.now_iso()
        specs_by_id = {s["id"]: s for s in self.html_specs}
        wanted = [str(x).strip() for x in template_ids if str(x).strip()]
        if not wanted:
            return 0

        templates = list(self.repo.load_templates() or [])
        index_by_id = {t.get("id"): i for i, t in enumerate(templates) if t.get("id")}

        built: List[Dict[str, Any]] = []
        for tid in wanted:
            spec = specs_by_id.get(tid)
            if not spec:
                continue
            content = self.get_html_content_by_id(tid)
            record = self.build_html_template_record(spec, content, now_iso)
            if tid in index_by_id:
                prev = templates[index_by_id[tid]]
                record["created_at"] = prev.get("created_at") or now_iso
                templates[index_by_id[tid]] = record
            else:
                templates.append(record)
            built.append(record)

        self.repo.save_templates(templates)

        if self.repo.default_file and self.repo.default_file.exists():
            try:
                with open(self.repo.default_file, "r", encoding="utf-8") as f:
                    payload = json.load(f) or {}
                default_list = list(payload.get("templates", []) or [])
                d_index = {t.get("id"): i for i, t in enumerate(default_list) if t.get("id")}
                for record in built:
                    tid = record.get("id")
                    if not tid:
                        continue
                    if tid in d_index:
                        prev = default_list[d_index[tid]]
                        record_d = dict(record)
                        record_d["created_at"] = prev.get("created_at") or record_d.get("created_at")
                        default_list[d_index[tid]] = record_d
                    else:
                        default_list.append(dict(record))
                with open(self.repo.default_file, "w", encoding="utf-8") as f:
                    json.dump({"templates": default_list}, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        return len(built)

