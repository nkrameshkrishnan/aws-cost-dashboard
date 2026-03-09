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


# ---------------------------------------------------------------------------
# Shared helpers — all export routes funnel through these two functions so
# the S3-or-stream decision is defined exactly once.
# ---------------------------------------------------------------------------

def _resolve_audit_results(
    request: "ExportRequest",
    job_id: Optional[str],
    log_format: str,
) -> FullAuditResults:
    """Return FullAuditResults from request body or job storage, or raise HTTP 4xx."""
    if request.audit_results:
        logger.info(f"Using audit results from request body for {log_format} export")
        return request.audit_results
    if job_id:
        job = job_storage.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Audit job {job_id} not found")
        if job["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Audit job is not completed yet (status: {job['status']})",
            )
        if not job.get("results"):
            raise HTTPException(status_code=404, detail="Audit results not available")
        logger.info(f"Using audit results from job {job_id} for {log_format} export")
        return FullAuditResults.model_validate(job["results"])
    raise HTTPException(
        status_code=400,
        detail="Either audit_results in request body or job_id query parameter must be provided",
    )


def _stream_or_upload(
    file_bytes: bytes,
    media_type: str,
    file_name: str,
    upload_to_s3: bool,
    s3_bucket: Optional[str],
    profile_name: str,
    db: "DBSession",
    s3_message: str = "File exported to S3 successfully",
) -> "Response":
    """
    Return a StreamingResponse (file download) or an ExportResponse (S3 upload).

    Uses the generic S3UploaderService.upload_report uploader.
    For audit-specific uploads use _stream_or_upload_audit instead.
    """
    if upload_to_s3 and s3_bucket:
        aws_session = db_session_manager.get_session(db, profile_name)
        upload_result = S3UploaderService.upload_report(
            file_content=file_bytes,
            bucket_name=s3_bucket,
            file_name=file_name,
            aws_session=aws_session,
            content_type=media_type,
        )
        if not upload_result["success"]:
            raise HTTPException(
                status_code=500, detail=upload_result.get("error", "S3 upload failed")
            )
        return ExportResponse(
            success=True,
            message=s3_message,
            file_name=file_name,
            file_size=len(file_bytes),
            s3_url=upload_result.get("s3_url"),
            s3_bucket=upload_result.get("s3_bucket"),
            s3_key=upload_result.get("s3_key"),
        )
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


