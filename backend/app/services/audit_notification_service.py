"""
Audit notification service for sending FinOps audit reports via Microsoft Teams webhooks.
"""
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.teams_webhook import TeamsWebhook
from app.integrations.teams import TeamsNotificationService
from app.schemas.audit import FullAuditResults

logger = logging.getLogger(__name__)


class AuditNotificationService:
    """Service for sending audit reports to Teams webhooks."""

    @staticmethod
    def _extract_top_opportunities(audit_results: FullAuditResults) -> List[Dict[str, Any]]:
        """
        Extract top cost-saving opportunities from audit results.

        Args:
            audit_results: Complete audit results

        Returns:
            List of top opportunities sorted by savings
        """
        opportunities = []

        # EC2 idle instances
        if audit_results.ec2_audit and audit_results.ec2_audit.idle_instances:
            total_savings = sum(i.potential_monthly_savings for i in audit_results.ec2_audit.idle_instances)
            if total_savings > 0:
                opportunities.append({
                    'type': 'EC2 Idle Instances',
                    'count': len(audit_results.ec2_audit.idle_instances),
                    'savings': total_savings,
                    'description': 'Instances with low CPU utilization'
                })

        # EC2 stopped instances
        if audit_results.ec2_audit and audit_results.ec2_audit.stopped_instances:
            total_cost = sum(i.estimated_ebs_cost for i in audit_results.ec2_audit.stopped_instances)
            if total_cost > 0:
                opportunities.append({
                    'type': 'EC2 Stopped Instances',
                    'count': len(audit_results.ec2_audit.stopped_instances),
                    'savings': total_cost,
                    'description': 'Stopped instances still incurring EBS costs'
                })

        # EBS unattached volumes
        if audit_results.ebs_audit and audit_results.ebs_audit.unattached_volumes:
            total_savings = sum(v.estimated_monthly_cost for v in audit_results.ebs_audit.unattached_volumes)
            if total_savings > 0:
                opportunities.append({
                    'type': 'Unattached EBS Volumes',
                    'count': len(audit_results.ebs_audit.unattached_volumes),
                    'savings': total_savings,
                    'description': 'Volumes not attached to any instance'
                })

        # EBS old snapshots
        if audit_results.ebs_audit and audit_results.ebs_audit.old_snapshots:
            total_savings = sum(s.estimated_monthly_cost for s in audit_results.ebs_audit.old_snapshots)
            if total_savings > 0:
                opportunities.append({
                    'type': 'Old EBS Snapshots',
                    'count': len(audit_results.ebs_audit.old_snapshots),
                    'savings': total_savings,
                    'description': 'Snapshots older than 90 days'
                })

        # Elastic IPs unattached
        if audit_results.eip_audit and audit_results.eip_audit.unattached_ips:
            total_savings = sum(ip.estimated_monthly_cost for ip in audit_results.eip_audit.unattached_ips)
            if total_savings > 0:
                opportunities.append({
                    'type': 'Unattached Elastic IPs',
                    'count': len(audit_results.eip_audit.unattached_ips),
                    'savings': total_savings,
                    'description': 'Elastic IPs not associated with instances'
                })

        # RDS idle instances
        if audit_results.rds_audit and audit_results.rds_audit.idle_instances:
            total_savings = sum(i.potential_monthly_savings for i in audit_results.rds_audit.idle_instances)
            if total_savings > 0:
                opportunities.append({
                    'type': 'RDS Idle Instances',
                    'count': len(audit_results.rds_audit.idle_instances),
                    'savings': total_savings,
                    'description': 'RDS databases with low CPU/connections'
                })

        # Lambda unused functions
        if audit_results.lambda_audit and audit_results.lambda_audit.unused_functions:
            total_savings = sum(f.estimated_monthly_cost for f in audit_results.lambda_audit.unused_functions)
            if total_savings > 0:
                opportunities.append({
                    'type': 'Unused Lambda Functions',
                    'count': len(audit_results.lambda_audit.unused_functions),
                    'savings': total_savings,
                    'description': 'Functions not invoked in 30+ days'
                })

        # Lambda over-provisioned functions
        if audit_results.lambda_audit and audit_results.lambda_audit.over_provisioned_functions:
            total_savings = sum(f.potential_monthly_savings for f in audit_results.lambda_audit.over_provisioned_functions)
            if total_savings > 0:
                opportunities.append({
                    'type': 'Over-provisioned Lambda',
                    'count': len(audit_results.lambda_audit.over_provisioned_functions),
                    'savings': total_savings,
                    'description': 'Functions using less memory than allocated'
                })

        # S3 buckets without lifecycle
        if audit_results.s3_audit and audit_results.s3_audit.buckets_without_lifecycle:
            total_savings = sum(b.potential_monthly_savings for b in audit_results.s3_audit.buckets_without_lifecycle)
            if total_savings > 0:
                opportunities.append({
                    'type': 'S3 Lifecycle Opportunities',
                    'count': len(audit_results.s3_audit.buckets_without_lifecycle),
                    'savings': total_savings,
                    'description': 'Buckets without lifecycle policies'
                })

        # Load balancers with no targets
        if audit_results.lb_audit and audit_results.lb_audit.lbs_no_targets:
            total_savings = sum(lb.estimated_monthly_cost for lb in audit_results.lb_audit.lbs_no_targets)
            if total_savings > 0:
                opportunities.append({
                    'type': 'Load Balancers (No Targets)',
                    'count': len(audit_results.lb_audit.lbs_no_targets),
                    'savings': total_savings,
                    'description': 'Load balancers with no backend targets'
                })

        # NAT Gateways idle
        if audit_results.nat_gateway_audit and audit_results.nat_gateway_audit.idle_gateways:
            total_savings = sum(ng.potential_monthly_savings for ng in audit_results.nat_gateway_audit.idle_gateways)
            if total_savings > 0:
                opportunities.append({
                    'type': 'Idle NAT Gateways',
                    'count': len(audit_results.nat_gateway_audit.idle_gateways),
                    'savings': total_savings,
                    'description': 'NAT gateways with minimal traffic'
                })

        # Sort by savings (descending) and return top 10
        opportunities.sort(key=lambda x: x['savings'], reverse=True)
        return opportunities[:10]

    @staticmethod
    def send_audit_report_to_teams(
        db: Session,
        audit_results: FullAuditResults,
        webhook_id: int = None
    ) -> dict:
        """
        Send audit report to Teams webhook(s).

        Args:
            db: Database session
            audit_results: Complete audit results to send
            webhook_id: Optional specific webhook ID. If None, sends to all active webhooks with audit reports enabled

        Returns:
            Dictionary with send results
        """
        # Fetch webhooks
        if webhook_id:
            webhooks = db.query(TeamsWebhook).filter(
                TeamsWebhook.id == webhook_id,
                TeamsWebhook.is_active == True
            ).all()
        else:
            webhooks = db.query(TeamsWebhook).filter(
                TeamsWebhook.is_active == True,
                TeamsWebhook.send_audit_reports == True
            ).all()

        if not webhooks:
            return {
                "success": False,
                "error": "No active webhooks configured for audit reports"
            }

        # Extract top opportunities
        top_opportunities = AuditNotificationService._extract_top_opportunities(audit_results)

        # Calculate total savings from summary
        total_savings = audit_results.summary.total_potential_savings
        total_findings = audit_results.summary.total_findings

        notifications_sent = 0
        errors = []

        for webhook in webhooks:
            try:
                if webhook.webhook_type == 'power_automate':
                    # Send to Power Automate
                    data = {
                        'total_findings': total_findings,
                        'potential_savings': total_savings,
                        'top_findings': top_opportunities,
                        'account_name': audit_results.account_name
                    }
                    pa_data = TeamsNotificationService.convert_to_power_automate_format(
                        'audit_report',
                        data
                    )
                    success = TeamsNotificationService.send_to_power_automate(
                        webhook.webhook_url,
                        pa_data
                    )
                else:
                    # Send adaptive card to Teams
                    card = TeamsNotificationService.create_audit_findings_card(
                        total_findings=total_findings,
                        potential_savings=total_savings,
                        top_findings=top_opportunities,
                        account_name=audit_results.account_name
                    )
                    success = TeamsNotificationService.send_adaptive_card(
                        webhook.webhook_url,
                        card
                    )

                if success:
                    webhook.last_sent_at = datetime.now()
                    db.commit()
                    notifications_sent += 1
                    logger.info(f"Sent audit report to webhook '{webhook.name}'")
                else:
                    error_msg = f"Failed to send to webhook '{webhook.name}'"
                    errors.append(error_msg)
                    logger.error(error_msg)

            except Exception as e:
                error_msg = f"Error sending to webhook '{webhook.name}': {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        return {
            "success": notifications_sent > 0,
            "notifications_sent": notifications_sent,
            "webhooks_checked": len(webhooks),
            "total_findings": total_findings,
            "total_savings": total_savings,
            "top_opportunities": len(top_opportunities),
            "errors": errors
        }
