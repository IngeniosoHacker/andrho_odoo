"""A crew (cuadrilla): who works together and where inside the site, as the
supervisor reported it by WhatsApp. Each report is kept in its history:
who reported what and when."""
from odoo import api, fields, models


class Crew(models.Model):
    _name = "andrho.crew"
    _description = "Cuadrilla"
    _order = "work_location_id, name"

    name = fields.Char("Cuadrilla", required=True)
    work_location_id = fields.Many2one("hr.work.location", "Obra", required=True, index=True, ondelete="cascade")
    member_ids = fields.Many2many("hr.employee", "andrho_crew_employee_rel", "crew_id", "employee_id", "Integrantes")
    zone = fields.Char("Dónde trabaja", help="Dentro de la obra: nivel, torre, área.")
    activity = fields.Char("Actividad")
    reported_by = fields.Char("Reportó")
    reported_at = fields.Datetime("Reportado")
    report_ids = fields.One2many("andrho.crew.report", "crew_id", "Historial")
    active = fields.Boolean(default=True)

    def _andrho_dict(self):
        self.ensure_one()
        return {
            "id": self.id, "name": self.name, "site_id": self.work_location_id.id, "zone": self.zone or "",
            "activity": self.activity or "", "members": [{"id": m.id, "name": m.name, "code": m.andrho_code or ""} for m in self.member_ids],
            "reported_by": self.reported_by or "",
            "reported_at": fields.Datetime.to_string(self.reported_at) if self.reported_at else "",
        }

    @api.model
    def andrho_report(self, location_id, vals):
        """Saves a crew report: {name, member_ids, zone, activity,
        reported_by}. The crew is found by name within the site."""
        name = (vals.get("name") or "").strip() or "Cuadrilla"
        crew = self.search([("work_location_id", "=", location_id), ("name", "=ilike", name)], limit=1)
        now = fields.Datetime.now()
        data = {
            "name": name, "work_location_id": location_id, "zone": vals.get("zone") or False,
            "activity": vals.get("activity") or False, "reported_by": vals.get("reported_by") or False,
            "reported_at": now, "member_ids": [(6, 0, vals.get("member_ids") or [])],
        }
        if crew:
            crew.write(data)
        else:
            crew = self.create(data)
        self.env["andrho.crew.report"].create({
            "crew_id": crew.id, "zone": data["zone"], "activity": data["activity"],
            "members": ", ".join(crew.member_ids.mapped("name")), "reported_by": data["reported_by"], "reported_at": now,
        })
        return crew.id

    @api.model
    def andrho_overview(self, location_ids=None):
        """Staff grouped by site, with the crews, for AndRho's dashboard."""
        Loc = self.env["hr.work.location"]
        locs = Loc.browse(location_ids).exists() if location_ids else Loc.search([("andrho_site_ref", "!=", False)])
        out = []
        for loc in locs:
            emps = self.env["hr.employee"].search([("work_location_id", "=", loc.id)], order="name")
            crews = self.search([("work_location_id", "=", loc.id)])
            out.append({
                "id": loc.id, "ref": loc.andrho_site_ref or "", "name": loc.name,
                "employees": [e._andrho_dict() for e in emps], "crews": [c._andrho_dict() for c in crews],
            })
        return out


class CrewReport(models.Model):
    _name = "andrho.crew.report"
    _description = "Reporte de cuadrilla"
    _order = "reported_at desc, id desc"

    crew_id = fields.Many2one("andrho.crew", "Cuadrilla", required=True, ondelete="cascade", index=True)
    zone = fields.Char("Dónde")
    activity = fields.Char("Actividad")
    members = fields.Char("Integrantes")
    reported_by = fields.Char("Reportó")
    reported_at = fields.Datetime("Cuándo")
