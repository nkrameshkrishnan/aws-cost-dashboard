"""
Centralized cache TTL configuration.
Optimized TTL values based on data volatility and access patterns.
"""

class CacheTTL:
    """
    Cache Time-To-Live (TTL) constants in seconds.

    Optimized based on:
    - Data change frequency
    - AWS API rate limits
    - Cost optimization (minimize API calls)
    - User experience (freshness vs performance)
    """

    # Cost Data - High volatility for current period, low for historical
    COST_CURRENT_MONTH = 300         # 5 minutes - updates frequently
    COST_HISTORICAL = 86400          # 24 hours - doesn't change
    COST_DAILY = 900                 # 15 minutes - balance freshness/cost
    COST_BY_SERVICE = 900            # 15 minutes
    COST_FORECAST = 3600             # 1 hour - AWS forecast stable
    COST_TREND = 1800                # 30 minutes

    # Budget Data - Medium volatility
    BUDGET_LIST = 600                # 10 minutes
    BUDGET_STATUS = 600              # 10 minutes - needs current data
    BUDGET_SUMMARY = 600             # 10 minutes

    # FinOps Audit - Low volatility (resources change slowly)
    AUDIT_RESULTS = 1800             # 30 minutes
    AUDIT_SUMMARY = 1800             # 30 minutes
    IDLE_INSTANCES = 1800            # 30 minutes
    UNTAGGED_RESOURCES = 3600        # 1 hour - tagging doesn't change often

    # Right-sizing - Very low volatility (requires 30+ hours data)
    RIGHTSIZING_RECOMMENDATIONS = 3600   # 1 hour - AWS Compute Optimizer data
    RIGHTSIZING_SUMMARY = 3600           # 1 hour

    # Analytics - Medium-low volatility
    ANALYTICS_FORECAST = 1800        # 30 minutes
    ANALYTICS_ANOMALY = 1800         # 30 minutes
    ANALYTICS_TREND = 1800           # 30 minutes
    MOM_COMPARISON = 3600            # 1 hour
    YOY_COMPARISON = 86400           # 24 hours - yearly data stable

    # Unit Costs - Medium volatility
    UNIT_COSTS = 900                 # 15 minutes
    UNIT_COST_TREND = 1800           # 30 minutes

    # KPI Metrics - Medium volatility
    KPI_VALUES = 900                 # 15 minutes
    KPI_DEFINITIONS = 3600           # 1 hour - definitions don't change often

    # AWS Account/Profile - Very low volatility
    AWS_ACCOUNTS = 3600              # 1 hour - rarely changes
    PROFILE_LIST = 3600              # 1 hour

    # Teams Webhooks - Low volatility
    TEAMS_WEBHOOKS = 1800            # 30 minutes

    # Performance Metrics - High volatility
    PERFORMANCE_STATS = 60           # 1 minute - real-time monitoring

    # Dashboard aggregated data - Medium volatility
    DASHBOARD_SUMMARY = 300          # 5 minutes - frequently accessed

    @classmethod
    def get_ttl_for_date_range(cls, start_date: str, end_date: str) -> int:
        """
        Get optimal TTL based on date range.

        - Current month data: 5 minutes (volatile)
        - Historical data: 24 hours (stable)
        - Mix: 15 minutes (balanced)

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Optimal TTL in seconds
        """
        from datetime import datetime

        try:
            end = datetime.strptime(end_date, '%Y-%m-%d')
            now = datetime.now()

            # If end date is current month, use short TTL
            if end.year == now.year and end.month == now.month:
                return cls.COST_CURRENT_MONTH

            # Historical data - long TTL
            return cls.COST_HISTORICAL

        except ValueError:
            # Default to balanced TTL if date parsing fails
            return cls.COST_DAILY

    @classmethod
    def get_summary(cls) -> dict:
        """Get summary of all TTL values for documentation."""
        return {
            "cost_data": {
                "current_month": f"{cls.COST_CURRENT_MONTH}s (5 min)",
                "historical": f"{cls.COST_HISTORICAL}s (24 hours)",
                "daily": f"{cls.COST_DAILY}s (15 min)",
                "by_service": f"{cls.COST_BY_SERVICE}s (15 min)",
                "forecast": f"{cls.COST_FORECAST}s (1 hour)",
            },
            "budgets": {
                "list": f"{cls.BUDGET_LIST}s (10 min)",
                "status": f"{cls.BUDGET_STATUS}s (10 min)",
            },
            "audits": {
                "results": f"{cls.AUDIT_RESULTS}s (30 min)",
                "summary": f"{cls.AUDIT_SUMMARY}s (30 min)",
            },
            "rightsizing": {
                "recommendations": f"{cls.RIGHTSIZING_RECOMMENDATIONS}s (1 hour)",
            },
            "analytics": {
                "forecast": f"{cls.ANALYTICS_FORECAST}s (30 min)",
                "mom_comparison": f"{cls.MOM_COMPARISON}s (1 hour)",
                "yoy_comparison": f"{cls.YOY_COMPARISON}s (24 hours)",
            },
        }


# Convenience exports
COST_CURRENT_MONTH = CacheTTL.COST_CURRENT_MONTH
COST_HISTORICAL = CacheTTL.COST_HISTORICAL
COST_DAILY = CacheTTL.COST_DAILY
COST_BY_SERVICE = CacheTTL.COST_BY_SERVICE
COST_FORECAST = CacheTTL.COST_FORECAST
COST_TREND = CacheTTL.COST_TREND

BUDGET_LIST = CacheTTL.BUDGET_LIST
BUDGET_STATUS = CacheTTL.BUDGET_STATUS
BUDGET_SUMMARY = CacheTTL.BUDGET_SUMMARY

AUDIT_RESULTS = CacheTTL.AUDIT_RESULTS
AUDIT_SUMMARY = CacheTTL.AUDIT_SUMMARY
IDLE_INSTANCES = CacheTTL.IDLE_INSTANCES
UNTAGGED_RESOURCES = CacheTTL.UNTAGGED_RESOURCES

RIGHTSIZING_RECOMMENDATIONS = CacheTTL.RIGHTSIZING_RECOMMENDATIONS
RIGHTSIZING_SUMMARY = CacheTTL.RIGHTSIZING_SUMMARY

ANALYTICS_FORECAST = CacheTTL.ANALYTICS_FORECAST
ANALYTICS_ANOMALY = CacheTTL.ANALYTICS_ANOMALY
MOM_COMPARISON = CacheTTL.MOM_COMPARISON
YOY_COMPARISON = CacheTTL.YOY_COMPARISON

UNIT_COSTS = CacheTTL.UNIT_COSTS
UNIT_COST_TREND = CacheTTL.UNIT_COST_TREND

KPI_VALUES = CacheTTL.KPI_VALUES
KPI_DEFINITIONS = CacheTTL.KPI_DEFINITIONS

AWS_ACCOUNTS = CacheTTL.AWS_ACCOUNTS
TEAMS_WEBHOOKS = CacheTTL.TEAMS_WEBHOOKS

PERFORMANCE_STATS = CacheTTL.PERFORMANCE_STATS
DASHBOARD_SUMMARY = CacheTTL.DASHBOARD_SUMMARY
