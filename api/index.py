"""
leiten-webhook — Vercel Serverless Function
Webhook receiver for GitHub Pull Request events.
Sends an email notification to the PR author before merge.
"""

import os
import hmac
import hashlib
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
import json


# -- Config from environment variables --
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
USER_AGENT = "leiten-webhook/1.0"


def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify the GitHub webhook signature (HMAC SHA-256)."""
    if not WEBHOOK_SECRET:
        return True
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def send_email(to_email: str, subject: str, body_html: str) -> dict:
    """Send an email via Resend API. Returns dict with status details."""
    if not RESEND_API_KEY:
        return {"ok": False, "error": "RESEND_API_KEY not configured"}

    from_address = "Leiten IT <onboarding@resend.dev>"

    payload = json.dumps({
        "from": from_address,
        "to": [to_email],
        "subject": subject,
        "html": body_html,
    }).encode()

    try:
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            return {"ok": True, "resend_id": result.get("id"), "to": to_email, "from": from_address}
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()
        except Exception:
            error_body = "could not read error body"
        return {"ok": False, "error": f"HTTP {e.code}", "detail": error_body, "to": to_email, "from": from_address}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)}", "to": to_email, "from": from_address}


def get_author_email(pr: dict, repo: dict, sender: dict) -> dict:
    """Try to get author email from multiple sources. Returns dict with email and source."""
    author_email = (
        pr.get("head", {}).get("user", {}).get("email")
        or pr.get("user", {}).get("email")
        or sender.get("email")
    )
    if author_email:
        return {"email": author_email, "source": "webhook_payload"}

    if not GITHUB_TOKEN:
        return {"email": None, "source": "no_github_token"}

    # Try PR commits API
    try:
        repo_full = repo.get("full_name", "")
        pr_number = pr.get("number", "")
        api_url = f"https://api.github.com/repos/{repo_full}/pulls/{pr_number}/commits"
        req = urllib.request.Request(api_url, headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": USER_AGENT,
        })
        with urllib.request.urlopen(req) as resp:
            commits = json.loads(resp.read())
            if commits:
                email = commits[-1].get("commit", {}).get("author", {}).get("email", "")
                if email and "noreply" not in email:
                    return {"email": email, "source": "commits_api"}
    except Exception:
        pass

    # Try user profile API
    try:
        username = sender.get("login", "")
        api_url = f"https://api.github.com/users/{username}"
        req = urllib.request.Request(api_url, headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": USER_AGENT,
        })
        with urllib.request.urlopen(req) as resp:
            user_data = json.loads(resp.read())
            email = user_data.get("email", "")
            if email:
                return {"email": email, "source": "user_profile_api"}
    except Exception:
        pass

    return {"email": None, "source": "all_methods_failed"}


def build_pr_email(action: str, pr: dict, repo: dict, sender: dict) -> tuple:
    """Build subject and HTML body for a PR notification."""
    pr_title = pr.get("title", "Sin titulo")
    pr_number = pr.get("number", "?")
    pr_url = pr.get("html_url", "#")
    repo_name = repo.get("full_name", "unknown")
    base_branch = pr.get("base", {}).get("ref", "main")
    head_branch = pr.get("head", {}).get("ref", "?")
    author = sender.get("login", "alguien")

    subject = "Tus cambios se enviaron correctamente"

    body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 560px; margin: 0 auto; background: #ffffff;">

        <div style="background: #0f172a; padding: 32px 28px; border-radius: 12px 12px 0 0; text-align: center;">
            <div style="font-size: 40px; margin-bottom: 8px;">&#9989;</div>
            <h1 style="margin: 0; color: #ffffff; font-size: 22px; font-weight: 600;">
                Tus cambios se enviaron correctamente
            </h1>
        </div>

        <div style="border: 1px solid #e2e8f0; border-top: none; padding: 28px; border-radius: 0 0 12px 12px;">

            <p style="color: #334155; font-size: 15px; line-height: 1.6; margin-top: 0;">
                Hola <strong>{author}</strong>, tus cambios fueron enviados y estan
                <strong>pendientes de revision</strong> antes de pasar a produccion.
            </p>

            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 20px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 6px 0; color: #64748b; font-size: 13px; width: 100px;">Proyecto</td>
                        <td style="padding: 6px 0; color: #1e293b; font-size: 13px; font-weight: 600;">{repo_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #64748b; font-size: 13px;">PR</td>
                        <td style="padding: 6px 0; color: #1e293b; font-size: 13px; font-weight: 600;">#{pr_number} &mdash; {pr_title}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #64748b; font-size: 13px;">Rama</td>
                        <td style="padding: 6px 0; color: #1e293b; font-size: 13px;"><code style="background: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-size: 12px;">{head_branch}</code> &rarr; <code style="background: #e2e8f0; padding: 2px 6px; border-radius: 4px; font-size: 12px;">{base_branch}</code></td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #64748b; font-size: 13px;">Estado</td>
                        <td style="padding: 6px 0; font-size: 13px;">
                            <span style="background: #fef3c7; color: #92400e; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">Pendiente de revision</span>
                        </td>
                    </tr>
                </table>
            </div>

            <div style="text-align: center; margin: 24px 0;">
                <a href="{pr_url}"
                   style="display: inline-block; background: #0f172a; color: #ffffff;
                          padding: 12px 28px; border-radius: 8px; text-decoration: none;
                          font-size: 14px; font-weight: 600;">
                    Ver Pull Request
                </a>
            </div>

            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">

            <p style="color: #94a3b8; font-size: 12px; line-height: 1.5; margin: 0; text-align: center;">
                Cualquier duda, comunicarse con el sector de <strong>Ingenieria IT</strong>.
            </p>
        </div>
    </div>
    """
    return subject, body


