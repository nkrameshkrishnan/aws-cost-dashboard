"""
Anomaly detection service for identifying unusual cost patterns.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class AnomalyDetectionService:
    """Service for detecting cost anomalies using statistical methods."""

    @staticmethod
    def detect_z_score_anomalies(
        historical_data: List[Dict[str, Any]],
        threshold: float = 3.0
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies using Z-score method.

        Args:
            historical_data: List of {"date": "YYYY-MM-DD", "cost": float}
            threshold: Z-score threshold (default: 3.0 = 99.7% confidence)

        Returns:
            List of detected anomalies
        """
        if len(historical_data) < 7:
            return []

        df = pd.DataFrame(historical_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # Calculate z-scores
        mean_cost = df['cost'].mean()
        std_cost = df['cost'].std()

        if std_cost == 0:
            return []

        df['z_score'] = (df['cost'] - mean_cost) / std_cost

        # Find anomalies
        anomalies = df[np.abs(df['z_score']) > threshold].copy()

        results = []
        for _, row in anomalies.iterrows():
            severity = "critical" if abs(row['z_score']) > 4 else "high"
            anomaly_type = "spike" if row['z_score'] > 0 else "drop"

            results.append({
                "date": row['date'].strftime("%Y-%m-%d"),
                "cost": row['cost'],
                "baseline_cost": mean_cost,
                "z_score": row['z_score'],
                "severity": severity,
                "type": anomaly_type,
                "delta": row['cost'] - mean_cost,
                "percentage_change": ((row['cost'] - mean_cost) / mean_cost * 100) if mean_cost > 0 else 0,
                "description": f"Cost is {abs(row['z_score']):.1f} standard deviations from normal"
            })

        return results

    @staticmethod
    def detect_iqr_anomalies(
        historical_data: List[Dict[str, Any]],
        multiplier: float = 1.5
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies using IQR (Interquartile Range) method.
        More robust to outliers than Z-score.

        Args:
            historical_data: List of {"date": "YYYY-MM-DD", "cost": float}
            multiplier: IQR multiplier (default: 1.5 for outliers, 3.0 for extreme outliers)

        Returns:
            List of detected anomalies
        """
        if len(historical_data) < 7:
            return []

        df = pd.DataFrame(historical_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # Calculate IQR
        Q1 = df['cost'].quantile(0.25)
        Q3 = df['cost'].quantile(0.75)
        IQR = Q3 - Q1

        # Calculate bounds
        lower_bound = Q1 - (multiplier * IQR)
        upper_bound = Q3 + (multiplier * IQR)

        # Find anomalies
        anomalies = df[(df['cost'] < lower_bound) | (df['cost'] > upper_bound)].copy()

        results = []
        for _, row in anomalies.iterrows():
            is_high = row['cost'] > upper_bound
            severity = "high" if multiplier == 1.5 else "critical"
            anomaly_type = "spike" if is_high else "drop"

            median_cost = df['cost'].median()

            results.append({
                "date": row['date'].strftime("%Y-%m-%d"),
                "cost": row['cost'],
                "baseline_cost": median_cost,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "severity": severity,
                "type": anomaly_type,
                "delta": row['cost'] - median_cost,
                "percentage_change": ((row['cost'] - median_cost) / median_cost * 100) if median_cost > 0 else 0,
                "description": f"Cost {'exceeds upper' if is_high else 'below lower'} bound (IQR method)"
            })

        return results

    @staticmethod
    def detect_sudden_spikes(
        historical_data: List[Dict[str, Any]],
        spike_threshold: float = 2.0
    ) -> List[Dict[str, Any]]:
        """
        Detect sudden cost spikes (day-over-day changes).

        Args:
            historical_data: List of {"date": "YYYY-MM-DD", "cost": float}
            spike_threshold: Multiplier for detecting spikes (e.g., 2.0 = 2x increase)

        Returns:
            List of detected spikes
        """
        if len(historical_data) < 2:
            return []

        df = pd.DataFrame(historical_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # Calculate day-over-day change
        df['previous_cost'] = df['cost'].shift(1)
        df['change_ratio'] = df['cost'] / df['previous_cost']
        df['percentage_change'] = ((df['cost'] - df['previous_cost']) / df['previous_cost']) * 100

        # Find spikes
        spikes = df[df['change_ratio'] >= spike_threshold].copy()

        results = []
        for _, row in spikes.iterrows():
            if pd.isna(row['previous_cost']):
                continue

            severity = "critical" if row['change_ratio'] >= 3.0 else "high"

            results.append({
                "date": row['date'].strftime("%Y-%m-%d"),
                "cost": row['cost'],
                "previous_cost": row['previous_cost'],
                "change_ratio": row['change_ratio'],
                "severity": severity,
                "type": "sudden_spike",
                "delta": row['cost'] - row['previous_cost'],
                "percentage_change": row['percentage_change'],
                "description": f"Cost increased {row['change_ratio']:.1f}x from previous day"
            })

        return results

    @staticmethod
    def detect_cost_drift(
        historical_data: List[Dict[str, Any]],
        window_size: int = 7,
        drift_threshold: float = 20.0
    ) -> List[Dict[str, Any]]:
        """
        Detect gradual cost drift (cost creep) over time.

        Args:
            historical_data: List of {"date": "YYYY-MM-DD", "cost": float}
            window_size: Number of days to compare (default: 7 days)
            drift_threshold: Percentage increase to flag as drift (default: 20%)

        Returns:
            List of detected drift periods
        """
        if len(historical_data) < window_size * 2:
            return []

        df = pd.DataFrame(historical_data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # Calculate rolling averages
        df['rolling_avg'] = df['cost'].rolling(window=window_size, min_periods=1).mean()

        results = []

        # Compare recent window to baseline
        recent_avg = df['rolling_avg'].tail(window_size).mean()
        baseline_avg = df['rolling_avg'].head(window_size).mean()

        if baseline_avg > 0:
            drift_percentage = ((recent_avg - baseline_avg) / baseline_avg) * 100

            if abs(drift_percentage) >= drift_threshold:
                severity = "high" if abs(drift_percentage) >= 30 else "medium"
                drift_type = "upward_drift" if drift_percentage > 0 else "downward_drift"

                results.append({
                    "start_date": df['date'].head(window_size).iloc[-1].strftime("%Y-%m-%d"),
                    "end_date": df['date'].tail(window_size).iloc[-1].strftime("%Y-%m-%d"),
                    "baseline_cost": baseline_avg,
                    "current_cost": recent_avg,
                    "drift_percentage": drift_percentage,
                    "severity": severity,
                    "type": drift_type,
                    "delta": recent_avg - baseline_avg,
                    "description": f"Cost has drifted {drift_percentage:+.1f}% over {window_size} days"
                })

        return results

    @staticmethod
    def detect_service_anomalies(
        service_costs: Dict[str, List[Dict[str, Any]]],
        threshold: float = 2.5
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in individual service costs.

        Args:
            service_costs: {"service_name": [{"date": "YYYY-MM-DD", "cost": float}]}
            threshold: Z-score threshold

        Returns:
            List of service-specific anomalies
        """
        all_anomalies = []

        for service_name, cost_data in service_costs.items():
            if len(cost_data) < 7:
                continue

            # Detect anomalies for this service
            service_anomalies = AnomalyDetectionService.detect_z_score_anomalies(
                cost_data, threshold
            )

            # Add service name to each anomaly
            for anomaly in service_anomalies:
                anomaly['service'] = service_name
                anomaly['affected_resource'] = service_name
                all_anomalies.append(anomaly)

        # Sort by severity and date
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_anomalies.sort(
            key=lambda x: (severity_order.get(x['severity'], 99), x['date']),
            reverse=True
        )

        return all_anomalies

    @staticmethod
    def get_anomaly_summary(
        historical_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get comprehensive anomaly detection summary using multiple methods.

        Args:
            historical_data: List of {"date": "YYYY-MM-DD", "cost": float}

        Returns:
            Summary of all detected anomalies
        """
        # Run all detection methods
        z_score_anomalies = AnomalyDetectionService.detect_z_score_anomalies(historical_data)
        iqr_anomalies = AnomalyDetectionService.detect_iqr_anomalies(historical_data)
        spike_anomalies = AnomalyDetectionService.detect_sudden_spikes(historical_data)
        drift_anomalies = AnomalyDetectionService.detect_cost_drift(historical_data)

        # Combine and deduplicate
        all_anomalies = []
        seen_dates = set()

        for anomaly in z_score_anomalies + iqr_anomalies + spike_anomalies:
            if anomaly['date'] not in seen_dates:
                seen_dates.add(anomaly['date'])
                all_anomalies.append(anomaly)

        # Sort by severity and date
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_anomalies.sort(
            key=lambda x: (severity_order.get(x['severity'], 99), x['date']),
            reverse=True
        )

        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for anomaly in all_anomalies:
            severity = anomaly.get('severity', 'low')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        return {
            "total_anomalies": len(all_anomalies),
            "critical_anomalies": severity_counts['critical'],
            "high_anomalies": severity_counts['high'],
            "medium_anomalies": severity_counts['medium'],
            "anomalies": all_anomalies[:20],  # Top 20 most severe
            "drift_analysis": drift_anomalies,
            "detection_methods_used": ["z_score", "iqr", "sudden_spike", "drift"],
            "data_points_analyzed": len(historical_data)
        }

    @staticmethod
    def recommend_actions(anomaly: Dict[str, Any]) -> List[str]:
        """
        Recommend actions based on anomaly type.

        Args:
            anomaly: Anomaly detection result

        Returns:
            List of recommended actions
        """
        recommendations = []
        anomaly_type = anomaly.get('type', '')
        severity = anomaly.get('severity', '')

        if anomaly_type == 'spike' or anomaly_type == 'sudden_spike':
            recommendations.extend([
                "Check CloudWatch for unusual resource usage",
                "Review recent infrastructure changes or deployments",
                "Check for autoscaling events or traffic spikes",
                "Verify no unauthorized resource launches"
            ])

        if anomaly_type == 'upward_drift':
            recommendations.extend([
                "Run FinOps audit to identify cost creep sources",
                "Review resource utilization trends",
                "Check for resource sprawl or zombie resources",
                "Consider implementing stricter resource policies"
            ])

        if severity == 'critical':
            recommendations.insert(0, "🚨 IMMEDIATE ACTION REQUIRED")
            recommendations.append("Send alert to team via Microsoft Teams")

        if not recommendations:
            recommendations.append("Investigate cost changes in AWS Cost Explorer")

        return recommendations
