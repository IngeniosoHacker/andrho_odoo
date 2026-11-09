"""A live sale and its items.

The seller picks products in AndRho and taps "Organizar venta": andrho-api
creates the live here (``andrho_create``), orders the items and gives each
one a short unique live name (``andrho_set_order``). During the live it
reserves the first commenter's item (``andrho_reserve``), confirms or
releases it with the buyer's Messenger answer, and at the end marks what
didn't sell (``andrho_finish``) so it can be posted on the Page.

Item states:
  available  on sale (in the live, or posted after it)
  reserved   someone commented its name first; waiting for "Sí"
  confirmed  the buyer said "Sí": on a shipping card, reserved in stock
  unsold     the live ended without a buyer
  posted     published on the Page after the live ("comenta Mío")
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

STATES = [
    ("available", "Disponible"),
    ("reserved", "Apartado"),
    ("confirmed", "Confirmado"),
    ("unsold", "No vendido"),
    ("posted", "Publicado"),
]


class LiveSale(models.Model):
    _name = "andrho.live.sale"
    _description = "Venta en vivo"
    _order = "date desc, id desc"

    name = fields.Char("Live", required=True, default=lambda self: "Live del %s" % fields.Date.context_today(self).strftime("%d/%m/%Y"))
    date = fields.Datetime("Fecha", default=fields.Datetime.now, required=True)
    state = fields.Selection(
        [("draft", "Preparando"), ("ready", "Organizado"), ("live", "En vivo"), ("done", "Terminado")],
        default="draft", required=True, index=True,
    )
    channel = fields.Selection([("facebook", "Facebook"), ("instagram", "Instagram")], default="facebook", required=True)
    live_url = fields.Char("Enlace del live")
    platform_live_id = fields.Char("ID del live en Meta", index=True)
    started_at = fields.Datetime("Inició")
    ended_at = fields.Datetime("Terminó")
    line_ids = fields.One2many("andrho.live.sale.line", "live_id", "Artículos")
    card_ids = fields.One2many("andrho.live.card", "live_id", "Tarjetas de envío")
    item_count = fields.Integer("Nº de artículos", compute="_compute_stats", store=True)
    sold_count = fields.Integer("Vendidos", compute="_compute_stats", store=True)
    reserved_count = fields.Integer("Apartados", compute="_compute_stats", store=True)
    unsold_count = fields.Integer("Sin vender", compute="_compute_stats", store=True)
    revenue = fields.Float("Ventas", compute="_compute_stats", store=True)
    buyer_count = fields.Integer("Compradores", compute="_compute_stats", store=True)
    current_line_id = fields.Many2one("andrho.live.sale.line", "Siguiente artículo", compute="_compute_current")

    @api.depends("line_ids.state", "line_ids.price", "line_ids.buyer_id")
    def _compute_stats(self):
        for live in self:
            lines = live.line_ids
            sold = lines.filtered(lambda l: l.state == "confirmed")
            live.item_count = len(lines)
            live.sold_count = len(sold)
            live.reserved_count = len(lines.filtered(lambda l: l.state == "reserved"))
            live.unsold_count = len(lines.filtered(lambda l: l.state in ("unsold", "posted")))
            live.revenue = sum(sold.mapped("price"))
            live.buyer_count = len(sold.mapped("buyer_id"))

    def _compute_current(self):
        for live in self:
            live.current_line_id = live.line_ids.filtered(lambda l: l.state == "available")[:1]

    # -- called by andrho-api ---------------------------------------------

    @api.model
    def andrho_set_enabled(self, enabled):
        """Shows or hides live sales for everyone in this ERP. AndRho turns
        it on when the plan includes it and the business uses it, and off
        when it doesn't (a downgrade, or the owner turns it off)."""
        group = self.env.ref("andrho_live_sale.group_live_sale")
        internal = self.env.ref("base.group_user")
        if enabled:
            internal.sudo().write({"implied_ids": [(4, group.id)]})
        else:
            internal.sudo().write({"implied_ids": [(3, group.id)]})
            group.sudo().write({"user_ids": [(5, 0, 0)]})
        self.env["ir.config_parameter"].sudo().set_param("andrho.live.enabled", "1" if enabled else "0")
        return True

    @api.model
    def andrho_create(self, name, items, channel="facebook"):
        """A live with items [{product_id, price}] in the given order."""
        if not items:
            raise UserError("Elige al menos un artículo para el live.")
        live = self.create({"name": name or False, "channel": channel} if name else {"channel": channel})
        products = self.env["product.product"].browse([int(i["product_id"]) for i in items]).exists()
        by_id = {p.id: p for p in products}
        lines = []
        for seq, item in enumerate(items, start=1):
            product = by_id.get(int(item["product_id"]))
            if not product:
                continue
            price = item.get("price")
            lines.append({
                "live_id": live.id,
                "sequence": seq * 10,
                "product_id": product.id,
                "live_name": item.get("live_name") or "%s %d" % (product.name, seq),
                "price": float(price) if price not in (None, False, "") else product.lst_price,
            })
        self.env["andrho.live.sale.line"].create(lines)
        return live.id

    def andrho_set_order(self, ordered):
        """[{line_id, sequence, live_name}]: AndRho's suggested order."""
        self.ensure_one()
        Line = self.env["andrho.live.sale.line"]
        for o in ordered:
            line = Line.browse(int(o["line_id"]))
            if line.live_id != self:
                continue
            vals = {"sequence": int(o.get("sequence", line.sequence))}
            if o.get("live_name"):
                vals["live_name"] = o["live_name"]
            line.write(vals)
        if self.state == "draft":
            self.state = "ready"
        return True

    def andrho_start(self, live_url=None, platform_live_id=None):
        self.ensure_one()
        vals = {"state": "live", "started_at": self.started_at or fields.Datetime.now()}
        if live_url:
            vals["live_url"] = live_url
        if platform_live_id:
            vals["platform_live_id"] = platform_live_id
        self.write(vals)
        return True

    def andrho_finish(self):
        """Ends the live: what nobody bought becomes "No vendido"."""
        for live in self:
            live.line_ids.filtered(lambda l: l.state == "available").write({"state": "unsold"})
            live.write({"state": "done", "ended_at": fields.Datetime.now()})
        return True

    def andrho_summary(self):
        """What AndRho's dashboard shows for a live."""
        self.ensure_one()
        return {
            "id": self.id, "name": self.name, "state": self.state, "channel": self.channel,
            "date": fields.Datetime.to_string(self.date), "live_url": self.live_url or "",
            "platform_live_id": self.platform_live_id or "",
            "started_at": fields.Datetime.to_string(self.started_at) if self.started_at else "",
            "ended_at": fields.Datetime.to_string(self.ended_at) if self.ended_at else "",
            "item_count": self.item_count, "sold_count": self.sold_count, "reserved_count": self.reserved_count,
            "unsold_count": self.unsold_count, "revenue": self.revenue, "buyer_count": self.buyer_count,
            "lines": [l._andrho_dict() for l in self.line_ids],
            "cards": [{
                "id": c.id, "buyer": c.buyer_name or "", "first_name": c.first_name or "", "phone": c.phone or "",
                "address": c.address or "", "zone": c.zone or "", "items": c.item_count, "total": c.total,
                "discount_pct": c.discount_pct, "state": c.state,
            } for c in self.card_ids],
        }


