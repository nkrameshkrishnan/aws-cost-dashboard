"""
Abstract base class for all regional auditors.

Regional auditors (app/aws/auditors/) must subclass AuditorBase and implement
run(**kwargs) -> dict.  The returned dict is stored directly in the region
results under the key  ``<audit_type>_audit``  and later merged by
AuditService.run_full_audit().

Global auditors (CloudFront, Route53) take only a session in __init__ and are
not expected to subclass AuditorBase because they never run per-region.

Example
-------
class MyAuditor(AuditorBase):
    def run(self, days: int = 30, **kwargs) -> dict:
        findings = self._do_work(days)
        return {"my_findings": findings}
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import boto3

logger = logging.getLogger(__name__)


class AuditorBase(ABC):
    """
    Base class for all per-region auditors.

    Subclasses receive a boto3 Session and a region string in ``__init__``
    and must implement ``run(**kwargs) -> dict`` which executes all audit
    checks for that region and returns results as a plain dict.
    """

    def __init__(self, session: boto3.Session, region: str) -> None:
        self.session = session
        self.region = region

    @abstractmethod
    def run(self, **kwargs: Any) -> dict:
        """
        Execute all audit checks for this auditor.

        Returns a dict whose keys map to the fields that AuditService will
        merge into the corresponding *AuditResults schema.  For example::

            {"unused_queues": [...], "high_retention_queues": [...]}

        Implementations should catch and log errors internally rather than
        propagating them, so that a single failing auditor does not abort the
        entire region scan.
        """
        raise NotImplementedError
