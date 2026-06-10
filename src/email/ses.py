"""AWS SES helper."""

from __future__ import annotations

from dataclasses import dataclass

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.config import AWS_ACCESS_KEY_ID, AWS_REGION, AWS_SECRET_ACCESS_KEY, SES_SENDER_EMAIL


@dataclass
class EmailResult:
    sent: bool
    message_id: str | None = None
    error: str | None = None


def send_email(to_email: str, subject: str, html_body: str, text_body: str | None = None) -> EmailResult:
    if not SES_SENDER_EMAIL:
        return EmailResult(sent=False, error="SES_SENDER_EMAIL is not configured.")

    if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
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
        return EmailResult(sent=True, message_id=response.get("MessageId"))
    except (BotoCoreError, ClientError) as exc:
        return EmailResult(sent=False, error=str(exc))

