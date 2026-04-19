from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass(frozen=True)
class FileHtmlContentProvider:
    """
    Provider de contenu HTML à partir de fichiers :
      template_studio/html_sources/<template_id>.html
    """

    sources_dir: Path
    encoding: str = "utf-8"

    def __call__(self, template_id: str) -> str:
        template_id = str(template_id).strip()
        file_path = self.sources_dir / f"{template_id}.html"
        if not file_path.exists():
            raise FileNotFoundError(f"Source HTML introuvable: {file_path}")
        return file_path.read_text(encoding=self.encoding)


def fallback_provider(
    primary: Callable[[str], str],
    fallback: Callable[[str], str],
) -> Callable[[str], str]:
    """
    Utilise `primary` si disponible, sinon `fallback`.
    """

    def _provider(template_id: str) -> str:
        try:
            return primary(template_id)
        except FileNotFoundError:
            return fallback(template_id)

    return _provider


def brand_provider(
    common_sources_dir: Path,
    brand_sources_dir: Optional[Path] = None,
    *,
    encoding: str = "utf-8",
) -> Callable[[str], str]:
    """
    Provider multi-domaine:
    - lit d'abord `template_studio/brands/<brand>/html_sources/<template_id>.html`
    - sinon fallback vers `template_studio/html_sources/<template_id>.html`
    """
    common = FileHtmlContentProvider(sources_dir=common_sources_dir, encoding=encoding)
    if brand_sources_dir is None:
        return common
    brand = FileHtmlContentProvider(sources_dir=brand_sources_dir, encoding=encoding)
    return fallback_provider(brand, common)

