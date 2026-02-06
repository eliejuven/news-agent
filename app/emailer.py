from __future__ import annotations

import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from typing import List, Optional, Any

def _extract_what_to_remember(brief: str) -> str:
    """
    Extracts only the WHAT TO REMEMBER section from the brief text.
    """
    lines = brief.splitlines()
    out = []
    keep = False

    for ln in lines:
        if ln.strip().upper() == "WHAT TO REMEMBER":
            keep = True
            out.append("WHAT TO REMEMBER")
            continue
        if keep:
            # Stop if another section starts (future-proof)
            if ln.strip().isupper() and not ln.strip().startswith("-"):
                break
            out.append(ln)

    return "\n".join(out).strip()


def _brief_to_html(brief: str) -> str:
    lines = [ln.strip() for ln in brief.splitlines() if ln.strip()]
    html_parts = []
    in_ul = False

    def close_ul():
        nonlocal in_ul
        if in_ul:
            html_parts.append("</ul>")
            in_ul = False

    for ln in lines:
        if ln.upper() == "WHAT TO REMEMBER":
          close_ul()
          html_parts.append("<h3 style='margin:14px 0 6px 0;'>What to remember</h3>")
          continue

        if ln.startswith("- "):
            if not in_ul:
                html_parts.append("<ul style='margin:6px 0 12px 18px; padding:0;'>")
                in_ul = True
            item = ln[2:].strip()
            html_parts.append(f"<li style='margin:6px 0; color:#222;'>{item}</li>")
        else:
            close_ul()
            html_parts.append(f"<div style='margin:6px 0; color:#444;'>{ln}</div>")

    close_ul()
    return "\n".join(html_parts)

def render_html(top10: List[Any], brief: Optional[str] = None) -> str:
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
                  {_brief_to_html(_extract_what_to_remember(brief)) if brief else ""}
        <hr style="border:none;border-top:1px solid #eee;margin:16px 0;" />
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

    recipients = [e.strip() for e in settings.EMAIL_TO.split(",") if e.strip()]

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM, recipients, msg.as_string())