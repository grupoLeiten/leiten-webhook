"""
Test endpoint — sends a test email via Resend and shows the full result.
Visit /api/test-email in the browser to trigger.
"""

import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
TEST_TO_EMAIL = "jose.poletto@sinis.com.ar"


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        result = {"step": "start", "resend_key_present": bool(RESEND_API_KEY)}

        if not RESEND_API_KEY:
            result["error"] = "RESEND_API_KEY is empty"
            self._respond(200, result)
            return

        from_address = "Leiten IT <onboarding@resend.dev>"
        payload = json.dumps({
            "from": from_address,
            "to": [TEST_TO_EMAIL],
            "subject": "Test directo desde Vercel",
            "html": "<h1>Hola!</h1><p>Este es un email de prueba enviado directamente desde el endpoint /api/test-email.</p>",
        }).encode()

        result["payload"] = {
            "from": from_address,
            "to": TEST_TO_EMAIL,
            "subject": "Test directo desde Vercel",
        }

        try:
            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=payload,
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                body = resp.read().decode()
                result["resend_status"] = status
                result["resend_response"] = json.loads(body)
                result["success"] = True
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode()
            except Exception:
                error_body = "could not read"
            result["resend_status"] = e.code
            result["resend_error"] = error_body
            result["success"] = False
        except Exception as e:
            result["exception"] = f"{type(e).__name__}: {str(e)}"
            result["success"] = False

        self._respond(200, result)

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