class LiveSaleLine(models.Model):
    _name = "andrho.live.sale.line"
    _description = "Artículo de una venta en vivo"
    _order = "sequence, id"

    live_id = fields.Many2one("andrho.live.sale", "Live", ondelete="cascade", index=True)
    sequence = fields.Integer("Orden", default=10)
    product_id = fields.Many2one("product.product", "Producto", required=True, ondelete="restrict")
    image_128 = fields.Image(related="product_id.image_128")
    live_name = fields.Char("Nombre en el live", required=True, help="Lo que dices en el live y lo que el comprador comenta.")
    price = fields.Float("Precio", required=True)
    state = fields.Selection(STATES, default="available", required=True, index=True)
    buyer_id = fields.Many2one("andrho.live.buyer", "Comprador", ondelete="set null")
    card_id = fields.Many2one("andrho.live.card", "Tarjeta de envío", ondelete="set null")
    comment_id = fields.Char("Comentario (Meta)")
    comment_text = fields.Char("Comentario")
    claimed_at = fields.Datetime("Apartado a las")
    post_id = fields.Char("Publicación (Meta)", help="La publicación del artículo en la Página, después del live.")

    _live_name_uniq = models.Constraint(
        "UNIQUE(live_id, live_name)", "Cada artículo del live necesita un nombre distinto."
    )

    def _andrho_dict(self):
        self.ensure_one()
        return {
            "id": self.id, "sequence": self.sequence, "product_id": self.product_id.id,
            "product": self.product_id.display_name, "live_name": self.live_name, "price": self.price,
            "state": self.state, "buyer": self.buyer_id.name or "", "buyer_psid": self.buyer_id.psid or "",
            "card_id": self.card_id.id or False, "post_id": self.post_id or "",
            "comment_id": self.comment_id or "",
        }

    @api.model
    def andrho_lines(self, line_ids):
        return [l._andrho_dict() for l in self.browse(line_ids).exists()]

    def andrho_reserve(self, psid, buyer_name, page_id, comment_id=None, comment_text=None, channel="facebook"):
        """The first commenter takes it. False if it's no longer available."""
        self.ensure_one()
        if self.state not in ("available", "posted"):
            return False
        buyer_id = self.env["andrho.live.buyer"].andrho_find_or_create(psid, buyer_name, page_id, channel)
        self.write({
            "state": "reserved", "buyer_id": buyer_id, "comment_id": comment_id or False,
            "comment_text": comment_text or False, "claimed_at": fields.Datetime.now(),
        })
        return buyer_id

    def andrho_release(self):
        """The buyer said no (or didn't answer): back on sale."""
        for line in self:
            if line.state != "reserved":
                continue
            back = "posted" if line.post_id else ("available" if line.live_id.state != "done" else "unsold")
            line.write({"state": back, "buyer_id": False, "comment_id": False, "comment_text": False, "claimed_at": False})
        return True

    def andrho_confirm(self):
        """The buyer said "Sí": on their card, reserved in stock. Returns
        {card_id, needs_data, discount_pct}."""
        self.ensure_one()
        if self.state != "reserved" or not self.buyer_id:
            raise UserError("Este artículo no está apartado.")
        Card = self.env["andrho.live.card"]
        buyer = self.buyer_id
        # One card per buyer per live; a sale from the post after the live
        # joins the buyer's card if it hasn't been printed yet.
        card = Card.search([
            ("buyer_id", "=", buyer.id), ("live_id", "=", self.live_id.id), ("state", "in", ("data", "ready")),
        ], limit=1)
        if not card:
            enabled, minimum, discount = buyer._loyalty()
            card = Card.create({
                "live_id": self.live_id.id,
                "buyer_id": buyer.id, "phone": buyer.phone, "address": buyer.address, "zone": buyer.zone,
                "discount_pct": discount if enabled and buyer.purchase_count >= minimum else 0.0,
            })
            if card.phone and card.address:
                card.state = "ready"
        self.write({"state": "confirmed", "card_id": card.id})
        card._reserve(self)
        buyer.write({
            "purchase_count": buyer.purchase_count + 1,
            "total_spent": buyer.total_spent + self.price,
            "last_purchase": fields.Datetime.now(),
        })
        return {"card_id": card.id, "needs_data": card.state == "data", "discount_pct": card.discount_pct,
                "phone": card.phone or "", "address": card.address or "", "zone": card.zone or ""}

    def andrho_mark_posted(self, post_id):
        self.ensure_one()
        self.write({"state": "posted", "post_id": post_id})
        return True

    def andrho_post_data(self):
        """The photo (base64) and sales description for the unsold-items
        post. No product name: the post shows the photo and the price."""
        self.ensure_one()
        img = self.product_id.image_1024 or self.product_id.product_tmpl_id.image_1024
        return {
            "image": img.decode() if isinstance(img, bytes) else (img or ""),
            "description": self.product_id.description_sale or "",
        }
