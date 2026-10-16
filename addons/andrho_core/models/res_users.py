from odoo import api, models
from odoo.exceptions import AccessDenied

from .sso import verify_token

# AndRho roles that administer the ERP; anyone else is an inventory user.
ADMIN_ROLES = {"owner", "admin"}


class ResUsers(models.Model):
    _inherit = "res.users"

    def _check_credentials(self, credential, env):
        if credential.get("type") == "andrho_sso":
            data = verify_token(self.env, credential.get("token"))
            if data["login"] != (self.env.user.login or "").lower():
                raise AccessDenied()
            return {"uid": self.env.user.id, "auth_method": "andrho_sso", "mfa": "skip"}
        return super()._check_credentials(credential, env)

    @api.model
    def _andrho_user(self, login, name, role):
        """The Odoo user for an AndRho user, created on their first entry.
        Owners and admins get the administrator's groups."""
        users = self.sudo().with_context(active_test=False)
        user = users.search([("login", "=ilike", login)], limit=1)
        if user:
            if not user.active:
                raise AccessDenied()
            return user
        if role in ADMIN_ROLES:
            groups = self.env.ref("base.user_admin").sudo().group_ids
        else:
            groups = self.env.ref("base.group_user") | self.env.ref("stock.group_stock_user")
        return users.with_context(no_reset_password=True).create({
            "login": login,
            "email": login,
            "name": name or login,
            "group_ids": [(6, 0, groups.ids)],
            "action_id": self.env.ref("stock.stock_picking_type_action").id,
        })
