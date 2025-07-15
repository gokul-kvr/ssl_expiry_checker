# check_ssl_expiry.py

import ssl
import socket
from datetime import datetime, timezone, date
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from send_email_util import send_email
import time
import pytz
import os


DOMAINS = os.getenv("DOMAINS", "").split(",") if os.getenv("DOMAINS") else []
THRESHOLD_DAYS = 15

RECIPIENTS = os.getenv("EMAIL_TO", "").split(",")

def status_priority(status):
    if status == "ERROR":
        return 1
    if "Expired" in status:
        return 2
    if "Expires today" in status:
        return 3
    if "Expires tomorrow" in status:
        return 4
    if "Expires in" in status:
        try:
            days = int(status.split()[2])
            if days <= 15:
                return 5
            elif days <= 30:
                return 6
            else:
                return 7
        except:
            return 99
    return 99  # Unknown/uncategorized

def sort_results(results):
    return sorted(results, key=lambda x: status_priority(x[1]))

def get_ssl_expiry_status(domain, port=443):
    try:
        context = ssl._create_unverified_context()
        with context.wrap_socket(socket.socket(), server_hostname=domain) as conn:
            conn.settimeout(5)
            conn.connect((domain, port))

            # Try default way first
            cert = conn.getpeercert()
            if cert and 'notAfter' in cert:
                expiry_str = cert['notAfter']
                expiry_date = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            else:
                # Fallback: manually extract from DER
                der_cert = conn.getpeercert(binary_form=True)
                x509_cert = x509.load_der_x509_certificate(der_cert, default_backend())
                expiry_date = x509_cert.not_valid_after_utc

            now = datetime.now(timezone.utc)
            delta_days = (expiry_date - now).days

            expiry_str = expiry_date.strftime("%d-%b-%Y")

            if delta_days > 1:
                return f"Expires in {delta_days} days", expiry_date.date()
            elif delta_days == 1:
                return "Expires tomorrow", expiry_date.date()
            elif delta_days == 0:
                return "Expires today", expiry_date.date()
            else:
                return f"Expired {-delta_days} days ago", expiry_date.date()

    except ssl.SSLError as e:
        return "ERROR", str(e)
    except socket.timeout:
        return "ERROR", "Connection timed out"
    except Exception as e:
        return "ERROR", str(e)

def build_html_report(status_list):
    def format_date(info):
        return info.strftime("%d-%b-%Y") if isinstance(info, date) else str(info)

    def render_table(title, rows):
        if not rows:
            return ""

        html = f"""
        <h4>{title}</h4>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; font-family: Arial, sans-serif; width: 100%; margin-bottom: 30px;">
            <thead>
                <tr style="background-color: #333; color: #fff;">
                    <th>Domain</th>
                    <th>Status</th>
                    <th>Expiry Date</th>
                </tr>
            </thead>
            <tbody>
        """
        for domain, status, info in rows:
            formatted_info = format_date(info)

            if status == "ERROR":
                row_color = "#ffcccc"
                text_color = "red"
            elif "Expired" in status:
                row_color = "#ffe6e6"
                text_color = "red"
            elif "Expires today" in status or "Expires tomorrow" in status or ("Expires in" in status and int(status.split()[2]) <= 15):
                row_color = "#fff4e6"
                text_color = "#cc6600"
            elif "Expires in" in status and int(status.split()[2]) <= 30:
                row_color = "#ffffcc"
                text_color = "#999900"
            else:
                row_color = "#e6ffcc"
                text_color = "green"

            html += f"""
                <tr style="background-color: {row_color}; color: {text_color};">
                    <td><strong>{domain}</strong></td>
                    <td>{status}</td>
                    <td><code>{formatted_info}</code></td>
                </tr>
            """
        html += "</tbody></table>"
        return html

    # Split into categories
    expired = []
    expiring_soon = []
    safe = []
    error = []

    for item in status_list:
        domain, status, info = item
        if status == "ERROR":
            error.append(item)
        elif "Expired" in status:
            expired.append(item)
        elif "Expires today" in status or "Expires tomorrow" in status or ("Expires in" in status and int(status.split()[2]) <= 15):
            expiring_soon.append(item)
        elif "Expires in" in status:
            safe.append(item)

    # Build full HTML
    html = "<h3>⚠️ SSL Certificate Expiry Report</h3>"
    html += render_table("🔴 Expired Certificates", expired)
    html += render_table("🟠 Expiring Soon (0–15 days)", expiring_soon)
    html += render_table("🟢 Safe (More than 15 days)", safe)
    html += render_table("❌ Errors / Could Not Check", error)

    return html


def main():
    results = []
    for domain in DOMAINS:
        print(f"Checking {domain}...")
        status, info = get_ssl_expiry_status(domain)
        if status == "ERROR":
            print(f"{domain}: {status} ({info})")
        elif info == datetime.now(timezone.utc).date():
            print(f"{domain}: {status} (today)")
        else:
            print(f"{domain}: {status} ({info.strftime('%b %d, %Y')})")
        results.append((domain, status, info))

    sorted_results = sort_results(results)
    html_body = build_html_report(sorted_results)
    subject = "🔔 SSL Certificate Expiry Report"
    send_email(subject, html_body, RECIPIENTS)

def run():
    IST = pytz.timezone('Asia/Kolkata')
    weekday = int(os.getenv("WEEKDAY", 5))  # Default to Monday
    check_hour = int(os.getenv("CHECK_HOUR", 9))  # Default to 3 PM
    check_minute = int(os.getenv("CHECK_MINUTE", 30))  # Default
    while True:
        now_ist = datetime.now(IST)
        if now_ist.weekday() == weekday and now_ist.hour == check_hour and now_ist.minute == check_minute:
            print("🟢 Triggering SSL check now...")
            main()
            # Sleep for 61 seconds to avoid re-triggering during the same minute
            time.sleep(61)
        else:
            # Sleep for 30 seconds to not hog the CPU
            time.sleep(30)

if __name__ == "__main__":
    # run()
    main()