def _stream_or_upload_audit(
    file_bytes: bytes,
    media_type: str,
    file_name: str,
    report_format: str,
    account_name: str,
    upload_to_s3: bool,
    s3_bucket: Optional[str],
    db: "DBSession",
    s3_message: str = "Report uploaded to S3 successfully",
) -> "Response":
    """
    Return a StreamingResponse or an ExportResponse for audit-specific S3 uploads.

    Uses S3UploaderService.upload_audit_report (distinct from the generic uploader).
    """
    if upload_to_s3 and s3_bucket:
        aws_session = db_session_manager.get_session(db, account_name)
        upload_result = S3UploaderService.upload_audit_report(
            file_content=file_bytes,
            account_name=account_name,
            report_format=report_format,
            bucket_name=s3_bucket,
            aws_session=aws_session,
        )
        if not upload_result["success"]:
            raise HTTPException(
                status_code=500, detail=upload_result.get("error", "S3 upload failed")
            )
        return ExportResponse(
            success=True,
            message=s3_message,
            file_name=file_name,
            s3_url=upload_result.get("s3_url"),
            s3_bucket=upload_result.get("s3_bucket"),
            s3_key=upload_result.get("s3_key"),
        )
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

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
        from datetime import datetime
        audit_results = _resolve_audit_results(request, job_id, "PDF")
        pdf_bytes = PDFReportGenerator().generate_audit_report(audit_results, include_charts=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = audit_results.account_name.replace(" ", "_").replace("/", "_")
        file_name = f"finops_audit_{safe_name}_{timestamp}.pdf"
        return _stream_or_upload_audit(
            pdf_bytes, "application/pdf", file_name, "pdf",
            audit_results.account_name, request.upload_to_s3, request.s3_bucket, db,
            s3_message="PDF report uploaded to S3 successfully",
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
        from datetime import datetime
        _XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        audit_results = _resolve_audit_results(request, job_id, "Excel")
        excel_bytes = ExcelReportGenerator().generate_audit_report(audit_results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = audit_results.account_name.replace(" ", "_").replace("/", "_")
        file_name = f"finops_audit_{safe_name}_{timestamp}.xlsx"
        return _stream_or_upload_audit(
            excel_bytes, _XLSX, file_name, "xlsx",
            audit_results.account_name, request.upload_to_s3, request.s3_bucket, db,
            s3_message="Excel report uploaded to S3 successfully",
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

        # Reuse the job-resolution helper via a thin shim (no request body for CSV)
        class _NoBodyRequest:
            audit_results = None
        audit_results = _resolve_audit_results(_NoBodyRequest(), job_id, "CSV")

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
        cost_data = {"daily_costs": DatabaseCostProcessor.get_daily_costs(
            db, request.profile_name, request.start_date, request.end_date
        )}
        exporter = CSVJSONExporter()
        if request.export_format.lower() == "json":
            file_bytes = exporter.export_to_json(cost_data)
            media_type = "application/json"
        else:
            file_bytes = exporter.export_daily_costs_csv(cost_data["daily_costs"])
            media_type = "text/csv"
        file_name = exporter.generate_filename("daily_costs", request.profile_name, request.export_format)
        return _stream_or_upload(
            file_bytes, media_type, file_name,
            request.upload_to_s3, request.s3_bucket, request.profile_name, db,
            s3_message="Daily costs exported to S3 successfully",
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
        service_data = {"service_costs": DatabaseCostProcessor.get_service_breakdown(
            db, request.profile_name, request.start_date, request.end_date
        )}
        exporter = CSVJSONExporter()
        if request.export_format.lower() == "json":
            file_bytes = exporter.export_to_json(service_data)
            media_type = "application/json"
        else:
            file_bytes = exporter.export_service_breakdown_csv(service_data["service_costs"])
            media_type = "text/csv"
        file_name = exporter.generate_filename("service_breakdown", request.profile_name, request.export_format)
        return _stream_or_upload(
            file_bytes, media_type, file_name,
            request.upload_to_s3, request.s3_bucket, request.profile_name, db,
            s3_message="Service breakdown exported to S3 successfully",
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
        from app.services.rightsizing_service import RightSizingService
        _XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        rs_data = RightSizingService(db).get_recommendations(
            profile_name=request.profile_name,
            resource_types=request.resource_types.split(",") if request.resource_types else None,
        )
        recommendations = {
            "recommendations": rs_data.recommendations,
            "total_recommendations": rs_data.total_recommendations,
            "total_monthly_savings": rs_data.total_monthly_savings,
        }
        exporter = CSVJSONExporter()
        fmt = request.export_format.lower()
        if fmt == "json":
            file_bytes, media_type, file_ext = exporter.export_to_json(recommendations), "application/json", "json"
        elif fmt == "excel":
            file_bytes, media_type, file_ext = b"", _XLSX, "xlsx"  # placeholder
        else:
            file_bytes, media_type, file_ext = exporter.export_rightsizing_csv(recommendations["recommendations"]), "text/csv", "csv"
        file_name = exporter.generate_filename("rightsizing_recommendations", request.profile_name, file_ext)
        return _stream_or_upload(
            file_bytes, media_type, file_name,
            request.upload_to_s3, request.s3_bucket, request.profile_name, db,
            s3_message="Right-sizing recommendations exported to S3 successfully",
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
        unit_costs = UnitCostService(db).calculate_unit_costs(
            profile_name=request.profile_name,
            start_date=request.start_date,
            end_date=request.end_date,
            region=request.region,
        )
        unit_costs_dict = unit_costs.model_dump() if hasattr(unit_costs, "model_dump") else unit_costs
        exporter = CSVJSONExporter()
        if request.export_format.lower() == "json":
            file_bytes, media_type = exporter.export_to_json(unit_costs_dict), "application/json"
        else:
            file_bytes, media_type = exporter.export_unit_costs_csv(unit_costs_dict), "text/csv"
        file_name = exporter.generate_filename("unit_costs", request.profile_name, request.export_format)
        return _stream_or_upload(
            file_bytes, media_type, file_name,
            request.upload_to_s3, request.s3_bucket, request.profile_name, db,
            s3_message="Unit costs exported to S3 successfully",
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
        forecast_data = DatabaseCostProcessor.get_forecast(db, request.profile_name, days)
        exporter = CSVJSONExporter()
        if request.export_format.lower() == 'json':
            file_bytes, media_type = exporter.export_to_json(forecast_data), "application/json"
        else:
            file_bytes, media_type = exporter.export_forecast_csv(forecast_data.get('predictions', [])), "text/csv"
        file_name = exporter.generate_filename('forecast', request.profile_name, request.export_format)
        return _stream_or_upload(
            file_bytes, media_type, file_name,
            request.upload_to_s3, request.s3_bucket, request.profile_name, db,
            s3_message="Forecast data exported to S3 successfully",
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
        # TODO: Implement actual anomaly detection service integration
        anomalies_data = {'anomalies': [], 'message': 'Anomaly detection feature coming soon'}
        exporter = CSVJSONExporter()
        if request.export_format.lower() == 'json':
            file_bytes, media_type = exporter.export_to_json(anomalies_data), "application/json"
        else:
            file_bytes, media_type = exporter.export_anomalies_csv(anomalies_data.get('anomalies', [])), "text/csv"
        file_name = exporter.generate_filename('anomalies', request.profile_name, request.export_format)
        return _stream_or_upload(
            file_bytes, media_type, file_name,
            request.upload_to_s3, request.s3_bucket, request.profile_name, db,
            s3_message="Anomaly data exported to S3 successfully",
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
        cost_data = {
            'daily_costs': DatabaseCostProcessor.get_daily_costs(
                db, request.profile_name, request.start_date, request.end_date
            ),
            'service_breakdown': DatabaseCostProcessor.get_service_breakdown(
                db, request.profile_name, request.start_date, request.end_date
            ),
        }
        pdf_bytes = PDFReportGenerator().generate_cost_report(cost_data, request.profile_name)
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile = request.profile_name.replace(' ', '_').replace('/', '_')
        file_name = f"cost_report_{safe_profile}_{timestamp}.pdf"
        return _stream_or_upload(
            pdf_bytes, 'application/pdf', file_name,
            request.upload_to_s3, request.s3_bucket, request.profile_name, db,
            s3_message="Cost report uploaded to S3 successfully",
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
        cost_data = {
            'daily_costs': DatabaseCostProcessor.get_daily_costs(
                db, request.profile_name, request.start_date, request.end_date
            ),
            'service_breakdown': DatabaseCostProcessor.get_service_breakdown(
                db, request.profile_name, request.start_date, request.end_date
            ),
        }
        excel_bytes = ExcelReportGenerator().generate_cost_report(cost_data, request.profile_name)
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile = request.profile_name.replace(' ', '_').replace('/', '_')
        file_name = f"cost_report_{safe_profile}_{timestamp}.xlsx"
        xlsx_mt = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return _stream_or_upload(
            excel_bytes, xlsx_mt, file_name,
            request.upload_to_s3, request.s3_bucket, request.profile_name, db,
            s3_message="Cost report uploaded to S3 successfully",
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
        forecast_data = DatabaseCostProcessor.get_forecast(db, request.profile_name, days)
        pdf_bytes = PDFReportGenerator().generate_forecast_report(forecast_data, request.profile_name)
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile = request.profile_name.replace(' ', '_').replace('/', '_')
        file_name = f"forecast_report_{safe_profile}_{timestamp}.pdf"
        return _stream_or_upload(
            pdf_bytes, 'application/pdf', file_name,
            request.upload_to_s3, request.s3_bucket, request.profile_name, db,
            s3_message="Forecast report uploaded to S3 successfully",
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
        forecast_data = DatabaseCostProcessor.get_forecast(db, request.profile_name, days)
        excel_bytes = ExcelReportGenerator().generate_forecast_report(forecast_data, request.profile_name)
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile = request.profile_name.replace(' ', '_').replace('/', '_')
        file_name = f"forecast_report_{safe_profile}_{timestamp}.xlsx"
        xlsx_mt = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return _stream_or_upload(
            excel_bytes, xlsx_mt, file_name,
            request.upload_to_s3, request.s3_bucket, request.profile_name, db,
            s3_message="Forecast report uploaded to S3 successfully",
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
        rs_response = RightSizingService(db).get_recommendations(request.profile_name, request.resource_types)
        rightsizing_data = rs_response.model_dump() if hasattr(rs_response, 'model_dump') else rs_response.dict()
        pdf_bytes = PDFReportGenerator().generate_rightsizing_report(rightsizing_data, request.profile_name)
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile = request.profile_name.replace(' ', '_').replace('/', '_')
        file_name = f"rightsizing_report_{safe_profile}_{timestamp}.pdf"
        return _stream_or_upload(
            pdf_bytes, 'application/pdf', file_name,
            request.upload_to_s3, request.s3_bucket, request.profile_name, db,
            s3_message="Right-sizing report uploaded to S3 successfully",
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
        rs_response = RightSizingService(db).get_recommendations(request.profile_name, request.resource_types)
        rightsizing_data = rs_response.model_dump() if hasattr(rs_response, 'model_dump') else rs_response.dict()
        excel_bytes = ExcelReportGenerator().generate_rightsizing_report(rightsizing_data, request.profile_name)
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile = request.profile_name.replace(' ', '_').replace('/', '_')
        file_name = f"rightsizing_report_{safe_profile}_{timestamp}.xlsx"
        xlsx_mt = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return _stream_or_upload(
            excel_bytes, xlsx_mt, file_name,
            request.upload_to_s3, request.s3_bucket, request.profile_name, db,
            s3_message="Right-sizing report uploaded to S3 successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting right-sizing Excel: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
