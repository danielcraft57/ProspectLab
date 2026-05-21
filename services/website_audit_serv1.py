"""Alias rétrocompatibilité — utiliser services.website_audit_agent."""

from services.website_audit_agent import (  # noqa: F401
    build_agent_pdf_command,
    generate_audit_pdf_via_agent,
    generate_audit_pdf_on_serv1,
    _build_command,
)
