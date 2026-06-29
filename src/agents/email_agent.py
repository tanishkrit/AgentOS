"""
Email Agent — Communication Drafting and Sending

Drafts personalized emails using context from the blackboard
and sends them via SMTP (with user approval required).

When the local LLM is available, uses it to generate highly personalized
email content based on upstream research data. Falls back to template-based
generation when the LLM is unavailable.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.agents.base_agent import BaseAgent
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


class EmailAgent(BaseAgent):
    """
    Drafts and sends emails using templated content and upstream data.

    Capabilities:
    - Generate personalized emails from templates + context data
    - Queue emails for user review/approval
    - Send via SMTP (requires approval)
    """

    def execute(
        self,
        task_description: str,
        parameters: dict,
        dependency_data: dict,
    ) -> dict:
        """
        Execute an email task.

        Expected parameters:
            - template (str): Email body template with {placeholders}
            - subject (str): Email subject line
            - recipients (list[dict]): List of {"email": ..., "name": ..., ...}
            - smtp_host (str): SMTP server host
            - smtp_port (int): SMTP server port
            - smtp_user (str): SMTP username
            - smtp_pass (str): SMTP password
        """
        self.logger.info(f"Starting email task: {task_description}")

        template = parameters.get("template", "Hello {name},\n\n{message}\n\nBest regards")
        subject = parameters.get("subject", "Hello")
        recipients = parameters.get("recipients", [])
        smtp_host = parameters.get("smtp_host", "")
        smtp_port = parameters.get("smtp_port", 587)
        smtp_user = parameters.get("smtp_user", "")
        smtp_pass = parameters.get("smtp_pass", "")

        # Merge in any lead data from upstream research
        if not recipients and dependency_data:
            for dep_id, dep_result in dependency_data.items():
                leads = dep_result.get("data", [])
                for lead in leads:
                    if isinstance(lead, dict) and "email" in lead:
                        recipients.append(lead)

        drafted_emails = []
        sent_count = 0

        # ── Try LLM-powered personalized drafting ────────────────────
        llm = LLMClient.get_instance()
        if llm.available and recipients:
            self._emit_log("🤖 Using LLM to draft personalized emails...")

            # Gather context from upstream research
            context_summary = ""
            for dep_id, dep_result in dependency_data.items():
                if isinstance(dep_result, dict):
                    context_summary += dep_result.get("summary", "") + "\n"

            for recipient in recipients:
                recipient_info = ", ".join(
                    f"{k}: {v}" for k, v in recipient.items() if v
                )
                prompt = (
                    f"Write a professional outreach email.\n"
                    f"Recipient info: {recipient_info}\n"
                    f"Context: {context_summary[:500]}\n"
                    f"Subject hint: {subject}\n\n"
                    f"Return a JSON object with 'subject' and 'body' keys."
                )

                result = llm.generate_json(
                    prompt=prompt,
                    system=(
                        "You are a professional email copywriter. "
                        "Write concise, personalized outreach emails. "
                        "Return ONLY a JSON object with 'subject' and 'body' keys."
                    ),
                    temperature=0.4,
                    max_tokens=1024,
                    timeout=30,
                )

                if result and "body" in result:
                    drafted_emails.append({
                        "to": recipient.get("email", "unknown"),
                        "subject": result.get("subject", subject),
                        "body": result["body"],
                    })
                    self._emit_log(f"✉️ Drafted personalized email to: {recipient.get('email', 'unknown')}")
                else:
                    # Fallback to template for this recipient
                    body = template
                    for key, value in recipient.items():
                        body = body.replace(f"{{{key}}}", str(value))
                    drafted_emails.append({
                        "to": recipient.get("email", "unknown"),
                        "subject": subject,
                        "body": body,
                    })
        else:
            # ── Fallback: Template-based drafting ────────────────────
            for recipient in recipients:
                body = template
                for key, value in recipient.items():
                    body = body.replace(f"{{{key}}}", str(value))

                drafted_emails.append({
                    "to": recipient.get("email", "unknown"),
                    "subject": subject,
                    "body": body,
                })

        # Show drafted emails and request approval
        if drafted_emails:
            print(f"\n📧 {len(drafted_emails)} email(s) drafted:")
            for i, email in enumerate(drafted_emails, 1):
                print(f"   {i}. To: {email['to']} | Subject: {email['subject']}")
                print(f"      Preview: {email['body'][:100]}...")

            if smtp_host and self.request_approval(
                f"Send {len(drafted_emails)} email(s) via {smtp_host}?"
            ):
                sent_count = self._send_emails(
                    drafted_emails, smtp_host, smtp_port, smtp_user, smtp_pass
                )

        return {
            "success": True,
            "summary": f"Drafted {len(drafted_emails)} emails, sent {sent_count}.",
            "drafted": drafted_emails,
            "sent_count": sent_count,
        }

    def _send_emails(
        self,
        emails: list[dict],
        host: str,
        port: int,
        user: str,
        password: str,
    ) -> int:
        """Send emails via SMTP. Returns the count of successfully sent."""
        sent = 0
        try:
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(user, password)

                for email_data in emails:
                    try:
                        msg = MIMEMultipart()
                        msg["From"] = user
                        msg["To"] = email_data["to"]
                        msg["Subject"] = email_data["subject"]
                        msg.attach(MIMEText(email_data["body"], "plain"))

                        server.send_message(msg)
                        sent += 1
                        self.logger.info(f"Sent email to: {email_data['to']}")
                    except Exception as e:
                        self.logger.error(f"Failed to send to {email_data['to']}: {e}")

        except Exception as e:
            self.logger.error(f"SMTP connection failed: {e}")

        return sent
