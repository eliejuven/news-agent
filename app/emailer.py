from __future__ import annotations

import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from app.config import settings
from app.rank import RankedItem


def render_html(top10: List[RankedItem]) -> str:
    items = []
    for i, it in enumerate(top10, 1):
        items.append(
            f"""
            <div style="margin: 0 0 14px 0; padding: 10px; border: 1px solid #eee; border-radius: 8px;">
              <div style="font-size: 15px; font-weight: 700;">
                {i:02d}. [{it.country}] {it.title}
              </div>
              <div style="color: #555; font-size: 13px; margin-top: 4px;">
                {it.source} • score {it.score:.2f}
              </div>
              <div style="margin-top: 6px;">
                <a href="{it.url}">{it.url}</a>
              </div>
            </div>
            """
        )

    return f"""
    <html>
      <body style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Arial;">
        <h2 style="margin-bottom: 6px;">Top 10 must-reads — {date.today().isoformat()}</h2>
        <div style="color:#666; margin-bottom: 16px;">
          Mostly English digest (US=5, UK=4, FR=1)
        </div>
        {''.join(items)}
      </body>
    </html>
    """


def send_email(subject: str, html: str) -> None:
    if not settings.EMAIL_TO or not settings.EMAIL_FROM:
        raise ValueError("EMAIL_TO / EMAIL_FROM missing in .env")
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise ValueError("SMTP_USER / SMTP_PASSWORD missing in .env")

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = settings.EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM, [settings.EMAIL_TO], msg.as_string())