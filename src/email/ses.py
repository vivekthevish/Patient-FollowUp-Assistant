"""AWS SES helper."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import AWS_ACCESS_KEY_ID, AWS_REGION, AWS_SECRET_ACCESS_KEY, MAX_RETRIES, SES_SENDER_EMAIL


logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    sent: bool
    message_id: str | None = None
    error: str | None = None


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    before_sleep=lambda retry_state: logger.warning(
        f"AWS SES email send failed (attempt {retry_state.attempt_number}/{MAX_RETRIES}), retrying..."
    )
)
def send_email(to_email: str, subject: str, html_body: str, text_body: str | None = None) -> EmailResult:
    if not SES_SENDER_EMAIL:
        logger.error("SES_SENDER_EMAIL is not configured")
        return EmailResult(sent=False, error="SES_SENDER_EMAIL is not configured.")

    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
        logger.error("AWS credentials are not configured")
        return EmailResult(sent=False, error="AWS credentials are not configured.")

    try:
        client = boto3.client(
            "ses",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        kwargs = {
            "Source": SES_SENDER_EMAIL,
            "Destination": {"ToAddresses": [to_email]},
            "Message": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                    "Text": {"Data": text_body or html_body, "Charset": "UTF-8"},
                },
            },
        }
        response = client.send_email(**kwargs)
        logger.info(f"Email sent successfully to {to_email}")
        return EmailResult(sent=True, message_id=response.get("MessageId"))
    except (BotoCoreError, ClientError) as exc:
        logger.error(f"Failed to send email to {to_email}: {exc}")
        return EmailResult(sent=False, error=str(exc))

