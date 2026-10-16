import logging

from odoo import http
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.session import Session
from odoo.exceptions import AccessDenied
from odoo.http import request

from ..models.sso import DASHBOARD_PARAM, verify_token

_logger = logging.getLogger(__name__)


# Everyone lands on Inventario's overview, every account's base.
HOME = "/odoo/action-stock.stock_picking_type_action"


def _dashboard_url():
    return request.env["ir.config_parameter"].sudo().get_param(DASHBOARD_PARAM) or ""


class AndrhoSso(http.Controller):
    @http.route("/andrho/sso", type="http", auth="public", methods=["GET"], readonly=False, sitemap=False)
    def sso(self, t=None, **kw):
        """The dashboard's ERP button lands here with a token from andrho-api."""
        try:
            data = verify_token(request.env, t)
            request.env["andrho.sso.jti"].burn(data["jti"])
            user = request.env["res.users"]._andrho_user(data["login"], data.get("name"), data.get("role"))
            request.session.authenticate(request.env, {"type": "andrho_sso", "login": user.login, "token": t})
        except AccessDenied:
            _logger.info("andrho_core: rejected SSO token")
            back = _dashboard_url()
            return request.redirect(back, local=False) if back else request.not_found()
        return request.redirect(HOME)


class AndrhoHome(Home):
    @http.route()
    def web_login(self, redirect=None, **kw):
        # Nobody signs in here: people enter from AndRho's dashboard.
        # ?local=1 keeps Odoo's form for AndRho's own support.
        dashboard = _dashboard_url()
        if request.httprequest.method == "GET" and dashboard and not kw.get("local") and not request.session.uid:
            return request.redirect(dashboard, local=False)
        return super().web_login(redirect=redirect, **kw)


class AndrhoSession(Session):
    @http.route()
    def logout(self, redirect="/odoo"):
        dashboard = _dashboard_url()
        if not dashboard or redirect != "/odoo":
            return super().logout(redirect=redirect)
        request.session.logout(keep_db=True)
        return request.redirect(dashboard, 303, local=False)
