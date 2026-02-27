"""
CSV and JSON exporters for cost data, budgets, analytics, and right-sizing recommendations.
"""
import csv
import json
import io
from typing import List, Dict, Any, Optional
from datetime import datetime


class CSVJSONExporter:
    """Generate CSV and JSON exports for various dashboard data."""

    @staticmethod
    def export_daily_costs_csv(daily_costs: List[Dict[str, Any]]) -> bytes:
        """
        Export daily costs to CSV format.

        Args:
            daily_costs: List of daily cost records

        Returns:
            CSV file as bytes
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(['Date', 'Cost (USD)', 'Service Count'])

        # Data
        for record in daily_costs:
            writer.writerow([
                record.get('date', ''),
                f"{record.get('cost', 0):.2f}",
                record.get('service_count', 0)
            ])

        csv_bytes = output.getvalue().encode('utf-8')
        output.close()
        return csv_bytes

    @staticmethod
    def export_service_breakdown_csv(service_costs: List[Dict[str, Any]]) -> bytes:
        """
        Export service breakdown costs to CSV format.

        Args:
            service_costs: List of service cost records

        Returns:
            CSV file as bytes
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(['Service', 'Cost (USD)', 'Percentage'])

        # Data
        total_cost = sum(record.get('cost', 0) for record in service_costs)
        for record in service_costs:
            cost = record.get('cost', 0)
            percentage = (cost / total_cost * 100) if total_cost > 0 else 0
            writer.writerow([
                record.get('service', ''),
                f"{cost:.2f}",
                f"{percentage:.1f}%"
            ])

        csv_bytes = output.getvalue().encode('utf-8')
        output.close()
        return csv_bytes

    @staticmethod
    def export_budgets_csv(budgets: List[Dict[str, Any]]) -> bytes:
        """
        Export budgets to CSV format.

        Args:
            budgets: List of budget records

        Returns:
            CSV file as bytes
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Budget Name',
            'Budgeted Amount (USD)',
            'Actual Spend (USD)',
            'Forecasted Spend (USD)',
            'Utilization (%)',
            'Status'
        ])

        # Data
        for budget in budgets:
            budgeted_amount = budget.get('budgeted_amount', 0)
            actual_spend = budget.get('actual_spend', 0)
            utilization = (actual_spend / budgeted_amount * 100) if budgeted_amount > 0 else 0

            writer.writerow([
                budget.get('budget_name', ''),
                f"{budgeted_amount:.2f}",
                f"{actual_spend:.2f}",
                f"{budget.get('forecasted_spend', 0):.2f}",
                f"{utilization:.1f}%",
                budget.get('status', 'Unknown')
            ])

        csv_bytes = output.getvalue().encode('utf-8')
        output.close()
        return csv_bytes

    @staticmethod
    def export_forecast_csv(forecast_data: List[Dict[str, Any]]) -> bytes:
        """
        Export forecast data to CSV format.

        Args:
            forecast_data: List of forecast predictions

        Returns:
            CSV file as bytes
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Date',
            'Predicted Cost (USD)',
            'Lower Bound (USD)',
            'Upper Bound (USD)'
        ])

        # Data
        for record in forecast_data:
            writer.writerow([
                record.get('date', ''),
                f"{record.get('predicted_cost', 0):.2f}",
                f"{record.get('lower_bound', 0):.2f}",
                f"{record.get('upper_bound', 0):.2f}"
            ])

        csv_bytes = output.getvalue().encode('utf-8')
        output.close()
        return csv_bytes

    @staticmethod
    def export_anomalies_csv(anomalies: List[Dict[str, Any]]) -> bytes:
        """
        Export anomaly detection results to CSV format.

        Args:
            anomalies: List of detected anomalies

        Returns:
            CSV file as bytes
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Date',
            'Cost (USD)',
            'Severity',
            'Type',
            'Percentage Change (%)',
            'Description'
        ])

        # Data
        for anomaly in anomalies:
            writer.writerow([
                anomaly.get('date', ''),
                f"{anomaly.get('cost', 0):.2f}",
                anomaly.get('severity', ''),
                anomaly.get('type', ''),
                f"{anomaly.get('percentage_change', 0):.1f}%",
                anomaly.get('description', '')
            ])

        csv_bytes = output.getvalue().encode('utf-8')
        output.close()
        return csv_bytes

    @staticmethod
    def export_rightsizing_csv(recommendations: List[Dict[str, Any]]) -> bytes:
        """
        Export right-sizing recommendations to CSV format.

        Args:
            recommendations: List of right-sizing recommendations

        Returns:
            CSV file as bytes
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Resource ARN',
            'Resource Name',
            'Resource Type',
            'Region',
            'Current Config',
            'Recommended Config',
            'Finding',
            'CPU Utilization (%)',
            'Memory Utilization (%)',
            'Performance Risk',
            'Estimated Monthly Savings (USD)',
            'Savings Percentage (%)',
            'Recommendation Source'
        ])

        # Data
        for rec in recommendations:
            writer.writerow([
                rec.get('resource_arn', ''),
                rec.get('resource_name', ''),
                rec.get('resource_type', ''),
                rec.get('region', ''),
                rec.get('current_config', ''),
                rec.get('recommended_config', ''),
                rec.get('finding', ''),
                f"{rec.get('cpu_utilization', 0):.1f}" if rec.get('cpu_utilization') is not None else 'N/A',
                f"{rec.get('memory_utilization', 0):.1f}" if rec.get('memory_utilization') is not None else 'N/A',
                f"{rec.get('performance_risk', 0):.1f}" if rec.get('performance_risk') is not None else 'N/A',
                f"{rec.get('estimated_monthly_savings', 0):.2f}",
                f"{rec.get('savings_percentage', 0):.1f}" if rec.get('savings_percentage') is not None else 'N/A',
                rec.get('recommendation_source', '')
            ])

        csv_bytes = output.getvalue().encode('utf-8')
        output.close()
        return csv_bytes

    @staticmethod
    def export_unit_costs_csv(unit_costs: Dict[str, Any]) -> bytes:
        """
        Export unit cost metrics to CSV format.

        Args:
            unit_costs: Unit cost data

        Returns:
            CSV file as bytes
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(['Metric', 'Value'])

        # Summary data
        writer.writerow(['Profile Name', unit_costs.get('profile_name', '')])
        writer.writerow(['Period', f"{unit_costs.get('start_date', '')} to {unit_costs.get('end_date', '')}"])
        writer.writerow(['Region', unit_costs.get('region', '')])
        writer.writerow(['Total Cost (USD)', f"{unit_costs.get('total_cost', 0):.2f}"])

        # Unit metrics
        writer.writerow([])
        writer.writerow(['Unit Cost Metrics', ''])

        for metric_name, metric_value in unit_costs.get('unit_costs', {}).items():
            formatted_name = metric_name.replace('_', ' ').title()
            if isinstance(metric_value, (int, float)):
                writer.writerow([formatted_name, f"{metric_value:.4f}"])
            else:
                writer.writerow([formatted_name, str(metric_value)])

        csv_bytes = output.getvalue().encode('utf-8')
        output.close()
        return csv_bytes

    @staticmethod
    def export_to_json(data: Any, indent: int = 2) -> bytes:
        """
        Export any data structure to JSON format.

        Args:
            data: Data to export
            indent: JSON indentation level

        Returns:
            JSON file as bytes
        """
        json_str = json.dumps(data, indent=indent, default=str)
        return json_str.encode('utf-8')

    @staticmethod
    def generate_filename(
        data_type: str,
        profile_name: str,
        file_format: str = 'csv'
    ) -> str:
        """
        Generate a standardized filename for exports.

        Args:
            data_type: Type of data (e.g., 'daily_costs', 'budgets', 'rightsizing')
            profile_name: AWS profile/account name
            file_format: File format extension

        Returns:
            Standardized filename
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_profile_name = profile_name.replace(' ', '_').replace('/', '_')
        return f"{data_type}_{safe_profile_name}_{timestamp}.{file_format}"
