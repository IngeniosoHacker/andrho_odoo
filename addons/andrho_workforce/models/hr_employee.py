"""Workers registered from the site by WhatsApp.

The photo is personal data: it lives only in this ERP (``image_1920``) and
is erased when the worker leaves (archived, or the departure wizard),
from the employee and from their work contact.
"""
import unicodedata

from odoo import api, fields, models


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return " ".join("".join(c for c in s if unicodedata.category(c) != "Mn").split())


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    andrho_code = fields.Char("Código interno", index=True, copy=False)
    andrho_reported_by = fields.Char("Dado de alta por", readonly=True)
    andrho_reported_at = fields.Datetime("Alta reportada", readonly=True)
    andrho_photo = fields.Boolean("Foto del trabajador", readonly=True,
                                  help="Tiene la foto que mandó el supervisor (no el avatar que Odoo genera).")
    andrho_crew_ids = fields.Many2many("andrho.crew", "andrho_crew_employee_rel", "employee_id", "crew_id", "Cuadrillas")

    def _andrho_forget_photo(self):
        for e in self.sudo():
            e.with_context(andrho_forgetting=True).write({"image_1920": False, "andrho_photo": False})
            if e.work_contact_id:
                e.work_contact_id.image_1920 = False

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("andrho_forgetting"):
            return res
        if vals.get("active") is False or vals.get("departure_date"):
            self.filtered(lambda e: not e.active or e.departure_date)._andrho_forget_photo()
        return res

    # -- called by andrho-api ---------------------------------------------

    def _andrho_dict(self):
        self.ensure_one()
        return {
            "id": self.id, "name": self.name, "code": self.andrho_code or "",
            "site_id": self.work_location_id.id or 0, "site": self.work_location_id.name or "",
            "has_photo": self.andrho_photo,
            "crews": self.andrho_crew_ids.mapped("name"),
            "reported_by": self.andrho_reported_by or "",
            "reported_at": fields.Datetime.to_string(self.andrho_reported_at) if self.andrho_reported_at else "",
        }

    @api.model
    def andrho_find(self, location_ids, name=None, code=None):
        """Employees that match a code (exact, company-wide) or a name
        (accents and case ignored; within the sites, then anywhere)."""
        if code:
            found = self.search([("andrho_code", "=ilike", code.strip())])
            if found:
                return [e._andrho_dict() for e in found]
        if not name:
            return []
        n = norm(name)
        pool = self.search([("work_location_id", "in", location_ids or [])]) or self.search([])
        exact = pool.filtered(lambda e: norm(e.name) == n)
        if exact:
            return [e._andrho_dict() for e in exact]
        words = n.split()
        partial = pool.filtered(lambda e: all(w in norm(e.name) for w in words))
        return [e._andrho_dict() for e in partial[:5]]

    @api.model
    def andrho_upsert(self, location_id, vals):
        """Creates or updates a worker: {employee_id?, name, code, image,
        reported_by}. Returns {id, created}."""
        data = {"work_location_id": location_id}
        if vals.get("name"):
            data["name"] = vals["name"].strip()
        if vals.get("code"):
            data["andrho_code"] = vals["code"].strip()
        if vals.get("image"):
            data.update(image_1920=vals["image"], andrho_photo=True)
        if vals.get("reported_by"):
            data.update(andrho_reported_by=vals["reported_by"], andrho_reported_at=fields.Datetime.now())
        emp = self.browse(vals.get("employee_id") or 0).exists()
        if emp:
            emp.write(data)
            return {"id": emp.id, "created": False}
        data.setdefault("name", vals.get("code") or "Sin nombre")
        return {"id": self.create(data).id, "created": True}

    def andrho_terminate(self):
        """The worker leaves: archived, and their photo erased."""
        self.write({"active": False})
        self._andrho_forget_photo()
        return True
