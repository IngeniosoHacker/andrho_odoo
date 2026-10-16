"""Entry from AndRho's dashboard, without an Odoo login.

andrho-api signs a short-lived token with this database's secret
(ir.config_parameter ``andrho.sso_secret``, written by the VPS script and
kept, sealed, by the API):

    base64url(json payload) + "." + base64url(HMAC-SHA256(secret, payload part))

payload: {"login": email, "name": ..., "role": owner|admin|member|...,
          "aud": database name, "exp": unix seconds, "jti": random id}

/andrho/sso checks it, burns the jti (a token works once), finds or creates
the AndRho user here and opens a session with credential type
``andrho_sso`` (res_users._check_credentials verifies the token again).
"""
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessDenied

SECRET_PARAM = "andrho.sso_secret"
DASHBOARD_PARAM = "andrho.dashboard_url"
MAX_TTL = 300  # seconds; the API issues tokens for 60


def _b64decode(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def verify_token(env, token):
    """Returns the token's payload, or raises AccessDenied."""
    secret = env["ir.config_parameter"].sudo().get_param(SECRET_PARAM)
    if not secret or not isinstance(token, str) or token.count(".") != 1:
        raise AccessDenied()
    body, sig = token.split(".")
    expected = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    if not hmac.compare_digest(expected, sig):
        raise AccessDenied()
    try:
        data = json.loads(_b64decode(body))
    except ValueError:
        raise AccessDenied() from None
    now = time.time()
    exp = data.get("exp")
    if (
        not isinstance(data, dict)
        or not isinstance(exp, (int, float))
        or not now < exp <= now + MAX_TTL
        or data.get("aud") != env.cr.dbname
        or not data.get("login")
        or not data.get("jti")
    ):
        raise AccessDenied()
    data["login"] = str(data["login"]).strip().lower()
    return data


class AndrhoSsoJti(models.Model):
    """Tokens already used: each one opens a session once."""

    _name = "andrho.sso.jti"
    _description = "AndRho SSO token used"

    jti = fields.Char(required=True, index=True)

    _jti_unique = models.Constraint("UNIQUE(jti)", "This token was already used.")

    @api.model
    def burn(self, jti):
        """Records jti; raises AccessDenied when it was already used."""
        self.sudo().search([("create_date", "<", datetime.now() - timedelta(days=1))]).unlink()
        if self.sudo().search_count([("jti", "=", jti)]):
            raise AccessDenied()
        self.sudo().create({"jti": jti})
