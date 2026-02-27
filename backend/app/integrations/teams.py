"""
Microsoft Teams webhook integration service.
Sends notifications and reports to Teams channels using Adaptive Cards.
"""
import logging
from typing import Dict, Any, List, Optional
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class TeamsNotificationService:
    """Service for sending notifications to Microsoft Teams."""

    @staticmethod
    def send_adaptive_card(webhook_url: str, card_data: Dict[str, Any]) -> bool:
        """
        Send an adaptive card to Teams webhook.

        Args:
            webhook_url: Teams incoming webhook URL
            card_data: Adaptive card JSON data

        Returns:
            True if successful, False otherwise
        """
        try:
            headers = {"Content-Type": "application/json"}
            response = requests.post(webhook_url, json=card_data, headers=headers, timeout=10)

            if response.status_code == 200:
                logger.info("Successfully sent notification to Teams")
                return True
            else:
                logger.error(f"Failed to send Teams notification: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Teams notification: {e}")
            return False

    @staticmethod
    def create_budget_alert_card(
        budget_name: str,
        current_spend: float,
        budget_amount: float,
        percentage: float,
        forecast_spend: float,
        account_name: str
    ) -> Dict[str, Any]:
        """
        Create an enhanced adaptive card for budget threshold alerts.

        Args:
            budget_name: Name of the budget
            current_spend: Current spending amount
            budget_amount: Total budget amount
            percentage: Percentage of budget used
            forecast_spend: Forecasted spend for the period
            account_name: AWS account name

        Returns:
            Adaptive card JSON
        """
        # Determine alert color and status based on percentage
        if percentage >= 100:
            color = "attention"  # Red
            status = "🚨 BUDGET EXCEEDED"
            accent_color = "#DC2626"  # Red-600
        elif percentage >= 90:
            color = "warning"  # Yellow
            status = "⚠️ BUDGET WARNING"
            accent_color = "#F59E0B"  # Amber-500
        elif percentage >= 80:
            color = "accent"  # Blue
            status = "⚡ BUDGET ALERT"
            accent_color = "#3B82F6"  # Blue-500
        else:
            color = "good"  # Green
            status = "✅ BUDGET OK"
            accent_color = "#10B981"  # Green-500

        # Calculate forecast percentage
        forecast_percentage = (forecast_spend / budget_amount * 100) if budget_amount > 0 else 0

        # Determine budget health emoji
        if forecast_percentage >= 100:
            health_emoji = "🔴"
        elif forecast_percentage >= 90:
            health_emoji = "🟡"
        else:
            health_emoji = "🟢"

        card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            # Header with status
                            {
                                "type": "Container",
                                "style": "emphasis",
                                "items": [
                                    {
                                        "type": "ColumnSet",
                                        "columns": [
                                            {
                                                "type": "Column",
                                                "width": "auto",
                                                "items": [
                                                    {
                                                        "type": "TextBlock",
                                                        "text": status,
                                                        "weight": "bolder",
                                                        "size": "large",
                                                        "color": color
                                                    }
                                                ]
                                            },
                                            {
                                                "type": "Column",
                                                "width": "stretch",
                                                "items": [
                                                    {
                                                        "type": "TextBlock",
                                                        "text": health_emoji,
                                                        "size": "extraLarge",
                                                        "horizontalAlignment": "right"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"**{budget_name}**",
                                        "size": "medium",
                                        "spacing": "small"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"📊 {account_name}",
                                        "isSubtle": True,
                                        "size": "small",
                                        "spacing": "none"
                                    }
                                ],
                                "bleed": True
                            },
                            # Current spending section - each metric on its own line
                            {
                                "type": "Container",
                                "spacing": "medium",
                                "separator": True,
                                "items": [
                                    # Current Spend
                                    {
                                        "type": "TextBlock",
                                        "text": "💳 Current Spend",
                                        "weight": "bolder",
                                        "size": "medium"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"${current_spend:,.2f}",
                                        "size": "extraLarge",
                                        "weight": "bolder",
                                        "spacing": "small"
                                    },
                                    # Budget Amount (separate line)
                                    {
                                        "type": "TextBlock",
                                        "text": "📈 Budget Amount",
                                        "weight": "bolder",
                                        "size": "medium",
                                        "spacing": "medium"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"${budget_amount:,.2f}",
                                        "size": "extraLarge",
                                        "weight": "bolder",
                                        "spacing": "small"
                                    },
                                    # Usage percentage (separate line)
                                    {
                                        "type": "TextBlock",
                                        "text": "📊 Usage",
                                        "weight": "bolder",
                                        "size": "medium",
                                        "spacing": "medium"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"{percentage:.1f}%",
                                        "size": "extraLarge",
                                        "weight": "bolder",
                                        "color": color,
                                        "spacing": "small"
                                    }
                                ]
                            },
                            # Forecast section - on its own line
                            {
                                "type": "Container",
                                "spacing": "medium",
                                "separator": True,
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": "🔮 Forecasted End-of-Month",
                                        "weight": "bolder",
                                        "size": "medium"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"${forecast_spend:,.2f}",
                                        "size": "extraLarge",
                                        "weight": "bolder",
                                        "color": "warning" if forecast_percentage > 100 else "good",
                                        "spacing": "small"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"({forecast_percentage:.1f}% of budget)",
                                        "isSubtle": True,
                                        "size": "small",
                                        "spacing": "none"
                                    }
                                ]
                            },
                            # Footer
                            {
                                "type": "Container",
                                "spacing": "medium",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": f"⏰ {datetime.now().strftime('%Y-%m-%d %I:%M %p')}",
                                        "size": "small",
                                        "isSubtle": True,
                                        "horizontalAlignment": "right"
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }
        return card

    @staticmethod
    def create_cost_summary_card(
        period: str,
        total_cost: float,
        previous_cost: float,
        change_percentage: float,
        top_services: List[Dict[str, Any]],
        account_name: str
    ) -> Dict[str, Any]:
        """
        Create an adaptive card for cost summary reports.

        Args:
            period: Time period (e.g., "Daily", "Weekly", "Monthly")
            total_cost: Total cost for the period
            previous_cost: Previous period cost
            change_percentage: Percentage change
            top_services: List of top services by cost
            account_name: AWS account name

        Returns:
            Adaptive card JSON
        """
        # Determine trend indicator
        if change_percentage > 10:
            trend = "📈 Significant Increase"
            color = "attention"
        elif change_percentage > 0:
            trend = "↗️ Slight Increase"
            color = "warning"
        elif change_percentage < -10:
            trend = "📉 Significant Decrease"
            color = "good"
        elif change_percentage < 0:
            trend = "↘️ Slight Decrease"
            color = "good"
        else:
            trend = "➡️ No Change"
            color = "accent"

        # Build top services list
        service_facts = []
        for service in top_services[:5]:  # Top 5 services
            service_facts.append({
                "title": service.get('service_name', 'Unknown'),
                "value": f"${service.get('cost', 0):,.2f}"
            })

        card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": f"{period} Cost Summary",
                                "weight": "bolder",
                                "size": "large"
                            },
                            {
                                "type": "TextBlock",
                                "text": f"Account: {account_name}",
                                "isSubtle": True,
                                "spacing": "none"
                            },
                            {
                                "type": "ColumnSet",
                                "columns": [
                                    {
                                        "type": "Column",
                                        "width": "stretch",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": "Total Cost",
                                                "weight": "bolder"
                                            },
                                            {
                                                "type": "TextBlock",
                                                "text": f"${total_cost:,.2f}",
                                                "size": "extraLarge",
                                                "color": "accent"
                                            }
                                        ]
                                    },
                                    {
                                        "type": "Column",
                                        "width": "stretch",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": "Change",
                                                "weight": "bolder"
                                            },
                                            {
                                                "type": "TextBlock",
                                                "text": f"{change_percentage:+.1f}%",
                                                "size": "large",
                                                "color": color
                                            },
                                            {
                                                "type": "TextBlock",
                                                "text": trend,
                                                "size": "small",
                                                "isSubtle": True
                                            }
                                        ]
                                    }
                                ],
                                "spacing": "medium"
                            },
                            {
                                "type": "TextBlock",
                                "text": "Top Services",
                                "weight": "bolder",
                                "spacing": "medium"
                            },
                            {
                                "type": "FactSet",
                                "facts": service_facts,
                                "spacing": "small"
                            },
                            {
                                "type": "TextBlock",
                                "text": f"Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                "size": "small",
                                "isSubtle": True,
                                "spacing": "medium"
                            }
                        ]
                    }
                }
            ]
        }
        return card

    @staticmethod
    def create_audit_findings_card(
        total_findings: int,
        potential_savings: float,
        top_findings: List[Dict[str, Any]],
        account_name: str
    ) -> Dict[str, Any]:
        """
        Create an enhanced adaptive card for FinOps audit findings.

        Args:
            total_findings: Total number of findings
            potential_savings: Total potential monthly savings
            top_findings: List of top findings
            account_name: AWS account name

        Returns:
            Adaptive card JSON
        """
        # Determine severity color based on total findings
        if total_findings > 1000:
            findings_color = "attention"
            severity_emoji = "🔴"
            severity_text = "Critical"
        elif total_findings > 500:
            findings_color = "warning"
            severity_emoji = "🟡"
            severity_text = "High"
        elif total_findings > 100:
            findings_color = "accent"
            severity_emoji = "🟠"
            severity_text = "Medium"
        else:
            findings_color = "good"
            severity_emoji = "🟢"
            severity_text = "Low"

        # Icon mapping for finding types
        finding_icons = {
            "EC2 Idle Instances": "💤",
            "EC2 Stopped Instances": "⏸️",
            "Load Balancers (No Targets)": "⚖️",
            "Unattached EBS Volumes": "💾",
            "RDS Idle Instances": "🗄️",
            "Unattached Elastic IPs": "🌐",
            "Lambda Over-Provisioned": "⚡",
            "S3 No Lifecycle": "📦",
            "NAT Gateway Idle": "🚪",
            "Old EBS Snapshots": "📸"
        }

        # Build findings list with icons - each finding on its own line
        findings_items = []
        for finding in top_findings[:5]:  # Top 5 findings
            finding_type = finding.get('type', 'Unknown')
            count = finding.get('count', 0)
            savings = finding.get('savings', 0)

            # Get icon or default
            icon = finding_icons.get(finding_type, "•")

            # Add finding as a container with vertical layout
            findings_items.append({
                "type": "Container",
                "spacing": "medium",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": f"{icon} {finding_type}",
                        "weight": "bolder",
                        "size": "medium"
                    },
                    {
                        "type": "TextBlock",
                        "text": f"${savings:,.2f}/month savings",
                        "color": "good",
                        "size": "medium",
                        "weight": "bolder",
                        "spacing": "small"
                    }
                ]
            })

        card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            # Header section
                            {
                                "type": "Container",
                                "style": "emphasis",
                                "items": [
                                    {
                                        "type": "ColumnSet",
                                        "columns": [
                                            {
                                                "type": "Column",
                                                "width": "auto",
                                                "items": [
                                                    {
                                                        "type": "TextBlock",
                                                        "text": "🔍",
                                                        "size": "extraLarge"
                                                    }
                                                ]
                                            },
                                            {
                                                "type": "Column",
                                                "width": "stretch",
                                                "items": [
                                                    {
                                                        "type": "TextBlock",
                                                        "text": "FinOps Audit Report",
                                                        "weight": "bolder",
                                                        "size": "large"
                                                    },
                                                    {
                                                        "type": "TextBlock",
                                                        "text": f"📊 {account_name}",
                                                        "isSubtle": True,
                                                        "size": "small",
                                                        "spacing": "none"
                                                    }
                                                ]
                                            },
                                            {
                                                "type": "Column",
                                                "width": "auto",
                                                "items": [
                                                    {
                                                        "type": "TextBlock",
                                                        "text": severity_emoji,
                                                        "size": "extraLarge"
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ],
                                "bleed": True
                            },
                            # Summary metrics - each on its own line
                            {
                                "type": "Container",
                                "spacing": "medium",
                                "separator": True,
                                "items": [
                                    # Total Findings
                                    {
                                        "type": "TextBlock",
                                        "text": "🎯 Total Findings",
                                        "weight": "bolder",
                                        "size": "medium"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"{total_findings:,}",
                                        "size": "extraLarge",
                                        "weight": "bolder",
                                        "color": findings_color,
                                        "spacing": "small"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"{severity_text} severity",
                                        "isSubtle": True,
                                        "size": "small",
                                        "spacing": "none"
                                    },
                                    # Potential Savings (separate line)
                                    {
                                        "type": "TextBlock",
                                        "text": "💰 Potential Savings",
                                        "weight": "bolder",
                                        "size": "medium",
                                        "spacing": "medium"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"${potential_savings:,.2f}",
                                        "size": "extraLarge",
                                        "weight": "bolder",
                                        "color": "good",
                                        "spacing": "small"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": "per month",
                                        "isSubtle": True,
                                        "size": "small",
                                        "spacing": "none"
                                    }
                                ]
                            },
                            # Top opportunities section
                            {
                                "type": "Container",
                                "spacing": "medium",
                                "separator": True,
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": "🏆 Top Opportunities",
                                        "weight": "bolder",
                                        "size": "medium",
                                        "color": "accent"
                                    }
                                ] + findings_items if findings_items else [
                                    {
                                        "type": "TextBlock",
                                        "text": "✅ No significant findings",
                                        "isSubtle": True,
                                        "horizontalAlignment": "center"
                                    }
                                ]
                            },
                            # Footer
                            {
                                "type": "Container",
                                "spacing": "medium",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": f"⏰ {datetime.now().strftime('%Y-%m-%d %I:%M %p')}",
                                        "size": "small",
                                        "isSubtle": True,
                                        "horizontalAlignment": "right"
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }
        return card

    @staticmethod
    def create_simple_message_card(title: str, message: str, color: str = "accent") -> Dict[str, Any]:
        """
        Create a simple message card.

        Args:
            title: Card title
            message: Message text
            color: Card color (good, warning, attention, accent)

        Returns:
            Adaptive card JSON
        """
        card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": title,
                                "weight": "bolder",
                                "size": "large",
                                "color": color
                            },
                            {
                                "type": "TextBlock",
                                "text": message,
                                "wrap": True,
                                "spacing": "medium"
                            },
                            {
                                "type": "TextBlock",
                                "text": f"Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                "size": "small",
                                "isSubtle": True,
                                "spacing": "medium"
                            }
                        ]
                    }
                }
            ]
        }
        return card

    @staticmethod
    def send_to_power_automate(webhook_url: str, data: Dict[str, Any]) -> bool:
        """
        Send a notification to Power Automate workflow.

        Args:
            webhook_url: Power Automate workflow webhook URL
            data: Notification data

        Returns:
            True if successful, False otherwise
        """
        try:
            headers = {"Content-Type": "application/json"}
            response = requests.post(webhook_url, json=data, headers=headers, timeout=10)

            if response.status_code in [200, 202]:  # Power Automate returns 202 Accepted
                logger.info("Successfully sent notification to Power Automate")
                return True
            else:
                logger.error(f"Failed to send Power Automate notification: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Power Automate notification: {e}")
            return False

    @staticmethod
    def convert_to_power_automate_format(notification_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert adaptive card data to simple Power Automate format.

        Args:
            notification_type: Type of notification
            data: Original notification data

        Returns:
            Simple JSON format for Power Automate with 'text' field
        """
        # Power Automate expects simpler JSON structure with a 'text' field
        if notification_type == "budget_alert":
            budget_name = data.get('budget_name', 'Unknown')
            current_spend = data.get('current_spend', 0)
            budget_amount = data.get('budget_amount', 0)
            percentage = data.get('percentage', 0)
            forecast_spend = data.get('forecast_spend', 0)
            account_name = data.get('account_name', 'Unknown')

            # Determine status emoji
            if percentage >= 100:
                status_emoji = "🚨"
                status_text = "BUDGET EXCEEDED"
            elif percentage >= 90:
                status_emoji = "⚠️"
                status_text = "BUDGET WARNING"
            elif percentage >= 80:
                status_emoji = "⚡"
                status_text = "BUDGET ALERT"
            else:
                status_emoji = "✅"
                status_text = "BUDGET OK"

            text = f"""{status_emoji} {status_text}: {budget_name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Account: {account_name}


💳 Current Spend:    ${current_spend:,.2f}

📈 Budget Amount:    ${budget_amount:,.2f}

📊 Usage:            {percentage:.1f}%

🔮 Forecast:         ${forecast_spend:,.2f}


⏰ {datetime.now().strftime('%Y-%m-%d %I:%M %p')}"""

            return {
                "text": text,
                "notification_type": "budget_alert",
                "budget_name": budget_name,
                "current_spend": current_spend,
                "budget_amount": budget_amount,
                "percentage": percentage,
                "forecast_spend": forecast_spend,
                "account_name": account_name,
                "timestamp": datetime.now().isoformat()
            }
        elif notification_type == "cost_summary":
            period = data.get('period', 'Daily')
            total_cost = data.get('total_cost', 0)
            previous_cost = data.get('previous_cost', 0)
            change_percentage = data.get('change_percentage', 0)
            account_name = data.get('account_name', 'Unknown')

            trend = "📈" if change_percentage > 0 else "📉" if change_percentage < 0 else "➡️"

            text = f"""{period} Cost Summary
Account: {account_name}
Total Cost: ${total_cost:,.2f}
Change: {trend} {change_percentage:+.1f}%
Previous: ${previous_cost:,.2f}"""

            return {
                "text": text,
                "notification_type": "cost_summary",
                "period": period,
                "total_cost": total_cost,
                "previous_cost": previous_cost,
                "change_percentage": change_percentage,
                "top_services": data.get('top_services', []),
                "account_name": account_name,
                "timestamp": datetime.now().isoformat()
            }
        elif notification_type == "audit_report":
            total_findings = data.get('total_findings', 0)
            potential_savings = data.get('potential_savings', 0)
            account_name = data.get('account_name', 'Unknown')
            top_findings = data.get('top_findings', [])

            # Icon mapping for finding types
            finding_icons = {
                "EC2 Idle Instances": "💤",
                "EC2 Stopped Instances": "⏸️",
                "Load Balancers (No Targets)": "⚖️",
                "Unattached EBS Volumes": "💾",
                "RDS Idle Instances": "🗄️",
                "Unattached Elastic IPs": "🌐",
                "Lambda Over-Provisioned": "⚡",
                "S3 No Lifecycle": "📦",
                "NAT Gateway Idle": "🚪",
                "Old EBS Snapshots": "📸"
            }

            findings_text = "\n".join([
                f"{finding_icons.get(f.get('type', 'Unknown'), '•')} {f.get('type', 'Unknown')}: ${f.get('savings', 0):,.2f}/mo"
                for f in top_findings[:5]
            ]) if top_findings else "✅ No major findings"

            # Determine severity
            if total_findings > 1000:
                severity = "🔴 Critical"
            elif total_findings > 500:
                severity = "🟡 High"
            elif total_findings > 100:
                severity = "🟠 Medium"
            else:
                severity = "🟢 Low"

            text = f"""🔍 FinOps Audit Report

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Account: {account_name}


🎯 Total Findings:       {total_findings:,}

   Severity:             {severity}


💰 Potential Savings:    ${potential_savings:,.2f}/month


🏆 Top Opportunities:

{findings_text}


⏰ {datetime.now().strftime('%Y-%m-%d %I:%M %p')}"""

            return {
                "text": text,
                "notification_type": "audit_report",
                "total_findings": total_findings,
                "potential_savings": potential_savings,
                "top_findings": top_findings,
                "account_name": account_name,
                "timestamp": datetime.now().isoformat()
            }
        else:  # custom
            text = f"{data.get('title', 'Notification')}\n{data.get('message', '')}"
            return {
                "text": text,
                "notification_type": "custom",
                "title": data.get('title', 'Notification'),
                "message": data.get('message', ''),
                "timestamp": datetime.now().isoformat()
            }

    @staticmethod
    def test_webhook(webhook_url: str, webhook_type: str = 'teams') -> bool:
        """
        Test a webhook by sending a test message.

        Args:
            webhook_url: Webhook URL
            webhook_type: Type of webhook ('teams' or 'power_automate')

        Returns:
            True if successful, False otherwise
        """
        if webhook_type == 'power_automate':
            # Send simple JSON for Power Automate with 'text' field
            test_data = {
                "text": "✅ AWS Cost Dashboard - Test Notification\n\nYour Power Automate webhook is configured correctly and working!",
                "notification_type": "test",
                "title": "AWS Cost Dashboard - Test Notification",
                "message": "Your Power Automate webhook is configured correctly and working!",
                "timestamp": datetime.now().isoformat()
            }
            return TeamsNotificationService.send_to_power_automate(webhook_url, test_data)
        else:
            # Send adaptive card for Teams
            test_card = TeamsNotificationService.create_simple_message_card(
                title="✅ AWS Cost Dashboard - Test Notification",
                message="Your Microsoft Teams webhook is configured correctly and working!",
                color="good"
            )
            return TeamsNotificationService.send_adaptive_card(webhook_url, test_card)
