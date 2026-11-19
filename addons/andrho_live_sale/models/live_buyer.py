"""A person who interacted with the seller's Page around a live: a buyer
(``kind=customer``) or a prospect (``kind=prospect``).

Meta gives each person several ids, and AndRho keeps them apart:

* ``commenter_id``: the id on their comments (what a live's comments carry);
* ``psid``: their Messenger id on the Page (known once they tap a button or
  write to the Page);
* ``wa_phone`` (on the contact, ``andrho_whatsapp``): only when they wrote
  themselves through WhatsApp.

Who's who (founder/live-sale-spec.md, audit 2026-11-19):

* a comment that matches an item's live name makes them a **customer** (tag
  "Cliente") and links them to the line and the live;
* a comment without a match, a message to the Page, or a reaction (only if
  the seller turns reactions on) makes them a **prospect** (tag "Prospecto"),
  with only what Meta gives: name and ids. People who only watch the live
  are not available through Meta's API, and AndRho doesn't look for them.

The loyalty program (optional) reads ``purchase_count``.
"""
from odoo import api, fields, models

LOYALTY_ENABLED = "andrho.live.loyalty_enabled"
LOYALTY_MIN = "andrho.live.loyalty_min_purchases"
LOYALTY_DISCOUNT = "andrho.live.loyalty_discount"

SOURCES = [
    ("comment", "Comentó un artículo"),
    ("comment_other", "Comentó"),
    ("message", "Escribió a la Página"),
    ("reaction", "Reaccionó"),
]


def first_name(full):
    """The first word of a name, for "¡Gracias por tu compra, Ana!"."""
    parts = (full or "").split()
    return parts[0].capitalize() if parts else ""


