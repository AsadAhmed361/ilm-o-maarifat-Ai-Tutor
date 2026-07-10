"""
services/email_sender.py

Sends an already-HTML-formatted report via Gmail SMTP. HTML conversion
happens ONCE in the caller (test.py) and is reused for both the API
response and the email body -- avoids converting markdown twice.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailSender:
    def __init__(self):
        self.sender_email = os.environ.get("SENDER_EMAIL")
        self.sender_password = os.environ.get("SENDER_APP_PASSWORD")

        if not self.sender_email or not self.sender_password:
            raise RuntimeError("SENDER_EMAIL and SENDER_APP_PASSWORD environment variables must be set")

        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def send(self, html_body: str, plain_body: str, recipient_email: str, subject: str = "Your Progress Report"):
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.sender_email
        message["To"] = recipient_email

        # Plain text fallback for clients that don't render HTML
        message.attach(MIMEText(plain_body, "plain"))
        message.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, recipient_email, message.as_string())
            print(f"Report emailed successfully to {recipient_email}")
        except Exception as e:
            # Runs as a background task -- can't raise back to the client,
            # so we log and swallow. The API response has ALREADY been
            # sent by this point regardless of what happens here.
            print(f"Failed to send email to {recipient_email}: {e}")
