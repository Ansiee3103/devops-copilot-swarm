import os
import smtplib
import json
import requests
from email.mime.text     import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime            import datetime, timezone, timedelta
from dotenv              import load_dotenv

load_dotenv()

IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_time() -> str:
    return datetime.now(IST).strftime('%d %b %Y %I:%M:%S %p IST')

# ── Email Alert ───────────────────────────────────────────

def send_email_alert(
    service_name:   str,
    status:         str,
    risk_score:     float,
    healing_report: str,
    affected:       list
) -> dict:
    """Send email alert to team"""

    sender   = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver = os.getenv("EMAIL_RECEIVER")

    if not all([sender, password, receiver]):
        print("⚠️ Email not configured — skipping")
        return {"success": False, "reason": "not configured"}

    try:
        # Build email content
        status_icon = "✅" if status == "healed" else "❌"
        risk_color  = "#f85149" if risk_score >= 7 else \
                      "#d29922" if risk_score >= 4 else "#3fb950"

        html = f"""
        <html><body style="font-family:Arial,sans-serif;
                           background:#0d1117; color:#e6edf3;
                           padding:20px;">

          <div style="max-width:600px; margin:auto;
                      background:#161b22; border-radius:12px;
                      border:1px solid #30363d; padding:30px;">

            <h2 style="color:#58a6ff; margin-bottom:5px">
              🚀 DevOps Copilot Swarm Alert
            </h2>
            <p style="color:#8b949e; font-size:13px">
              {get_ist_time()}
            </p>

            <hr style="border-color:#30363d; margin:20px 0"/>

            <h3>{status_icon} {service_name} — {status.upper()}</h3>

            <table style="width:100%; margin:15px 0">
              <tr>
                <td style="color:#8b949e; padding:8px 0">
                  Risk Score
                </td>
                <td>
                  <span style="background:{risk_color}33;
                               color:{risk_color};
                               padding:3px 10px;
                               border-radius:20px;
                               font-weight:bold">
                    {risk_score}/10
                  </span>
                </td>
              </tr>
              <tr>
                <td style="color:#8b949e; padding:8px 0">
                  Affected Services
                </td>
                <td>{', '.join(affected) if affected else 'None'}</td>
              </tr>
              <tr>
                <td style="color:#8b949e; padding:8px 0">Status</td>
                <td>{status}</td>
              </tr>
            </table>

            <hr style="border-color:#30363d; margin:20px 0"/>

            <h4 style="color:#58a6ff">🔧 AutoHealer Report</h4>
            <div style="background:#0d1117; border-radius:8px;
                        padding:15px; font-size:13px;
                        color:#8b949e; line-height:1.8">
              {healing_report[:500].replace(chr(10), '<br>') if healing_report else 'No healing required'}
            </div>

            <hr style="border-color:#30363d; margin:20px 0"/>

            <p style="color:#8b949e; font-size:12px; text-align:center">
              DevOps Copilot Swarm — Autonomous Deployment System
            </p>
          </div>
        </body></html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[DevOps Swarm] {status_icon} {service_name} — {status.upper()}"
        msg["From"]    = sender
        msg["To"]      = receiver
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())

        print(f"✅ Email alert sent to {receiver}")
        return {"success": True, "receiver": receiver}

    except Exception as e:
        print(f"❌ Email failed: {e}")
        return {"success": False, "error": str(e)}

# ── Slack Alert ───────────────────────────────────────────

def send_slack_alert(
    service_name:   str,
    status:         str,
    risk_score:     float,
    healing_report: str,
    affected:       list
) -> dict:
    """Send Slack alert to channel"""

    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not webhook_url:
        print("⚠️ Slack not configured — skipping")
        return {"success": False, "reason": "not configured"}

    try:
        status_icon  = "✅" if status == "healed" else "❌"
        risk_emoji   = "🔴" if risk_score >= 7 else \
                       "🟡" if risk_score >= 4 else "🟢"

        # Build Slack block message
        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚀 DevOps Copilot Swarm Alert"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Service:*\n{service_name}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Status:*\n{status_icon} {status.upper()}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Risk Score:*\n{risk_emoji} {risk_score}/10"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Affected Services:*\n{', '.join(affected) if affected else 'None'}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Time:*\n{get_ist_time()}"
                        }
                    ]
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🔧 AutoHealer Report:*\n```{healing_report[:300] if healing_report else 'No healing required'}```"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "DevOps Copilot Swarm — Risk-Aware Deployment & Self-Healing"
                        }
                    ]
                }
            ]
        }

        response = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 200:
            print("✅ Slack alert sent!")
            return {"success": True}
        else:
            print(f"❌ Slack failed: {response.text}")
            return {"success": False, "error": response.text}

    except Exception as e:
        print(f"❌ Slack failed: {e}")
        return {"success": False, "error": str(e)}

# ── Send Both ─────────────────────────────────────────────

def send_all_alerts(
    service_name:   str,
    status:         str,
    risk_score:     float,
    healing_report: str,
    affected:       list
) -> dict:
    """Send both email and slack alerts"""

    print("\n📣 Sending alerts...")

    email_result = send_email_alert(
        service_name, status,
        risk_score, healing_report, affected
    )
    slack_result = send_slack_alert(
        service_name, status,
        risk_score, healing_report, affected
    )

    return {
        "email": email_result,
        "slack": slack_result
    }
