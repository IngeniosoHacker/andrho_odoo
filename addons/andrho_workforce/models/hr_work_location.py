"""A work site (obra) is an hr.work.location: AndRho keeps the site and its
supervisors; here it's where employees and crews belong."""
from odoo import api, fields, models


class HrWorkLocation(models.Model):
    _inherit = "hr.work.location"

    andrho_site_ref = fields.Char("Obra en AndRho", index=True, copy=False)

    @api.model
    def andrho_sync_site(self, ref, name, active=True):
        """The location for AndRho's site ref (created the first time)."""
        loc = self.with_context(active_test=False).search([("andrho_site_ref", "=", ref)], limit=1)
        vals = {"name": name, "active": bool(active)}
        if loc:
            loc.write(vals)
            return loc.id
        vals.update(andrho_site_ref=ref, location_type="other", address_id=self.env.company.partner_id.id)
        return self.create(vals).id
