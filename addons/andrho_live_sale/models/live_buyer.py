"""A person who bought through a live or an unsold-items post.

Known by their Messenger id on the seller's Page (``psid``), which Meta
keeps stable per Page. The loyalty program (optional, the seller turns it
on from AndRho) reads ``purchase_count``.
"""
from odoo import api, fields, models

LOYALTY_ENABLED = "andrho.live.loyalty_enabled"
LOYALTY_MIN = "andrho.live.loyalty_min_purchases"
LOYALTY_DISCOUNT = "andrho.live.loyalty_discount"


def first_name(full):
    """The first word of a name, for "¡Gracias por tu compra, Ana!"."""
    parts = (full or "").split()
    return parts[0].capitalize() if parts else ""


class LiveBuyer(models.Model):
    _name = "andrho.live.buyer"
    _description = "Comprador de ventas en vivo"
    _order = "purchase_count desc, last_purchase desc, id desc"

    name = fields.Char("Nombre", required=True)
    first_name = fields.Char("Primer nombre", compute="_compute_first_name")
    psid = fields.Char("ID de Messenger", index=True, help="Identificador del comprador en la Página (lo da Meta).")
    page_id = fields.Char("Página", index=True)
    channel = fields.Selection([("facebook", "Facebook"), ("instagram", "Instagram")], default="facebook")
    phone = fields.Char("Teléfono")
    address = fields.Char("Dirección")
    zone = fields.Char("Zona o municipio")
    partner_id = fields.Many2one("res.partner", "Contacto", ondelete="set null")
    purchase_count = fields.Integer("Compras", default=0)
    total_spent = fields.Float("Total comprado", default=0.0)
    last_purchase = fields.Datetime("Última compra")
    frequent = fields.Boolean("Cliente frecuente", compute="_compute_frequent")
    card_ids = fields.One2many("andrho.live.card", "buyer_id", "Tarjetas de envío")

    _psid_page_uniq = models.Constraint(
        "UNIQUE(psid, page_id)", "Este comprador ya existe para esta Página."
    )

    @api.depends("name")
    def _compute_first_name(self):
        for b in self:
            b.first_name = first_name(b.name)

    @api.model
    def _loyalty(self):
        get = self.env["ir.config_parameter"].sudo().get_param
        enabled = get(LOYALTY_ENABLED, "0") in ("1", "true", "True")
        try:
            minimum = max(1, int(get(LOYALTY_MIN, "3")))
        except ValueError:
            minimum = 3
        try:
            discount = min(90.0, max(0.0, float(get(LOYALTY_DISCOUNT, "10"))))
        except ValueError:
            discount = 10.0
        return enabled, minimum, discount

    def _compute_frequent(self):
        enabled, minimum, _ = self._loyalty()
        for b in self:
            b.frequent = enabled and b.purchase_count >= minimum

    @api.model
    def andrho_find_or_create(self, psid, name, page_id, channel="facebook"):
        """The buyer for a Messenger id on a Page (created the first time)."""
        buyer = self.search([("psid", "=", psid), ("page_id", "=", page_id)], limit=1)
        if buyer:
            if name and buyer.name != name:
                buyer.name = name
            return buyer.id
        partner = self.env["res.partner"].create({"name": name or "Comprador"})
        return self.create({
            "name": name or "Comprador", "psid": psid, "page_id": page_id,
            "channel": channel, "partner_id": partner.id,
        }).id

    def _ensure_partner(self):
        for b in self:
            if not b.partner_id:
                b.partner_id = self.env["res.partner"].create({"name": b.name})
            b.partner_id.write({"phone": b.phone or False, "street": b.address or False, "city": b.zone or False})
