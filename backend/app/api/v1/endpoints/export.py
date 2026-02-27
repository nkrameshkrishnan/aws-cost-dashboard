"""
Export and report generation API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession
from typing import Optional
from pydantic import BaseModel
import logging
import io

from app.database.base import get_db
from app.schemas.audit import FullAuditResults
from app.schemas.export import (
    CostExportRequest,
    BudgetExportRequest,
    AnalyticsExportRequest,
    RightSizingExportRequest,
    UnitCostExportRequest,
    ExportResponse
)
from app.core.job_storage import job_storage
from app.export.pdf_generator import PDFReportGenerator
from app.export.excel_exporter import ExcelReportGenerator
from app.export.csv_json_exporter import CSVJSONExporter
from app.export.s3_uploader import S3UploaderService
from app.aws.session_manager_db import db_session_manager
from app.services.cost_processor_db import DatabaseCostProcessor
from app.services.budget_service import BudgetService
from app.services.unit_cost_service import UnitCostService
from app.services.forecast_service import ForecastService

router = APIRouter()
logger = logging.getLogger(__name__)


class ExportRequest(BaseModel):
    """Request body for exporting audit results."""
    audit_results: Optional[FullAuditResults] = None
    upload_to_s3: bool = False
    s3_bucket: Optional[str] = None


class ExportResponse(BaseModel):
    """Response for export operations."""
    success: bool
    message: str
    file_name: Optional[str] = None
    s3_url: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_key: Optional[str] = None


@router.post("/audit/pdf", response_class=StreamingResponse)
async def export_audit_pdf(
    request: ExportRequest,
    job_id: Optional[str] = Query(None, description="Audit job ID (optional if audit_results provided)"),
    db: DBSession = Depends(get_db)
):
    """
    Generate PDF audit report.

    Args:
        request: Export request with optional audit results
        job_id: Optional audit job ID
        db: Database session

    Returns:
        PDF file download or S3 upload confirmation
    """
    try:
        # Get audit results from request body or job lookup
        if request.audit_results:
            audit_results = request.audit_results
            logger.info(f"Using audit results from request body for PDF export")
        elif job_id:
            job = job_storage.get_job(job_id)
            if not job:
                raise HTTPException(status_code=404, detail=f"Audit job {job_id} not found")
            if job['status'] != 'completed':
                raise HTTPException(status_code=400, detail=f"Audit job is not completed yet (status: {job['status']})")
            if not job.get('results'):
                raise HTTPException(status_code=404, detail="Audit results not available")
            audit_results = FullAuditResults.model_validate(job['results'])
            logger.info(f"Using audit results from job {job_id} for PDF export")
        else:
            raise HTTPException(
                status_code=400,
                detail="Either audit_results in request body or job_id query parameter must be provided"
            )

        # Generate PDF
        pdf_generator = PDFReportGenerator()
        pdf_bytes = pdf_generator.generate_audit_report(audit_results, include_charts=True)

        # Generate file name
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_account_name = audit_results.account_name.replace(' ', '_').replace('/', '_')
        file_name = f"finops_audit_{safe_account_name}_{timestamp}.pdf"

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            # Get AWS session for the account
            aws_session = db_session_manager.get_session(db, audit_results.account_name)

            # Upload to S3
            upload_result = S3UploaderService.upload_audit_report(
                file_content=pdf_bytes,
                account_name=audit_results.account_name,
                report_format='pdf',
                bucket_name=request.s3_bucket,
                aws_session=aws_session
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message="PDF report uploaded to S3 successfully",
                file_name=file_name,
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return PDF as download
        pdf_stream = io.BytesIO(pdf_bytes)
        return StreamingResponse(
            pdf_stream,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating PDF export: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.post("/audit/excel", response_class=StreamingResponse)
async def export_audit_excel(
    request: ExportRequest,
    job_id: Optional[str] = Query(None, description="Audit job ID (optional if audit_results provided)"),
    db: DBSession = Depends(get_db)
):
    """
    Generate Excel audit report with multiple sheets.

    Args:
        request: Export request with optional audit results
        job_id: Optional audit job ID
        db: Database session

    Returns:
        Excel file download or S3 upload confirmation
    """
    try:
        # Get audit results from request body or job lookup
        if request.audit_results:
            audit_results = request.audit_results
            logger.info(f"Using audit results from request body for Excel export")
        elif job_id:
            job = job_storage.get_job(job_id)
            if not job:
                raise HTTPException(status_code=404, detail=f"Audit job {job_id} not found")
            if job['status'] != 'completed':
                raise HTTPException(status_code=400, detail=f"Audit job is not completed yet (status: {job['status']})")
            if not job.get('results'):
                raise HTTPException(status_code=404, detail="Audit results not available")
            audit_results = FullAuditResults.model_validate(job['results'])
            logger.info(f"Using audit results from job {job_id} for Excel export")
        else:
            raise HTTPException(
                status_code=400,
                detail="Either audit_results in request body or job_id query parameter must be provided"
            )

        # Generate Excel
        excel_generator = ExcelReportGenerator()
        excel_bytes = excel_generator.generate_audit_report(audit_results)

        # Generate file name
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_account_name = audit_results.account_name.replace(' ', '_').replace('/', '_')
        file_name = f"finops_audit_{safe_account_name}_{timestamp}.xlsx"

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            # Get AWS session for the account
            aws_session = db_session_manager.get_session(db, audit_results.account_name)

            # Upload to S3
            upload_result = S3UploaderService.upload_audit_report(
                file_content=excel_bytes,
                account_name=audit_results.account_name,
                report_format='xlsx',
                bucket_name=request.s3_bucket,
                aws_session=aws_session
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message="Excel report uploaded to S3 successfully",
                file_name=file_name,
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return Excel as download
        excel_stream = io.BytesIO(excel_bytes)
        return StreamingResponse(
            excel_stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating Excel export: {e}")
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {str(e)}")


@router.post("/audit/csv", response_class=StreamingResponse)
async def export_audit_csv(
    job_id: Optional[str] = Query(None, description="Audit job ID"),
    audit_type: str = Query(..., description="Type of audit data to export (ec2, ebs, rds, lambda, etc.)"),
    db: DBSession = Depends(get_db)
):
    """
    Generate CSV export for a specific audit type.

    Args:
        job_id: Audit job ID
        audit_type: Type of audit data to export
        db: Database session

    Returns:
        CSV file download
    """
    try:
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id is required for CSV export")

        job = job_storage.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Audit job {job_id} not found")
        if job['status'] != 'completed':
            raise HTTPException(status_code=400, detail=f"Audit job is not completed yet (status: {job['status']})")
        if not job.get('results'):
            raise HTTPException(status_code=404, detail="Audit results not available")

        audit_results = FullAuditResults.model_validate(job['results'])

        import csv

        # Generate CSV based on audit type
        output = io.StringIO()
        writer = csv.writer(output)

        if audit_type == 'ec2' and audit_results.ec2_audit:
            writer.writerow(['Instance ID', 'Instance Type', 'Region', 'Avg CPU %', 'Est. Monthly Cost', 'Potential Savings'])
            for instance in audit_results.ec2_audit.idle_instances:
                writer.writerow([
                    instance.instance_id,
                    instance.instance_type,
                    instance.region,
                    f"{instance.avg_cpu_utilization:.2f}",
                    f"{instance.estimated_monthly_cost:.2f}",
                    f"{instance.potential_monthly_savings:.2f}"
                ])
        elif audit_type == 'ebs' and audit_results.ebs_audit:
            writer.writerow(['Volume ID', 'Size (GB)', 'Volume Type', 'Region', 'Days Unattached', 'Est. Monthly Cost'])
            for volume in audit_results.ebs_audit.unattached_volumes:
                writer.writerow([
                    volume.volume_id,
                    volume.size_gb,
                    volume.volume_type,
                    volume.region,
                    volume.days_unattached,
                    f"{volume.estimated_monthly_cost:.2f}"
                ])
        elif audit_type == 'rds' and audit_results.rds_audit:
            writer.writerow(['Instance ID', 'Instance Class', 'Engine', 'Region', 'Avg CPU %', 'Avg Connections', 'Est. Monthly Cost'])
            for instance in audit_results.rds_audit.idle_instances:
                writer.writerow([
                    instance.db_instance_id,
                    instance.db_instance_class,
                    instance.engine,
                    instance.region,
                    f"{instance.avg_cpu_utilization:.2f}",
                    f"{instance.avg_connections:.0f}",
                    f"{instance.estimated_monthly_cost:.2f}"
                ])
        else:
            raise HTTPException(status_code=400, detail=f"Invalid or unsupported audit type: {audit_type}")

        # Generate file name
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_account_name = audit_results.account_name.replace(' ', '_').replace('/', '_')
        file_name = f"finops_{audit_type}_{safe_account_name}_{timestamp}.csv"

        # Return CSV as download
        csv_stream = io.BytesIO(output.getvalue().encode('utf-8'))
        return StreamingResponse(
            csv_stream,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating CSV export: {e}")
        raise HTTPException(status_code=500, detail=f"CSV generation failed: {str(e)}")


# ==================== Cost Data Export Endpoints ====================

@router.post("/costs/daily", response_class=StreamingResponse)
async def export_daily_costs(
    request: CostExportRequest,
    db: DBSession = Depends(get_db)
):
    """
    Export daily cost data to CSV or JSON.

    Args:
        request: Cost export request
        db: Database session

    Returns:
        CSV or JSON file download
    """
    try:
        # Get daily costs data
        daily_costs = DatabaseCostProcessor.get_daily_costs(
            db,
            request.profile_name,
            request.start_date,
            request.end_date
        )
        cost_data = {'daily_costs': daily_costs}

        exporter = CSVJSONExporter()

        # Generate file based on format
        if request.export_format.lower() == 'json':
            file_bytes = exporter.export_to_json(cost_data)
            media_type = "application/json"
        else:  # CSV
            file_bytes = exporter.export_daily_costs_csv(cost_data.get('daily_costs', []))
            media_type = "text/csv"

        # Generate filename
        file_name = exporter.generate_filename(
            'daily_costs',
            request.profile_name,
            request.export_format
        )

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            aws_session = db_session_manager.get_session(db, request.profile_name)
            upload_result = S3UploaderService.upload_report(
                file_content=file_bytes,
                bucket_name=request.s3_bucket,
                file_name=file_name,
                aws_session=aws_session,
                content_type=media_type
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message=f"Daily costs exported to S3 successfully",
                file_name=file_name,
                file_size=len(file_bytes),
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return file as download
        file_stream = io.BytesIO(file_bytes)
        return StreamingResponse(
            file_stream,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting daily costs: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/costs/by-service", response_class=StreamingResponse)
async def export_service_breakdown(
    request: CostExportRequest,
    db: DBSession = Depends(get_db)
):
    """
    Export service breakdown costs to CSV or JSON.

    Args:
        request: Cost export request
        db: Database session

    Returns:
        CSV or JSON file download
    """
    try:
        # Get service breakdown data
        service_costs = DatabaseCostProcessor.get_service_breakdown(
            db,
            request.profile_name,
            request.start_date,
            request.end_date
        )
        service_data = {'service_costs': service_costs}

        exporter = CSVJSONExporter()

        # Generate file based on format
        if request.export_format.lower() == 'json':
            file_bytes = exporter.export_to_json(service_data)
            media_type = "application/json"
        else:  # CSV
            file_bytes = exporter.export_service_breakdown_csv(service_data.get('service_costs', []))
            media_type = "text/csv"

        # Generate filename
        file_name = exporter.generate_filename(
            'service_breakdown',
            request.profile_name,
            request.export_format
        )

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            aws_session = db_session_manager.get_session(db, request.profile_name)
            upload_result = S3UploaderService.upload_report(
                file_content=file_bytes,
                bucket_name=request.s3_bucket,
                file_name=file_name,
                aws_session=aws_session,
                content_type=media_type
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message=f"Service breakdown exported to S3 successfully",
                file_name=file_name,
                file_size=len(file_bytes),
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return file as download
        file_stream = io.BytesIO(file_bytes)
        return StreamingResponse(
            file_stream,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting service breakdown: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ==================== Right-Sizing Export Endpoints ====================

@router.post("/rightsizing", response_class=StreamingResponse)
async def export_rightsizing_recommendations(
    request: RightSizingExportRequest,
    db: DBSession = Depends(get_db)
):
    """
    Export right-sizing recommendations to CSV, JSON, or Excel.

    Args:
        request: Right-sizing export request
        db: Database session

    Returns:
        File download (CSV, JSON, or Excel)
    """
    try:
        # Get right-sizing recommendations using the service
        from app.services.rightsizing_service import RightSizingService

        rs_service = RightSizingService(db)
        recommendations_data = rs_service.get_recommendations(
            profile_name=request.profile_name,
            resource_types=request.resource_types.split(',') if request.resource_types else None
        )
        recommendations = {
            'recommendations': recommendations_data.recommendations,
            'total_recommendations': recommendations_data.total_recommendations,
            'total_monthly_savings': recommendations_data.total_monthly_savings
        }

        exporter = CSVJSONExporter()

        # Generate file based on format
        if request.export_format.lower() == 'json':
            file_bytes = exporter.export_to_json(recommendations)
            media_type = "application/json"
            file_ext = 'json'
        elif request.export_format.lower() == 'excel':
            # Use Excel exporter for right-sizing (we'll need to create this method)
            file_bytes = b''  # Placeholder - would need Excel implementation
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            file_ext = 'xlsx'
        else:  # CSV
            file_bytes = exporter.export_rightsizing_csv(recommendations.get('recommendations', []))
            media_type = "text/csv"
            file_ext = 'csv'

        # Generate filename
        file_name = exporter.generate_filename(
            'rightsizing_recommendations',
            request.profile_name,
            file_ext
        )

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            aws_session = db_session_manager.get_session(db, request.profile_name)
            upload_result = S3UploaderService.upload_report(
                file_content=file_bytes,
                bucket_name=request.s3_bucket,
                file_name=file_name,
                aws_session=aws_session,
                content_type=media_type
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message=f"Right-sizing recommendations exported to S3 successfully",
                file_name=file_name,
                file_size=len(file_bytes),
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return file as download
        file_stream = io.BytesIO(file_bytes)
        return StreamingResponse(
            file_stream,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting right-sizing recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ==================== Unit Cost Export Endpoints ====================

@router.post("/unit-costs", response_class=StreamingResponse)
async def export_unit_costs(
    request: UnitCostExportRequest,
    db: DBSession = Depends(get_db)
):
    """
    Export unit cost metrics to CSV or JSON.

    Args:
        request: Unit cost export request
        db: Database session

    Returns:
        CSV or JSON file download
    """
    try:
        # Get unit cost data
        unit_cost_service = UnitCostService(db)
        unit_costs = unit_cost_service.calculate_unit_costs(
            profile_name=request.profile_name,
            start_date=request.start_date,
            end_date=request.end_date,
            region=request.region
        )

        exporter = CSVJSONExporter()

        # Convert Pydantic model to dict
        unit_costs_dict = unit_costs.model_dump() if hasattr(unit_costs, 'model_dump') else unit_costs

        # Generate file based on format
        if request.export_format.lower() == 'json':
            file_bytes = exporter.export_to_json(unit_costs_dict)
            media_type = "application/json"
        else:  # CSV
            file_bytes = exporter.export_unit_costs_csv(unit_costs_dict)
            media_type = "text/csv"

        # Generate filename
        file_name = exporter.generate_filename(
            'unit_costs',
            request.profile_name,
            request.export_format
        )

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            aws_session = db_session_manager.get_session(db, request.profile_name)
            upload_result = S3UploaderService.upload_report(
                file_content=file_bytes,
                bucket_name=request.s3_bucket,
                file_name=file_name,
                aws_session=aws_session,
                content_type=media_type
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message=f"Unit costs exported to S3 successfully",
                file_name=file_name,
                file_size=len(file_bytes),
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return file as download
        file_stream = io.BytesIO(file_bytes)
        return StreamingResponse(
            file_stream,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting unit costs: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ==================== Analytics Export Endpoints ====================

@router.post("/analytics/forecast", response_class=StreamingResponse)
async def export_forecast_data(
    request: AnalyticsExportRequest,
    days: int = Query(30, description="Number of days to forecast"),
    db: DBSession = Depends(get_db)
):
    """
    Export forecast data to CSV or JSON.

    Args:
        request: Analytics export request
        days: Number of days to forecast
        db: Database session

    Returns:
        CSV or JSON file download
    """
    try:
        # Get forecast data
        forecast_data = DatabaseCostProcessor.get_forecast(
            db,
            request.profile_name,
            days
        )

        exporter = CSVJSONExporter()

        # Generate file based on format
        if request.export_format.lower() == 'json':
            file_bytes = exporter.export_to_json(forecast_data)
            media_type = "application/json"
        else:  # CSV
            file_bytes = exporter.export_forecast_csv(forecast_data.get('predictions', []))
            media_type = "text/csv"

        # Generate filename
        file_name = exporter.generate_filename(
            'forecast',
            request.profile_name,
            request.export_format
        )

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            aws_session = db_session_manager.get_session(db, request.profile_name)
            upload_result = S3UploaderService.upload_report(
                file_content=file_bytes,
                bucket_name=request.s3_bucket,
                file_name=file_name,
                aws_session=aws_session,
                content_type=media_type
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message=f"Forecast data exported to S3 successfully",
                file_name=file_name,
                file_size=len(file_bytes),
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return file as download
        file_stream = io.BytesIO(file_bytes)
        return StreamingResponse(
            file_stream,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting forecast data: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/analytics/anomalies", response_class=StreamingResponse)
async def export_anomalies(
    request: AnalyticsExportRequest,
    db: DBSession = Depends(get_db)
):
    """
    Export anomaly detection results to CSV or JSON.

    Args:
        request: Analytics export request
        db: Database session

    Returns:
        CSV or JSON file download
    """
    try:
        # Get anomaly data (this would typically come from a previous anomaly detection run)
        # For now, we'll assume the data is passed or retrieved from a job
        # Placeholder - in real implementation, fetch from analytics service or job storage
        # TODO: Implement actual anomaly detection service integration
        anomalies_data = {
            'anomalies': [],
            'message': 'Anomaly detection feature coming soon'
        }

        exporter = CSVJSONExporter()

        # Generate file based on format
        if request.export_format.lower() == 'json':
            file_bytes = exporter.export_to_json(anomalies_data)
            media_type = "application/json"
        else:  # CSV
            file_bytes = exporter.export_anomalies_csv(anomalies_data.get('anomalies', []))
            media_type = "text/csv"

        # Generate filename
        file_name = exporter.generate_filename(
            'anomalies',
            request.profile_name,
            request.export_format
        )

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            aws_session = db_session_manager.get_session(db, request.profile_name)
            upload_result = S3UploaderService.upload_report(
                file_content=file_bytes,
                bucket_name=request.s3_bucket,
                file_name=file_name,
                aws_session=aws_session,
                content_type=media_type
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message=f"Anomaly data exported to S3 successfully",
                file_name=file_name,
                file_size=len(file_bytes),
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return file as download
        file_stream = io.BytesIO(file_bytes)
        return StreamingResponse(
            file_stream,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting anomaly data: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ==================== Cost PDF/Excel Exports ====================

@router.post("/costs/pdf", response_class=StreamingResponse)
async def export_costs_pdf(
    request: CostExportRequest,
    db: DBSession = Depends(get_db)
):
    """
    Generate PDF report for cost data.

    Args:
        request: Cost export request
        db: Database session

    Returns:
        PDF file download or S3 upload confirmation
    """
    try:
        # Get cost data
        daily_costs = DatabaseCostProcessor.get_daily_costs(
            db, request.profile_name, request.start_date, request.end_date
        )
        service_breakdown = DatabaseCostProcessor.get_service_breakdown(
            db, request.profile_name, request.start_date, request.end_date
        )

        cost_data = {
            'daily_costs': daily_costs,
            'service_breakdown': service_breakdown
        }

        # Generate PDF
        pdf_generator = PDFReportGenerator()
        pdf_bytes = pdf_generator.generate_cost_report(cost_data, request.profile_name)

        # Generate file name
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile_name = request.profile_name.replace(' ', '_').replace('/', '_')
        file_name = f"cost_report_{safe_profile_name}_{timestamp}.pdf"

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            aws_session = db_session_manager.get_session(db, request.profile_name)
            upload_result = S3UploaderService.upload_report(
                file_content=pdf_bytes,
                bucket_name=request.s3_bucket,
                file_name=file_name,
                aws_session=aws_session,
                content_type='application/pdf'
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message=f"Cost report uploaded to S3 successfully",
                file_name=file_name,
                file_size=len(pdf_bytes),
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return file as download
        file_stream = io.BytesIO(pdf_bytes)
        return StreamingResponse(
            file_stream,
            media_type='application/pdf',
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting cost PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/costs/excel", response_class=StreamingResponse)
async def export_costs_excel(
    request: CostExportRequest,
    db: DBSession = Depends(get_db)
):
    """
    Generate Excel report for cost data.

    Args:
        request: Cost export request
        db: Database session

    Returns:
        Excel file download or S3 upload confirmation
    """
    try:
        # Get cost data
        daily_costs = DatabaseCostProcessor.get_daily_costs(
            db, request.profile_name, request.start_date, request.end_date
        )
        service_breakdown = DatabaseCostProcessor.get_service_breakdown(
            db, request.profile_name, request.start_date, request.end_date
        )

        cost_data = {
            'daily_costs': daily_costs,
            'service_breakdown': service_breakdown
        }

        # Generate Excel
        excel_generator = ExcelReportGenerator()
        excel_bytes = excel_generator.generate_cost_report(cost_data, request.profile_name)

        # Generate file name
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile_name = request.profile_name.replace(' ', '_').replace('/', '_')
        file_name = f"cost_report_{safe_profile_name}_{timestamp}.xlsx"

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            aws_session = db_session_manager.get_session(db, request.profile_name)
            upload_result = S3UploaderService.upload_report(
                file_content=excel_bytes,
                bucket_name=request.s3_bucket,
                file_name=file_name,
                aws_session=aws_session,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message=f"Cost report uploaded to S3 successfully",
                file_name=file_name,
                file_size=len(excel_bytes),
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return file as download
        file_stream = io.BytesIO(excel_bytes)
        return StreamingResponse(
            file_stream,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting cost Excel: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ==================== Forecast PDF/Excel Exports ====================

@router.post("/forecast/pdf", response_class=StreamingResponse)
async def export_forecast_pdf(
    request: AnalyticsExportRequest,
    days: int = Query(30, description="Number of days to forecast"),
    db: DBSession = Depends(get_db)
):
    """
    Generate PDF report for forecast data.

    Args:
        request: Analytics export request
        days: Number of days to forecast
        db: Database session

    Returns:
        PDF file download or S3 upload confirmation
    """
    try:
        # Get forecast data
        forecast_data = DatabaseCostProcessor.get_forecast(db, request.profile_name, days)

        # Generate PDF
        pdf_generator = PDFReportGenerator()
        pdf_bytes = pdf_generator.generate_forecast_report(forecast_data, request.profile_name)

        # Generate file name
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile_name = request.profile_name.replace(' ', '_').replace('/', '_')
        file_name = f"forecast_report_{safe_profile_name}_{timestamp}.pdf"

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            aws_session = db_session_manager.get_session(db, request.profile_name)
            upload_result = S3UploaderService.upload_report(
                file_content=pdf_bytes,
                bucket_name=request.s3_bucket,
                file_name=file_name,
                aws_session=aws_session,
                content_type='application/pdf'
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message=f"Forecast report uploaded to S3 successfully",
                file_name=file_name,
                file_size=len(pdf_bytes),
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return file as download
        file_stream = io.BytesIO(pdf_bytes)
        return StreamingResponse(
            file_stream,
            media_type='application/pdf',
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting forecast PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/forecast/excel", response_class=StreamingResponse)
async def export_forecast_excel(
    request: AnalyticsExportRequest,
    days: int = Query(30, description="Number of days to forecast"),
    db: DBSession = Depends(get_db)
):
    """
    Generate Excel report for forecast data.

    Args:
        request: Analytics export request
        days: Number of days to forecast
        db: Database session

    Returns:
        Excel file download or S3 upload confirmation
    """
    try:
        # Get forecast data
        forecast_data = DatabaseCostProcessor.get_forecast(db, request.profile_name, days)

        # Generate Excel
        excel_generator = ExcelReportGenerator()
        excel_bytes = excel_generator.generate_forecast_report(forecast_data, request.profile_name)

        # Generate file name
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile_name = request.profile_name.replace(' ', '_').replace('/', '_')
        file_name = f"forecast_report_{safe_profile_name}_{timestamp}.xlsx"

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            aws_session = db_session_manager.get_session(db, request.profile_name)
            upload_result = S3UploaderService.upload_report(
                file_content=excel_bytes,
                bucket_name=request.s3_bucket,
                file_name=file_name,
                aws_session=aws_session,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message=f"Forecast report uploaded to S3 successfully",
                file_name=file_name,
                file_size=len(excel_bytes),
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return file as download
        file_stream = io.BytesIO(excel_bytes)
        return StreamingResponse(
            file_stream,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting forecast Excel: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ==================== Right-Sizing PDF/Excel Exports ====================

@router.post("/rightsizing/pdf", response_class=StreamingResponse)
async def export_rightsizing_pdf(
    request: RightSizingExportRequest,
    db: DBSession = Depends(get_db)
):
    """
    Generate PDF report for right-sizing recommendations.

    Args:
        request: Right-sizing export request
        db: Database session

    Returns:
        PDF file download or S3 upload confirmation
    """
    try:
        from app.services.rightsizing_service import RightSizingService

        # Get right-sizing data
        rs_service = RightSizingService(db)
        rightsizing_response = rs_service.get_recommendations(
            request.profile_name,
            request.resource_types
        )

        # Convert Pydantic model to dict
        rightsizing_data = rightsizing_response.model_dump() if hasattr(rightsizing_response, 'model_dump') else rightsizing_response.dict()

        # Generate PDF
        pdf_generator = PDFReportGenerator()
        pdf_bytes = pdf_generator.generate_rightsizing_report(rightsizing_data, request.profile_name)

        # Generate file name
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile_name = request.profile_name.replace(' ', '_').replace('/', '_')
        file_name = f"rightsizing_report_{safe_profile_name}_{timestamp}.pdf"

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            aws_session = db_session_manager.get_session(db, request.profile_name)
            upload_result = S3UploaderService.upload_report(
                file_content=pdf_bytes,
                bucket_name=request.s3_bucket,
                file_name=file_name,
                aws_session=aws_session,
                content_type='application/pdf'
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message=f"Right-sizing report uploaded to S3 successfully",
                file_name=file_name,
                file_size=len(pdf_bytes),
                s3_url=upload_result.get('s3_url'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return file as download
        file_stream = io.BytesIO(pdf_bytes)
        return StreamingResponse(
            file_stream,
            media_type='application/pdf',
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting right-sizing PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/rightsizing/excel", response_class=StreamingResponse)
async def export_rightsizing_excel(
    request: RightSizingExportRequest,
    db: DBSession = Depends(get_db)
):
    """
    Generate Excel report for right-sizing recommendations.

    Args:
        request: Right-sizing export request
        db: Database session

    Returns:
        Excel file download or S3 upload confirmation
    """
    try:
        from app.services.rightsizing_service import RightSizingService

        # Get right-sizing data
        rs_service = RightSizingService(db)
        rightsizing_response = rs_service.get_recommendations(
            request.profile_name,
            request.resource_types
        )

        # Convert Pydantic model to dict
        rightsizing_data = rightsizing_response.model_dump() if hasattr(rightsizing_response, 'model_dump') else rightsizing_response.dict()

        # Generate Excel
        excel_generator = ExcelReportGenerator()
        excel_bytes = excel_generator.generate_rightsizing_report(rightsizing_data, request.profile_name)

        # Generate file name
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile_name = request.profile_name.replace(' ', '_').replace('/', '_')
        file_name = f"rightsizing_report_{safe_profile_name}_{timestamp}.xlsx"

        # Upload to S3 if requested
        if request.upload_to_s3 and request.s3_bucket:
            aws_session = db_session_manager.get_session(db, request.profile_name)
            upload_result = S3UploaderService.upload_report(
                file_content=excel_bytes,
                bucket_name=request.s3_bucket,
                file_name=file_name,
                aws_session=aws_session,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

            if not upload_result['success']:
                raise HTTPException(status_code=500, detail=upload_result.get('error', 'S3 upload failed'))

            return ExportResponse(
                success=True,
                message=f"Right-sizing report uploaded to S3 successfully",
                file_name=file_name,
                file_size=len(excel_bytes),
                s3_url=upload_result.get('s3_bucket'),
                s3_bucket=upload_result.get('s3_bucket'),
                s3_key=upload_result.get('s3_key')
            )

        # Return file as download
        file_stream = io.BytesIO(excel_bytes)
        return StreamingResponse(
            file_stream,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting right-sizing Excel: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