class LiveBuyer(models.Model):
    _name = "andrho.live.buyer"
    _description = "Cliente o prospecto de ventas en vivo"
    _order = "purchase_count desc, last_purchase desc, id desc"

    name = fields.Char("Nombre", required=True)
    first_name = fields.Char("Primer nombre", compute="_compute_first_name")
    kind = fields.Selection([("customer", "Cliente"), ("prospect", "Prospecto")], "Tipo", default="customer",
                            required=True, index=True)
    source = fields.Selection(SOURCES, "Cómo llegó", default="comment")
    commenter_id = fields.Char("ID en los comentarios", index=True, help="El id que Meta pone en sus comentarios.")
    psid = fields.Char("ID de Messenger", index=True, help="Su id de Messenger en la Página (lo da Meta).")
    page_id = fields.Char("Página", index=True)
    channel = fields.Selection([("facebook", "Facebook"), ("instagram", "Instagram")], default="facebook")
    phone = fields.Char("Teléfono")
    address = fields.Char("Dirección")
    zone = fields.Char("Zona o municipio")
    partner_id = fields.Many2one("res.partner", "Contacto", ondelete="set null")
    preferred_channel = fields.Selection(related="partner_id.andrho_preferred_channel", readonly=False)
    wa_phone = fields.Char(related="partner_id.andrho_whatsapp", string="WhatsApp")
    consent_at = fields.Datetime(related="partner_id.andrho_consent_at")
    consent_channel = fields.Selection(related="partner_id.andrho_consent_channel")
    live_ids = fields.Many2many("andrho.live.sale", "andrho_live_buyer_live_rel", "buyer_id", "live_id", "Lives")
    first_seen = fields.Datetime("Primera vez", default=fields.Datetime.now)
    converted_at = fields.Datetime("Pasó a cliente", help="Cuándo un prospecto apartó su primer artículo.")
    purchase_count = fields.Integer("Compras", default=0)
    total_spent = fields.Float("Total comprado", default=0.0)
    last_purchase = fields.Datetime("Última compra")
    frequent = fields.Boolean("Cliente frecuente", compute="_compute_frequent")
    card_ids = fields.One2many("andrho.live.card", "buyer_id", "Tarjetas de envío")
    line_ids = fields.One2many("andrho.live.sale.line", "buyer_id", "Artículos")

    _psid_page_uniq = models.Constraint(
        "UNIQUE(psid, page_id)", "Esta persona ya existe para esta Página."
    )
    _commenter_page_uniq = models.Constraint(
        "UNIQUE(commenter_id, page_id)", "Esta persona ya existe para esta Página."
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

    # -- tags --------------------------------------------------------------

    def _tags(self):
        ref = self.env.ref
        return ref("andrho_core.tag_customer", raise_if_not_found=False), ref("andrho_core.tag_prospect", raise_if_not_found=False)

    def _sync_tags(self):
        customer, prospect = self._tags()
        for b in self:
            if not b.partner_id or not customer or not prospect:
                continue
            if b.kind == "customer":
                b.partner_id.sudo().write({"category_id": [(4, customer.id), (3, prospect.id)]})
            else:
                b.partner_id.sudo().write({"category_id": [(4, prospect.id)]})

    def _ensure_partner(self):
        for b in self:
            if not b.partner_id:
                b.partner_id = self.env["res.partner"].create({"name": b.name})
            b.partner_id.write({"phone": b.phone or False, "street": b.address or False, "city": b.zone or False})

    @api.model
    def _find(self, page_id, commenter_id=None, psid=None):
        if commenter_id:
            b = self.search([("commenter_id", "=", commenter_id), ("page_id", "=", page_id)], limit=1)
            if b:
                return b
        if psid:
            return self.search([("psid", "=", psid), ("page_id", "=", page_id)], limit=1)
        return self.browse()

    # -- called by andrho-api ---------------------------------------------

    @api.model
    def andrho_find_or_create(self, commenter_id, name, page_id, channel="facebook", live_id=None):
        """The customer behind a comment that matched an item (created the
        first time; a prospect becomes a customer). Returns its id."""
        buyer = self._find(page_id, commenter_id=commenter_id)
        if buyer:
            vals = {}
            if name and buyer.name != name:
                vals["name"] = name
            if buyer.kind != "customer":
                vals.update(kind="customer", converted_at=fields.Datetime.now())
            if live_id:
                vals["live_ids"] = [(4, live_id)]
            if vals:
                buyer.write(vals)
        else:
            partner = self.env["res.partner"].create({"name": name or "Comprador"})
            buyer = self.create({
                "name": name or "Comprador", "commenter_id": commenter_id, "page_id": page_id,
                "channel": channel, "partner_id": partner.id, "kind": "customer", "source": "comment",
                "live_ids": [(4, live_id)] if live_id else [],
            })
        buyer._sync_tags()
        return buyer.id

    @api.model
    def andrho_touch_prospects(self, page_id, live_id, people):
        """People who interacted without taking an item: [{commenter_id |
        psid, name, source}]. Customers just get the live added. Returns how
        many prospects are new."""
        new = 0
        for p in people or []:
            commenter_id, psid = p.get("commenter_id") or False, p.get("psid") or False
            if not commenter_id and not psid:
                continue
            buyer = self._find(page_id, commenter_id=commenter_id, psid=psid)
            if buyer:
                vals = {}
                if live_id:
                    vals["live_ids"] = [(4, live_id)]
                if psid and not buyer.psid:
                    vals["psid"] = psid
                if commenter_id and not buyer.commenter_id:
                    vals["commenter_id"] = commenter_id
                if vals:
                    buyer.write(vals)
                continue
            name = (p.get("name") or "").strip() or "Sin nombre"
            partner = self.env["res.partner"].create({"name": name})
            buyer = self.create({
                "name": name, "commenter_id": commenter_id, "psid": psid, "page_id": page_id,
                "kind": "prospect", "source": p.get("source") if p.get("source") in dict(SOURCES) else "comment_other",
                "partner_id": partner.id, "live_ids": [(4, live_id)] if live_id else [],
            })
            buyer._sync_tags()
            new += 1
        return new

    def andrho_link_psid(self, psid):
        """The buyer tapped a button in Messenger: now we know their PSID.
        If they had written to the Page before (a prospect with that PSID),
        both become one."""
        self.ensure_one()
        if not psid or self.psid == psid:
            return self.id
        other = self.search([("psid", "=", psid), ("page_id", "=", self.page_id), ("id", "!=", self.id)], limit=1)
        if other:
            self.write({"live_ids": [(4, l.id) for l in other.live_ids]})
            old_partner = other.partner_id
            other.unlink()
            if old_partner and old_partner != self.partner_id:
                old_partner.sudo().write({"active": False})
        self.psid = psid
        return self.id

    def andrho_set_reach(self, vals):
        """{preferred_channel, whatsapp, consent_channel} on the contact."""
        self._ensure_partner()
        self.mapped("partner_id").andrho_set_reach(vals)
        return True

    def _andrho_person(self):
        self.ensure_one()
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "source": self.source or "",
            "preferred_channel": self.preferred_channel or "", "has_whatsapp": bool(self.wa_phone),
            "has_messenger": bool(self.psid), "consent_at": fields.Datetime.to_string(self.consent_at) if self.consent_at else "",
            "consent_channel": self.consent_channel or "", "purchase_count": self.purchase_count,
            "total_spent": self.total_spent, "first_seen": fields.Datetime.to_string(self.first_seen) if self.first_seen else "",
            "converted_at": fields.Datetime.to_string(self.converted_at) if self.converted_at else "",
            "partner_id": self.partner_id.id or 0, "lives": len(self.live_ids),
        }

    @api.model
    def andrho_people(self, live_id):
        """A live's customers and prospects, for AndRho's dashboard."""
        people = self.search([("live_ids", "in", [live_id])])
        lines = self.env["andrho.live.sale.line"].search([("live_id", "=", live_id), ("buyer_id", "!=", False)])
        items = {}
        for l in lines:
            items.setdefault(l.buyer_id.id, []).append({"live_name": l.live_name, "state": l.state, "price": l.price})
        out = []
        for b in people:
            row = b._andrho_person()
            row["items"] = items.get(b.id, [])
            out.append(row)
        return out

    @api.model
    def andrho_contacts(self, kind=None, limit=500):
        """Every live contact with the totals: customers, prospects and how
        many prospects became customers."""
        domain = [("kind", "=", kind)] if kind in ("customer", "prospect") else []
        rows = [b._andrho_person() for b in self.search(domain, limit=limit, order="id desc")]
        count = self.search_count
        customers = count([("kind", "=", "customer")])
        prospects = count([("kind", "=", "prospect")])
        converted = count([("converted_at", "!=", False)])
        channels = {c: count([("partner_id.andrho_preferred_channel", "=", c)]) for c in ("messenger", "whatsapp")}
        return {
            "contacts": rows, "customers": customers, "prospects": prospects, "converted": converted,
            "conversion": round(converted / (converted + prospects), 4) if (converted + prospects) else 0.0,
            "channels": channels,
        }
