"""
PDF report generator using ReportLab for FinOps audit reports and cost summaries.
"""
import io
from datetime import datetime
from typing import List, Dict, Any, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, Image, KeepTogether
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.pdfgen import canvas

from app.schemas.audit import FullAuditResults


class PDFReportGenerator:
    """Generate professional PDF reports for FinOps audits and cost analysis."""

    def __init__(self, pagesize=letter):
        """
        Initialize PDF generator.

        Args:
            pagesize: Page size (letter or A4)
        """
        self.pagesize = pagesize
        self.width, self.height = pagesize
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1E3A8A'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))

        # Heading2 style
        self.styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1E40AF'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        ))

        # Heading3 style
        self.styles.add(ParagraphStyle(
            name='CustomHeading3',
            parent=self.styles['Heading3'],
            fontSize=13,
            textColor=colors.HexColor('#3B82F6'),
            spaceAfter=8,
            fontName='Helvetica-Bold'
        ))

        # Summary box style
        self.styles.add(ParagraphStyle(
            name='SummaryBox',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.black,
            alignment=TA_LEFT,
            fontName='Helvetica'
        ))

    def _create_header_footer(self, canvas_obj, doc):
        """Add header and footer to each page."""
        canvas_obj.saveState()

        # Header
        canvas_obj.setFont('Helvetica-Bold', 10)
        canvas_obj.setFillColor(colors.HexColor('#1E3A8A'))
        canvas_obj.drawString(inch, self.height - 0.5 * inch, "AWS Cost Dashboard - FinOps Report")

        # Footer
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.grey)
        canvas_obj.drawString(
            inch, 0.5 * inch,
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        canvas_obj.drawRightString(
            self.width - inch, 0.5 * inch,
            f"Page {doc.page}"
        )

        canvas_obj.restoreState()

    def generate_audit_report(
        self,
        audit_results: FullAuditResults,
        include_charts: bool = True
    ) -> bytes:
        """
        Generate a comprehensive PDF audit report.

        Args:
            audit_results: Full audit results
            include_charts: Whether to include charts

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.pagesize,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch
        )

        story = []

        # Title Page
        story.append(Spacer(1, 1.5 * inch))
        story.append(Paragraph("FinOps Audit Report", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.3 * inch))

        # Account and timestamp info
        info_text = f"""
        <b>Account:</b> {audit_results.account_name}<br/>
        <b>Audit Date:</b> {audit_results.audit_timestamp.strftime('%Y-%m-%d %H:%M:%S')}<br/>
        <b>Total Findings:</b> {audit_results.summary.total_findings:,}<br/>
        <b>Potential Savings:</b> ${audit_results.summary.total_potential_savings:,.2f}/month
        """
        story.append(Paragraph(info_text, self.styles['SummaryBox']))
        story.append(PageBreak())

        # Executive Summary
        story.append(Paragraph("Executive Summary", self.styles['CustomHeading2']))
        story.append(Spacer(1, 0.2 * inch))

        summary_data = [
            ['Metric', 'Value'],
            ['Total Findings', f"{audit_results.summary.total_findings:,}"],
            ['Potential Monthly Savings', f"${audit_results.summary.total_potential_savings:,.2f}"],
            ['Critical Severity', f"{audit_results.summary.findings_by_severity.get('critical', 0):,}"],
            ['High Severity', f"{audit_results.summary.findings_by_severity.get('high', 0):,}"],
            ['Medium Severity', f"{audit_results.summary.findings_by_severity.get('medium', 0):,}"],
            ['Low Severity', f"{audit_results.summary.findings_by_severity.get('low', 0):,}"],
        ]

        summary_table = Table(summary_data, colWidths=[3 * inch, 2.5 * inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F4F6')]),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.3 * inch))

        # Top Opportunities
        if audit_results.summary.top_opportunities:
            story.append(Paragraph("Top Savings Opportunities", self.styles['CustomHeading2']))
            story.append(Spacer(1, 0.1 * inch))
            for idx, opportunity in enumerate(audit_results.summary.top_opportunities[:5], 1):
                story.append(Paragraph(f"{idx}. {opportunity}", self.styles['Normal']))
                story.append(Spacer(1, 0.05 * inch))

        story.append(PageBreak())

        # EC2 Findings
        if audit_results.ec2_audit and (audit_results.ec2_audit.idle_instances or audit_results.ec2_audit.stopped_instances):
            story.extend(self._generate_ec2_section(audit_results.ec2_audit))
            story.append(PageBreak())

        # EBS Findings
        if audit_results.ebs_audit and (audit_results.ebs_audit.unattached_volumes or audit_results.ebs_audit.old_snapshots):
            story.extend(self._generate_ebs_section(audit_results.ebs_audit))
            story.append(PageBreak())

        # RDS Findings
        if audit_results.rds_audit and audit_results.rds_audit.idle_instances:
            story.extend(self._generate_rds_section(audit_results.rds_audit))
            story.append(PageBreak())

        # Lambda Findings
        if audit_results.lambda_audit and (audit_results.lambda_audit.unused_functions or audit_results.lambda_audit.over_provisioned_functions):
            story.extend(self._generate_lambda_section(audit_results.lambda_audit))
            story.append(PageBreak())

        # S3 Findings
        if audit_results.s3_audit and (audit_results.s3_audit.buckets_without_lifecycle or audit_results.s3_audit.incomplete_multipart_uploads):
            story.extend(self._generate_s3_section(audit_results.s3_audit))
            story.append(PageBreak())

        # NAT Gateway Findings
        if audit_results.nat_gateway_audit and (audit_results.nat_gateway_audit.idle_gateways or audit_results.nat_gateway_audit.unused_gateways):
            story.extend(self._generate_nat_gateway_section(audit_results.nat_gateway_audit))
            story.append(PageBreak())

        # Build PDF
        doc.build(story, onFirstPage=self._create_header_footer, onLaterPages=self._create_header_footer)

        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    def _generate_ec2_section(self, ec2_audit) -> List:
        """Generate EC2 findings section."""
        elements = []

        elements.append(Paragraph("EC2 Findings", self.styles['CustomHeading2']))
        elements.append(Spacer(1, 0.1 * inch))

        # Summary
        summary_text = f"""
        <b>Idle Instances:</b> {len(ec2_audit.idle_instances)}<br/>
        <b>Stopped Instances:</b> {len(ec2_audit.stopped_instances)}<br/>
        <b>Total Potential Savings:</b> ${ec2_audit.total_potential_savings:,.2f}/month
        """
        elements.append(Paragraph(summary_text, self.styles['SummaryBox']))
        elements.append(Spacer(1, 0.2 * inch))

        # Idle instances table
        if ec2_audit.idle_instances:
            elements.append(Paragraph("Idle Instances (Low CPU Utilization)", self.styles['CustomHeading3']))
            elements.append(Spacer(1, 0.1 * inch))

            table_data = [['Instance ID', 'Type', 'Region', 'Avg CPU %', 'Est. Monthly Cost', 'Potential Savings']]
            for instance in ec2_audit.idle_instances[:20]:  # Limit to 20 for space
                table_data.append([
                    instance.instance_id[:12] + '...',
                    instance.instance_type,
                    instance.region,
                    f"{instance.avg_cpu_utilization:.1f}%",
                    f"${instance.estimated_monthly_cost:.2f}",
                    f"${instance.potential_monthly_savings:.2f}"
                ])

            table = Table(table_data, colWidths=[1.2*inch, 0.9*inch, 0.9*inch, 0.8*inch, 1*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DC2626')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEE2E2')]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        # Stopped instances table
        if ec2_audit.stopped_instances:
            elements.append(Paragraph("Stopped Instances (Still Incurring EBS Costs)", self.styles['CustomHeading3']))
            elements.append(Spacer(1, 0.1 * inch))

            table_data = [['Instance ID', 'Type', 'Region', 'Days Stopped', 'EBS Cost']]
            for instance in ec2_audit.stopped_instances[:15]:
                table_data.append([
                    instance.instance_id[:12] + '...',
                    instance.instance_type,
                    instance.region,
                    str(instance.days_stopped),
                    f"${instance.estimated_ebs_cost:.2f}"
                ])

            table = Table(table_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F59E0B')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEF3C7')]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _generate_ebs_section(self, ebs_audit) -> List:
        """Generate EBS findings section."""
        elements = []

        elements.append(Paragraph("EBS Findings", self.styles['CustomHeading2']))
        elements.append(Spacer(1, 0.1 * inch))

        # Summary
        summary_text = f"""
        <b>Unattached Volumes:</b> {len(ebs_audit.unattached_volumes)}<br/>
        <b>Old Snapshots:</b> {len(ebs_audit.old_snapshots)}<br/>
        <b>Total Potential Savings:</b> ${ebs_audit.total_potential_savings:,.2f}/month
        """
        elements.append(Paragraph(summary_text, self.styles['SummaryBox']))
        elements.append(Spacer(1, 0.2 * inch))

        # Unattached volumes table
        if ebs_audit.unattached_volumes:
            elements.append(Paragraph("Unattached EBS Volumes", self.styles['CustomHeading3']))
            elements.append(Spacer(1, 0.1 * inch))

            table_data = [['Volume ID', 'Size (GB)', 'Type', 'Region', 'Days Unattached', 'Monthly Cost']]
            for volume in ebs_audit.unattached_volumes[:20]:
                table_data.append([
                    volume.volume_id[:12] + '...',
                    str(volume.size_gb),
                    volume.volume_type,
                    volume.region,
                    str(volume.days_unattached),
                    f"${volume.estimated_monthly_cost:.2f}"
                ])

            table = Table(table_data, colWidths=[1.2*inch, 0.8*inch, 0.8*inch, 0.9*inch, 1*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DC2626')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEE2E2')]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _generate_rds_section(self, rds_audit) -> List:
        """Generate RDS findings section."""
        elements = []

        elements.append(Paragraph("RDS Findings", self.styles['CustomHeading2']))
        elements.append(Spacer(1, 0.1 * inch))

        # Summary
        summary_text = f"""
        <b>Idle Instances:</b> {len(rds_audit.idle_instances)}<br/>
        <b>Total Potential Savings:</b> ${rds_audit.total_potential_savings:,.2f}/month
        """
        elements.append(Paragraph(summary_text, self.styles['SummaryBox']))
        elements.append(Spacer(1, 0.2 * inch))

        # Idle instances table
        if rds_audit.idle_instances:
            elements.append(Paragraph("Idle RDS Instances", self.styles['CustomHeading3']))
            elements.append(Spacer(1, 0.1 * inch))

            table_data = [['Instance ID', 'Class', 'Engine', 'Region', 'Avg CPU %', 'Avg Connections', 'Monthly Cost']]
            for instance in rds_audit.idle_instances[:15]:
                table_data.append([
                    instance.db_instance_id[:15] + '...',
                    instance.db_instance_class,
                    instance.engine,
                    instance.region,
                    f"{instance.avg_cpu_utilization:.1f}%",
                    f"{instance.avg_connections:.0f}",
                    f"${instance.estimated_monthly_cost:.2f}"
                ])

            table = Table(table_data, colWidths=[1.2*inch, 0.9*inch, 0.7*inch, 0.8*inch, 0.7*inch, 0.8*inch, 0.9*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DC2626')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEE2E2')]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _generate_lambda_section(self, lambda_audit) -> List:
        """Generate Lambda findings section."""
        elements = []

        elements.append(Paragraph("Lambda Findings", self.styles['CustomHeading2']))
        elements.append(Spacer(1, 0.1 * inch))

        # Summary
        summary_text = f"""
        <b>Unused Functions:</b> {len(lambda_audit.unused_functions)}<br/>
        <b>Over-Provisioned Functions:</b> {len(lambda_audit.over_provisioned_functions)}<br/>
        <b>Total Potential Savings:</b> ${lambda_audit.total_potential_savings:,.2f}/month
        """
        elements.append(Paragraph(summary_text, self.styles['SummaryBox']))
        elements.append(Spacer(1, 0.2 * inch))

        # Unused functions table
        if lambda_audit.unused_functions:
            elements.append(Paragraph("Unused Lambda Functions (No Invocations)", self.styles['CustomHeading3']))
            elements.append(Spacer(1, 0.1 * inch))

            table_data = [['Function Name', 'Region', 'Runtime', 'Memory MB', 'Days Unused', 'Monthly Cost']]
            for func in lambda_audit.unused_functions[:15]:
                table_data.append([
                    func.function_name[:20] + '...' if len(func.function_name) > 20 else func.function_name,
                    func.region,
                    func.runtime,
                    str(func.memory_mb),
                    str(func.days_since_invocation),
                    f"${func.estimated_monthly_cost:.2f}"
                ])

            table = Table(table_data, colWidths=[1.5*inch, 0.8*inch, 0.9*inch, 0.8*inch, 0.9*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DC2626')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEE2E2')]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        # Over-provisioned functions table
        if lambda_audit.over_provisioned_functions:
            elements.append(Paragraph("Over-Provisioned Lambda Functions", self.styles['CustomHeading3']))
            elements.append(Spacer(1, 0.1 * inch))

            table_data = [['Function Name', 'Region', 'Allocated MB', 'Avg Used MB', 'Utilization %', 'Potential Savings']]
            for func in lambda_audit.over_provisioned_functions[:15]:
                table_data.append([
                    func.function_name[:20] + '...' if len(func.function_name) > 20 else func.function_name,
                    func.region,
                    str(func.configured_memory_mb),
                    f"{func.avg_memory_used_mb:.0f}",
                    f"{func.memory_utilization_percent:.1f}%",
                    f"${func.potential_monthly_savings:.2f}"
                ])

            table = Table(table_data, colWidths=[1.5*inch, 0.8*inch, 0.9*inch, 0.9*inch, 1*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F59E0B')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEF3C7')]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _generate_s3_section(self, s3_audit) -> List:
        """Generate S3 findings section."""
        elements = []

        elements.append(Paragraph("S3 Findings", self.styles['CustomHeading2']))
        elements.append(Spacer(1, 0.1 * inch))

        # Summary
        summary_text = f"""
        <b>Buckets Without Lifecycle:</b> {len(s3_audit.buckets_without_lifecycle)}<br/>
        <b>Incomplete Multipart Uploads:</b> {len(s3_audit.incomplete_multipart_uploads)}<br/>
        <b>Total Potential Savings:</b> ${s3_audit.total_potential_savings:,.2f}/month
        """
        elements.append(Paragraph(summary_text, self.styles['SummaryBox']))
        elements.append(Spacer(1, 0.2 * inch))

        # Buckets without lifecycle table
        if s3_audit.buckets_without_lifecycle:
            elements.append(Paragraph("Buckets Without Lifecycle Policies", self.styles['CustomHeading3']))
            elements.append(Spacer(1, 0.1 * inch))

            table_data = [['Bucket Name', 'Size (GB)', 'Object Count', 'Monthly Cost', 'Potential Savings']]
            for bucket in s3_audit.buckets_without_lifecycle[:15]:
                table_data.append([
                    bucket.bucket_name[:25] + '...' if len(bucket.bucket_name) > 25 else bucket.bucket_name,
                    f"{bucket.total_size_gb:.2f}",
                    f"{bucket.object_count:,}",
                    f"${bucket.estimated_monthly_cost:.2f}",
                    f"${bucket.potential_monthly_savings:.2f}"
                ])

            table = Table(table_data, colWidths=[1.8*inch, 0.9*inch, 1*inch, 1*inch, 1.1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F59E0B')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEF3C7')]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        # Incomplete multipart uploads table
        if s3_audit.incomplete_multipart_uploads:
            elements.append(Paragraph("Incomplete Multipart Uploads", self.styles['CustomHeading3']))
            elements.append(Spacer(1, 0.1 * inch))

            table_data = [['Bucket Name', 'Key', 'Days Old', 'Size (GB)', 'Monthly Cost']]
            for upload in s3_audit.incomplete_multipart_uploads[:15]:
                table_data.append([
                    upload.bucket_name[:20] + '...' if len(upload.bucket_name) > 20 else upload.bucket_name,
                    upload.key[:25] + '...' if len(upload.key) > 25 else upload.key,
                    str(upload.days_old),
                    f"{upload.estimated_size_gb:.2f}",
                    f"${upload.estimated_monthly_cost:.2f}"
                ])

            table = Table(table_data, colWidths=[1.3*inch, 1.8*inch, 0.8*inch, 0.9*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DC2626')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEE2E2')]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _generate_nat_gateway_section(self, nat_gateway_audit) -> List:
        """Generate NAT Gateway findings section."""
        elements = []

        elements.append(Paragraph("NAT Gateway Findings", self.styles['CustomHeading2']))
        elements.append(Spacer(1, 0.1 * inch))

        # Summary
        summary_text = f"""
        <b>Idle Gateways:</b> {len(nat_gateway_audit.idle_gateways)}<br/>
        <b>Unused Gateways:</b> {len(nat_gateway_audit.unused_gateways)}<br/>
        <b>Total Potential Savings:</b> ${nat_gateway_audit.total_potential_savings:,.2f}/month
        """
        elements.append(Paragraph(summary_text, self.styles['SummaryBox']))
        elements.append(Spacer(1, 0.2 * inch))

        # Idle gateways table
        if nat_gateway_audit.idle_gateways:
            elements.append(Paragraph("Idle NAT Gateways (Low Traffic)", self.styles['CustomHeading3']))
            elements.append(Spacer(1, 0.1 * inch))

            table_data = [['NAT Gateway ID', 'Region', 'Avg GB Out/Day', 'Monthly Cost', 'Potential Savings']]
            for gw in nat_gateway_audit.idle_gateways[:15]:
                table_data.append([
                    gw.nat_gateway_id[:20] + '...' if len(gw.nat_gateway_id) > 20 else gw.nat_gateway_id,
                    gw.region,
                    f"{gw.avg_gb_out_per_day:.2f}",
                    f"${gw.estimated_monthly_cost:.2f}",
                    f"${gw.potential_monthly_savings:.2f}"
                ])

            table = Table(table_data, colWidths=[1.5*inch, 1*inch, 1.2*inch, 1.1*inch, 1.2*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F59E0B')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEF3C7')]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        # Unused gateways table
        if nat_gateway_audit.unused_gateways:
            elements.append(Paragraph("Unused NAT Gateways (No Traffic)", self.styles['CustomHeading3']))
            elements.append(Spacer(1, 0.1 * inch))

            table_data = [['NAT Gateway ID', 'Region', 'VPC ID', 'Days Active', 'Monthly Cost']]
            for gw in nat_gateway_audit.unused_gateways[:15]:
                table_data.append([
                    gw.nat_gateway_id[:20] + '...' if len(gw.nat_gateway_id) > 20 else gw.nat_gateway_id,
                    gw.region,
                    gw.vpc_id[:15] + '...' if len(gw.vpc_id) > 15 else gw.vpc_id,
                    str(gw.days_active),
                    f"${gw.estimated_monthly_cost:.2f}"
                ])

            table = Table(table_data, colWidths=[1.5*inch, 1*inch, 1.2*inch, 1*inch, 1.1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DC2626')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEE2E2')]),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def generate_cost_report(self, cost_data: Dict[str, Any], profile_name: str, include_charts: bool = True) -> bytes:
        """
        Generate PDF report for cost data (Dashboard).

        Args:
            cost_data: Dictionary containing daily_costs and service_breakdown
            profile_name: AWS profile name
            include_charts: Whether to include charts

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=self.pagesize, topMargin=1*inch, bottomMargin=1*inch)
        elements = []

        # Title
        elements.append(Paragraph('AWS Cost Report', self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.2 * inch))

        # Profile and date
        summary_data = [
            ['Profile:', profile_name],
            ['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        ]
        summary_table = Table(summary_data, colWidths=[1.5*inch, 4*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.3 * inch))

        # Daily costs section
        if 'daily_costs' in cost_data and cost_data['daily_costs']:
            elements.append(Paragraph('Daily Costs', self.styles['CustomHeading2']))
            elements.append(Spacer(1, 0.1 * inch))

            # Limit to first 30 rows for PDF readability
            daily_costs = cost_data['daily_costs'][:30]
            table_data = [['Date', 'Cost (USD)']]
            total_cost = 0

            for item in daily_costs:
                cost = float(item.get('cost', 0))
                total_cost += cost
                table_data.append([item.get('date', ''), f"${cost:.2f}"])

            table_data.append(['TOTAL', f"${total_cost:,.2f}"])

            table = Table(table_data, colWidths=[3*inch, 2*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#EEF2FF')]),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#DBEAFE')),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.3 * inch))

        # Service breakdown section
        if 'service_breakdown' in cost_data and cost_data['service_breakdown']:
            elements.append(Paragraph('Service Breakdown', self.styles['CustomHeading2']))
            elements.append(Spacer(1, 0.1 * inch))

            service_breakdown = cost_data['service_breakdown'][:20]  # Top 20 services
            table_data = [['Service', 'Cost (USD)', 'Percentage']]
            total_cost = sum(float(item.get('cost', 0)) for item in cost_data['service_breakdown'])

            for item in service_breakdown:
                cost = float(item.get('cost', 0))
                percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                table_data.append([
                    item.get('service', 'Unknown')[:40],  # Truncate long names
                    f"${cost:.2f}",
                    f"{percentage:.1f}%"
                ])

            table = Table(table_data, colWidths=[3.5*inch, 1.5*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#EEF2FF')]),
            ]))
            elements.append(table)

        # Build PDF
        doc.build(elements, onFirstPage=self._create_header_footer, onLaterPages=self._create_header_footer)
        return buffer.getvalue()

    def generate_forecast_report(self, forecast_data: Dict[str, Any], profile_name: str) -> bytes:
        """
        Generate PDF report for forecast data (Analytics).

        Args:
            forecast_data: Dictionary containing forecast predictions
            profile_name: AWS profile name

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=self.pagesize, topMargin=1*inch, bottomMargin=1*inch)
        elements = []

        # Title
        elements.append(Paragraph('AWS Cost Forecast Report', self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.2 * inch))

        # Profile and date
        summary_data = [
            ['Profile:', profile_name],
            ['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Forecast Period Start:', forecast_data.get('forecast_period_start', 'N/A')],
            ['Forecast Period End:', forecast_data.get('forecast_period_end', 'N/A')],
            ['Forecasted Cost:', f"${forecast_data.get('forecasted_cost', 0):,.2f}"]
        ]
        summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (1, -1), colors.HexColor('#DBEAFE')),
            ('FONTSIZE', (0, -1), (1, -1), 11),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.3 * inch))

        # Predictions if available
        if 'predictions' in forecast_data and forecast_data['predictions']:
            elements.append(Paragraph('Forecast Predictions', self.styles['CustomHeading2']))
            elements.append(Spacer(1, 0.1 * inch))

            predictions = forecast_data['predictions'][:30]  # Limit to 30 rows
            table_data = [['Date', 'Forecasted Cost (USD)']]

            for item in predictions:
                table_data.append([item.get('date', ''), f"${item.get('cost', 0):.2f}"])

            table = Table(table_data, colWidths=[3*inch, 2.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#EEF2FF')]),
            ]))
            elements.append(table)

        # Build PDF
        doc.build(elements, onFirstPage=self._create_header_footer, onLaterPages=self._create_header_footer)
        return buffer.getvalue()

    def generate_rightsizing_report(self, rightsizing_data: Dict[str, Any], profile_name: str) -> bytes:
        """
        Generate PDF report for right-sizing recommendations.

        Args:
            rightsizing_data: Dictionary containing recommendations
            profile_name: AWS profile name

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=self.pagesize, topMargin=1*inch, bottomMargin=1*inch)
        elements = []

        # Title
        elements.append(Paragraph('AWS Right-Sizing Report', self.styles['CustomTitle']))
        elements.append(Spacer(1, 0.2 * inch))

        # Profile and summary
        summary_data = [
            ['Profile:', profile_name],
            ['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Total Recommendations:', str(rightsizing_data.get('total_recommendations', 0))],
            ['Total Monthly Savings:', f"${rightsizing_data.get('total_monthly_savings', 0):,.2f}"]
        ]
        summary_table = Table(summary_data, colWidths=[2.5*inch, 3.5*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (1, -1), colors.HexColor('#D1FAE5')),
            ('FONTSIZE', (0, -1), (1, -1), 11),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.3 * inch))

        # Recommendations if available
        if 'recommendations' in rightsizing_data and rightsizing_data['recommendations']:
            elements.append(Paragraph('Recommendations', self.styles['CustomHeading2']))
            elements.append(Spacer(1, 0.1 * inch))

            recommendations = rightsizing_data['recommendations'][:20]  # Limit to 20
            table_data = [['Resource ID', 'Type', 'Current', 'Recommended', 'Savings/Month']]

            for item in recommendations:
                table_data.append([
                    item.get('resource_id', 'N/A')[:20] + '...' if len(item.get('resource_id', '')) > 20 else item.get('resource_id', 'N/A'),
                    item.get('resource_type', 'N/A')[:15],
                    item.get('current_type', 'N/A')[:15],
                    item.get('recommended_type', 'N/A')[:15],
                    f"${item.get('monthly_savings', 0):.2f}"
                ])

            table = Table(table_data, colWidths=[1.8*inch, 1*inch, 1.2*inch, 1.2*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10B981')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#D1FAE5')]),
            ]))
            elements.append(table)

        # Build PDF
        doc.build(elements, onFirstPage=self._create_header_footer, onLaterPages=self._create_header_footer)
        return buffer.getvalue()
