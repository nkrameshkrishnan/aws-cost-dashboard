"""
Step Functions cost optimization auditor.
Identifies unused state machines.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class StepFunctionsAuditor:
    """Auditor for Step Functions state machines."""

    def __init__(self, session: boto3.Session, region: str):
        self.session = session
        self.region = region
        self.sfn = session.client('stepfunctions', region_name=region)

    def audit_unused_state_machines(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Find Step Functions state machines with no executions.

        Args:
            days: Number of days to check for executions (default: 30)

        Returns:
            List of unused state machines
        """
        unused = []

        try:
            paginator = self.sfn.get_paginator('list_state_machines')

            for page in paginator.paginate():
                for sm in page.get('stateMachines', []):
                    sm_arn = sm['stateMachineArn']
                    sm_name = sm['name']
                    sm_type = sm.get('type', 'STANDARD')

                    # List executions in the last N days
                    try:
                        exec_response = self.sfn.list_executions(
                            stateMachineArn=sm_arn,
                            maxResults=1
                        )

                        executions = exec_response.get('executions', [])

                        if len(executions) == 0:
                            # No executions at all
                            unused.append({
                                'state_machine_name': sm_name,
                                'state_machine_arn': sm_arn,
                                'type': sm_type,
                                'region': self.region,
                                'total_executions': 0,
                                'created_date': sm.get('creationDate', '').isoformat() if sm.get('creationDate') else None,
                                'recommendation': 'Delete unused state machine'
                            })
                        else:
                            # Check if latest execution is older than threshold
                            latest_execution = executions[0]
                            start_date = latest_execution.get('startDate')

                            if start_date:
                                days_since = (datetime.now(start_date.tzinfo) - start_date).days

                                if days_since > days:
                                    unused.append({
                                        'state_machine_name': sm_name,
                                        'state_machine_arn': sm_arn,
                                        'type': sm_type,
                                        'region': self.region,
                                        'days_since_last_execution': days_since,
                                        'last_execution_date': start_date.isoformat(),
                                        'recommendation': f'No executions in {days} days - consider deleting'
                                    })

                    except ClientError as e:
                        logger.warning(f"Could not list executions for state machine {sm_name}: {e}")

        except ClientError as e:
            logger.error(f"Error listing Step Functions state machines: {e}")

        return unused
