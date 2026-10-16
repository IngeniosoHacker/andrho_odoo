from odoo import models

from .sso import DASHBOARD_PARAM


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        info = super().session_info()
        # The way back to AndRho's dashboard (user menu, logout).
        info["andrho_dashboard_url"] = self.env["ir.config_parameter"].sudo().get_param(DASHBOARD_PARAM) or ""
        return info
