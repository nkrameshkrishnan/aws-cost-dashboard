"""
Unified auditor package.

All auditors implement AuditorBase so they can be driven by the registry
in AuditService without per-auditor branching.
"""
from app.auditors.base import AuditorBase

__all__ = ["AuditorBase"]
