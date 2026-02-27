"""
Schemas for export and reporting functionality.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date


class CostExportRequest(BaseModel):
    """Request for exporting cost data."""
    profile_name: str = Field(..., description="AWS profile name")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    export_format: str = Field("csv", description="Export format: csv or json")
    upload_to_s3: bool = Field(False, description="Upload to S3 after generation")
    s3_bucket: Optional[str] = Field(None, description="S3 bucket name for upload")


class BudgetExportRequest(BaseModel):
    """Request for exporting budget data."""
    profile_name: str = Field(..., description="AWS profile name")
    export_format: str = Field("csv", description="Export format: csv or json")
    upload_to_s3: bool = Field(False, description="Upload to S3 after generation")
    s3_bucket: Optional[str] = Field(None, description="S3 bucket name for upload")


class AnalyticsExportRequest(BaseModel):
    """Request for exporting analytics data."""
    profile_name: str = Field(..., description="AWS profile name")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    data_type: str = Field("forecast", description="Data type: forecast or anomalies")
    export_format: str = Field("csv", description="Export format: csv or json")
    upload_to_s3: bool = Field(False, description="Upload to S3 after generation")
    s3_bucket: Optional[str] = Field(None, description="S3 bucket name for upload")


class RightSizingExportRequest(BaseModel):
    """Request for exporting right-sizing recommendations."""
    profile_name: str = Field(..., description="AWS profile name")
    resource_types: Optional[str] = Field(None, description="Comma-separated resource types")
    export_format: str = Field("csv", description="Export format: csv, json, or excel")
    upload_to_s3: bool = Field(False, description="Upload to S3 after generation")
    s3_bucket: Optional[str] = Field(None, description="S3 bucket name for upload")


class UnitCostExportRequest(BaseModel):
    """Request for exporting unit cost metrics."""
    profile_name: str = Field(..., description="AWS profile name")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    region: str = Field("us-east-2", description="AWS region")
    export_format: str = Field("csv", description="Export format: csv or json")
    upload_to_s3: bool = Field(False, description="Upload to S3 after generation")
    s3_bucket: Optional[str] = Field(None, description="S3 bucket name for upload")


class ExportResponse(BaseModel):
    """Response for export operations."""
    success: bool = Field(..., description="Whether the export succeeded")
    message: str = Field(..., description="Status message")
    file_name: Optional[str] = Field(None, description="Name of the generated file")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    s3_url: Optional[str] = Field(None, description="S3 URL if uploaded")
    s3_bucket: Optional[str] = Field(None, description="S3 bucket name if uploaded")
    s3_key: Optional[str] = Field(None, description="S3 object key if uploaded")


class PDFReportRequest(BaseModel):
    """Request for generating PDF reports."""
    profile_name: str = Field(..., description="AWS profile name")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    report_type: str = Field("comprehensive", description="Report type: comprehensive, cost_only, or summary")
    include_charts: bool = Field(True, description="Include charts in the report")
    upload_to_s3: bool = Field(False, description="Upload to S3 after generation")
    s3_bucket: Optional[str] = Field(None, description="S3 bucket name for upload")