class handler(BaseHTTPRequestHandler):
    """Vercel serverless handler for GitHub webhooks."""

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_GET(self):
        """Health check."""
        self._send_json(200, {
            "status": "ok",
            "service": "leiten-webhook",
            "config": {
                "resend_api_key": "configured" if RESEND_API_KEY else "MISSING",
                "github_token": "configured" if GITHUB_TOKEN else "MISSING",
                "webhook_secret": "configured" if WEBHOOK_SECRET else "MISSING",
            }
        })

    def do_POST(self):
        """Handle GitHub webhook POST requests."""
        debug = {}

        # 1. Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # 2. Verify signature
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(body, signature):
            self._send_json(403, {"error": "Invalid signature"})
            return

        # 3. Check event type
        event = self.headers.get("X-GitHub-Event", "")
        debug["event"] = event

        if event == "ping":
            self._send_json(200, {"message": "pong"})
            return

        if event != "pull_request":
            self._send_json(200, {"message": f"Event '{event}' ignored"})
            return

        # 4. Parse payload
        payload = json.loads(body)
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        sender = payload.get("sender", {})

        debug["action"] = action
        debug["sender"] = sender.get("login")
        debug["pr_number"] = pr.get("number")

        # Only notify on meaningful actions
        notify_actions = {"opened", "reopened", "ready_for_review"}
        if action not in notify_actions:
            self._send_json(200, {"message": f"Action '{action}' ignored", "debug": debug})
            return

        # 5. Get author email
        email_result = get_author_email(pr, repo, sender)
        debug["email_lookup"] = email_result

        author_email = email_result.get("email")
        if not author_email:
            self._send_json(200, {
                "message": "No author email available",
                "debug": debug,
            })
            return

        # 6. Build and send email
        subject, email_body = build_pr_email(action, pr, repo, sender)
        email_result = send_email(author_email, subject, email_body)
        debug["email_send"] = email_result

        self._send_json(200, {
            "message": "Email sent!" if email_result.get("ok") else "Email FAILED",
            "debug": debug,
        })
