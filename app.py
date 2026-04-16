"""
leiten-webhook
Webhook receiver for GitHub Pull Request events.
Sends an email notification to the PR author before merge.
"""

import os
import hmac
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, abort

app = Flask(__name__)

# -- Config from environment variables --
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", SMTP_USER)


def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify the GitHub webhook signature (HMAC SHA-256)."""
    if not WEBHOOK_SECRET:
        return True  # Skip verification if no secret is configured (dev only)
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def send_email(to_email: str, subject: str, body_html: str) -> bool:
    """Send an email via SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        app.logger.warning("SMTP credentials not configured - skipping email.")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, to_email, msg.as_string())
        app.logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        app.logger.error(f"Failed to send email: {e}")
        return False


def build_pr_email(action: str, pr: dict, repo: dict, sender: dict) -> tuple[str, str]:
    """Build subject and HTML body for a PR notification."""
    pr_title = pr.get("title", "Sin titulo")
    pr_number = pr.get("number", "?")
    pr_url = pr.get("html_url", "#")
    repo_name = repo.get("full_name", "unknown")
    base_branch = pr.get("base", {}).get("ref", "main")
    head_branch = pr.get("head", {}).get("ref", "?")
    author = sender.get("login", "alguien")

    action_map = {
        "opened": "se abrio",
        "reopened": "se reabrio",
        "synchronize": "se actualizo",
        "ready_for_review": "esta listo para revision",
    }
    action_text = action_map.get(action, action)

    subject = f"[{repo_name}] PR #{pr_number} {action_text}: {pr_title}"

    body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1a1a2e; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">Notificacion de Pull Request</h2>
            <p style="margin: 5px 0 0; opacity: 0.8;">{repo_name}</p>
        </div>
        <div style="border: 1px solid #e0e0e0; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
            <p>Hola <strong>{author}</strong>,</p>
            <p>Tu Pull Request <strong>#{pr_number}</strong> {action_text}.</p>
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; color: #666;">Titulo</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>{pr_title}</strong></td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; color: #666;">Rama</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;"><code>{head_branch}</code> -&gt; <code>{base_branch}</code></td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; color: #666;">Estado</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{action_text.capitalize()}</td>
                </tr>
            </table>
            <p>
                <a href="{pr_url}"
                   style="display: inline-block; background: #0366d6; color: white;
                          padding: 10px 20px; border-radius: 5px; text-decoration: none;">
                    Ver Pull Request en GitHub
                </a>
            </p>
            <p style="color: #999; font-size: 12px; margin-top: 20px;">
                Recorda que este PR aun no fue mergeado. Revisa los cambios antes de aprobar.
            </p>
        </div>
    </div>
    """
    return subject, body


@app.route("/webhook", methods=["POST"])
def github_webhook():
    """Receive GitHub webhook events."""
    # 1. Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(request.data, signature):
        abort(403, "Invalid signature")

    # 2. Check event type
    event = request.headers.get("X-GitHub-Event", "")
    if event == "ping":
        return jsonify({"message": "pong"}), 200

    if event != "pull_request":
        return jsonify({"message": f"Event '{event}' ignored"}), 200

    # 3. Parse payload
    payload = request.json
    action = payload.get("action", "")
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    sender = payload.get("sender", {})

    # Only notify on meaningful actions (opened, reopened, ready_for_review)
    notify_actions = {"opened", "reopened", "ready_for_review"}
    if action not in notify_actions:
        return jsonify({"message": f"Action '{action}' ignored"}), 200

    # 4. Get author email from the PR commits
    author_email = (
        pr.get("head", {}).get("user", {}).get("email")
        or pr.get("user", {}).get("email")
        or payload.get("sender", {}).get("email")
    )

    if not author_email:
        app.logger.warning(
            f"No email found for PR #{pr.get('number')} author "
            f"({sender.get('login')}). Cannot send notification."
        )
        return jsonify({
            "message": "No author email available",
            "hint": "The user's GitHub email may be private. "
                    "Consider using the GitHub API to fetch it.",
        }), 200

    # 5. Build and send email
    subject, body = build_pr_email(action, pr, repo, sender)
    sent = send_email(author_email, subject, body)

    return jsonify({
        "message": "Notification sent" if sent else "Email skipped (check config)",
        "pr": pr.get("number"),
        "author": sender.get("login"),
    }), 200


@app.route("/health", methods=["GET"])
def health():
    """Simple health-check endpoint."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", False))
