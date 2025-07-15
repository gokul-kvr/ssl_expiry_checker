# send_email_util.py

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64

def send_email(subject, body, recipients):
    sender_email = os.getenv("EMAIL_FROM")
    sender_name = os.getenv("EMAIL_FROM_NAME", sender_email)
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    use_gmail_oauth = os.getenv("GMAIL_OAUTH", "0") == "1"

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "html"))

    # if smtp_host:
    #     with smtplib.SMTP(smtp_host, smtp_port) as server:
    #         server.starttls()
    #         if smtp_user and smtp_password:
    #             server.login(smtp_user, smtp_password)
    #         server.send_message(msg)
    # elif use_gmail_oauth:
    try:
        creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/gmail.send"])
        service = build('gmail', 'v1', credentials=creds)
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        message = {'raw': raw_message}
        sent_message = service.users().messages().send(userId="me", body=message).execute()
        print(f"Message sent: {sent_message['id']}")
    except Exception as e:
        raise RuntimeError(f"OAuth Error: {e}")
    # else:
    #     raise RuntimeError("No email method configured.")
