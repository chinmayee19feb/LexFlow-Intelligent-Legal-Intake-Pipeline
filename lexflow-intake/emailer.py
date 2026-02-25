import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Urgency badge colors for attorney alert HTML
URGENCY_COLORS = {
    "critical": "#DC2626",  # red
    "high":     "#EA580C",  # orange
    "medium":   "#D97706",  # amber
    "low":      "#16A34A",  # green
}

URGENCY_LABELS = {
    "critical": "🔴 CRITICAL",
    "high":     "🟠 HIGH",
    "medium":   "🟡 MEDIUM",
    "low":      "🟢 LOW",
}


def _ses_client(region: str = "us-east-1"):
    return boto3.client("ses", region_name=region)


def send_client_ack(
    to_email: str,
    client_name: str,
    case_type: str,
    acknowledgment_text: str,
    from_email: str,
    region: str = "us-east-1",
) -> None:
    """
    Send a plain-text acknowledgment email to the client.
    Plain text feels more personal than HTML.
    """
    subject = f"We received your inquiry — {case_type}"

    body = (
        f"{acknowledgment_text}\n\n"
        "---\n"
        "This message was sent automatically upon receipt of your inquiry.\n"
        "Please do not reply to this email.\n"
        "If you need immediate assistance, please call our office directly."
    )

    try:
        _ses_client(region).send_email(
            Source=from_email,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        logger.info("Client ack email sent | to=%s", to_email)
    except ClientError as e:
        # Log but never fail the intake request over an email error
        logger.error(
            "Client ack email FAILED | to=%s | error=%s",
            to_email,
            e.response["Error"]["Message"],
        )


def send_attorney_alert(
    to_email: str,
    record: dict,
    from_email: str,
    region: str = "us-east-1",
) -> None:
    """
    Send an HTML-formatted attorney alert with the full intake record.
    Urgency is color-coded. Viability score is prominent.
    """
    urgency = record.get("urgency", "medium")
    urgency_color = URGENCY_COLORS.get(urgency, "#6B7280")
    urgency_label = URGENCY_LABELS.get(urgency, urgency.upper())
    case_type = record.get("case_type", "Unknown")
    viability = record.get("viability_score", 0)
    intake_id = record.get("intake_id", "N/A")

    subject = f"[{urgency_label}] New intake — {case_type} — Score {viability}/10"

    key_facts_html = "".join(
        f"<li style='margin-bottom:6px'>{fact}</li>"
        for fact in record.get("key_facts", [])
    )

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 680px; margin: 0 auto; padding: 20px; color: #1F2937;">

  <!-- Header bar -->
  <div style="background-color: {urgency_color}; color: white; padding: 16px 20px; border-radius: 8px 8px 0 0;">
    <h1 style="margin:0; font-size:18px;">⚖️ LexFlow — New Intake Alert</h1>
    <p style="margin:4px 0 0; font-size:14px; opacity:0.9;">Urgency: {urgency_label} &nbsp;|&nbsp; Intake ID: {intake_id}</p>
  </div>

  <!-- Viability score -->
  <div style="background-color: #F9FAFB; border: 1px solid #E5E7EB; border-top: none; padding: 16px 20px; display:flex; align-items:center;">
    <div style="font-size:48px; font-weight:bold; color:{urgency_color}; margin-right:20px;">{viability}<span style="font-size:24px; color:#9CA3AF;">/10</span></div>
    <div>
      <div style="font-size:13px; color:#6B7280; text-transform:uppercase; letter-spacing:0.05em;">Viability Score</div>
      <div style="font-size:18px; font-weight:600; color:#111827;">{case_type}</div>
      <div style="font-size:14px; color:#6B7280;">Recommended specialty: {record.get('recommended_specialty', 'N/A')}</div>
    </div>
  </div>

  <!-- Client details -->
  <table style="width:100%; border-collapse:collapse; border:1px solid #E5E7EB; border-top:none;">
    <tr style="background-color:#F3F4F6;">
      <th style="text-align:left; padding:10px 16px; font-size:13px; color:#374151; width:35%;">Field</th>
      <th style="text-align:left; padding:10px 16px; font-size:13px; color:#374151;">Value</th>
    </tr>
    <tr>
      <td style="padding:10px 16px; border-top:1px solid #E5E7EB; font-size:14px; color:#6B7280;">Client Name</td>
      <td style="padding:10px 16px; border-top:1px solid #E5E7EB; font-size:14px; font-weight:600;">{record.get('client_name', 'N/A')}</td>
    </tr>
    <tr style="background-color:#F9FAFB;">
      <td style="padding:10px 16px; border-top:1px solid #E5E7EB; font-size:14px; color:#6B7280;">Email</td>
      <td style="padding:10px 16px; border-top:1px solid #E5E7EB; font-size:14px;"><a href="mailto:{record.get('client_email','')}" style="color:#2563EB;">{record.get('client_email', 'N/A')}</a></td>
    </tr>
    <tr>
      <td style="padding:10px 16px; border-top:1px solid #E5E7EB; font-size:14px; color:#6B7280;">Phone</td>
      <td style="padding:10px 16px; border-top:1px solid #E5E7EB; font-size:14px;">{record.get('client_phone', 'N/A')}</td>
    </tr>
    <tr style="background-color:#F9FAFB;">
      <td style="padding:10px 16px; border-top:1px solid #E5E7EB; font-size:14px; color:#6B7280;">Incident Date</td>
      <td style="padding:10px 16px; border-top:1px solid #E5E7EB; font-size:14px;">{record.get('incident_date', 'N/A')}</td>
    </tr>
    <tr>
      <td style="padding:10px 16px; border-top:1px solid #E5E7EB; font-size:14px; color:#6B7280;">Prior Attorney</td>
      <td style="padding:10px 16px; border-top:1px solid #E5E7EB; font-size:14px;">{"Yes" if record.get('prior_attorney') else "No"}</td>
    </tr>
    <tr style="background-color:#F9FAFB;">
      <td style="padding:10px 16px; border-top:1px solid #E5E7EB; font-size:14px; color:#6B7280;">Statute of Limitations</td>
      <td style="padding:10px 16px; border-top:1px solid #E5E7EB; font-size:14px;">
        {"⚠️ <strong style='color:#DC2626;'>FLAG — May be a concern</strong>" if record.get('statute_of_limitations_flag') else "✅ No immediate concern"}
      </td>
    </tr>
  </table>

  <!-- Key facts -->
  <div style="border:1px solid #E5E7EB; border-top:none; padding:16px 20px;">
    <h3 style="margin:0 0 10px; font-size:14px; text-transform:uppercase; letter-spacing:0.05em; color:#374151;">Key Facts</h3>
    <ul style="margin:0; padding-left:20px; font-size:14px; color:#1F2937;">
      {key_facts_html}
    </ul>
  </div>

  <!-- Recommended action -->
  <div style="border:1px solid #E5E7EB; border-top:none; padding:16px 20px; background-color:#EFF6FF;">
    <h3 style="margin:0 0 6px; font-size:14px; text-transform:uppercase; letter-spacing:0.05em; color:#1E40AF;">Recommended Action</h3>
    <p style="margin:0; font-size:15px; font-weight:600; color:#1E3A8A;">{record.get('recommended_action', 'N/A')}</p>
  </div>

  <!-- Raw description -->
  <div style="border:1px solid #E5E7EB; border-top:none; padding:16px 20px; border-radius:0 0 8px 8px;">
    <h3 style="margin:0 0 8px; font-size:14px; text-transform:uppercase; letter-spacing:0.05em; color:#374151;">Client's Description</h3>
    <p style="margin:0; font-size:14px; color:#4B5563; line-height:1.6; font-style:italic;">"{record.get('raw_description', 'N/A')}"</p>
  </div>

  <p style="margin-top:20px; font-size:12px; color:#9CA3AF; text-align:center;">
    LexFlow Intake System &nbsp;|&nbsp; {record.get('timestamp', '')} &nbsp;|&nbsp; {record.get('ai_model_used', '')}
  </p>

</body>
</html>"""

    try:
        _ses_client(region).send_email(
            Source=from_email,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
            },
        )
        logger.info("Attorney alert email sent | to=%s | intake_id=%s", to_email, intake_id)
    except ClientError as e:
        logger.error(
            "Attorney alert email FAILED | to=%s | intake_id=%s | error=%s",
            to_email,
            intake_id,
            e.response["Error"]["Message"],
        )
