"""
Phase 7 regional auditors package.

PHASE7_REGISTRY maps audit_type strings to their AuditorBase subclasses.
AuditService._scan_single_region iterates this registry instead of
maintaining a separate if-block per auditor.

Global-service auditors (CloudFront, Route53) are NOT in the registry
because they run once per account, not once per region.
"""
from app.aws.auditors.sqs_auditor import SQSAuditor
from app.aws.auditors.sns_auditor import SNSAuditor
from app.aws.auditors.apigateway_auditor import APIGatewayAuditor
from app.aws.auditors.stepfunctions_auditor import StepFunctionsAuditor
from app.aws.auditors.ecs_auditor import ECSAuditor
from app.aws.auditors.redshift_auditor import RedshiftAuditor
from app.aws.auditors.kinesis_auditor import KinesisAuditor
from app.aws.auditors.glue_auditor import GlueAuditor

# Global-service auditors (not per-region)
from app.aws.auditors.cloudfront_auditor import CloudFrontAuditor
from app.aws.auditors.route53_auditor import Route53Auditor

# Registry used by AuditService._scan_single_region.
# Key   = audit_type string from AuditRequest.audit_types
# Value = AuditorBase subclass; instantiated as Cls(session, region)
PHASE7_REGISTRY: dict = {
    'sqs': SQSAuditor,
    'sns': SNSAuditor,
    'apigateway': APIGatewayAuditor,
    'stepfunctions': StepFunctionsAuditor,
    'ecs': ECSAuditor,
    'redshift': RedshiftAuditor,
    'kinesis': KinesisAuditor,
    'glue': GlueAuditor,
}

__all__ = [
    "SQSAuditor",
    "SNSAuditor",
    "APIGatewayAuditor",
    "StepFunctionsAuditor",
    "ECSAuditor",
    "RedshiftAuditor",
    "KinesisAuditor",
    "GlueAuditor",
    "CloudFrontAuditor",
    "Route53Auditor",
    "PHASE7_REGISTRY",
]
