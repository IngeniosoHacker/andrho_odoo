"""A shipping card: one per buyer per live (or per sale from a post).

It gathers the buyer's confirmed items, holds the stock reservation (an
outgoing transfer, reserved with ``action_assign``) and prints on the
"Tarjetas de envío" PDF, four 10 × 10 cm cards per letter page.
"""
from odoo import api, fields, models

MESSAGE_PARAM = "andrho.live.card_message"
SHOW_LOGO_PARAM = "andrho.live.card_show_logo"
DEFAULT_MESSAGE = "¡Gracias por tu compra, {nombre}!"


class LiveCard(models.Model):
    _name = "andrho.live.card"
    _description = "Tarjeta de envío"
    _order = "create_date desc, id desc"

    name = fields.Char("Tarjeta", compute="_compute_name", store=True)
    live_id = fields.Many2one("andrho.live.sale", "Live", ondelete="set null", index=True)
    buyer_id = fields.Many2one("andrho.live.buyer", "Comprador", required=True, ondelete="restrict")
    buyer_name = fields.Char(related="buyer_id.name")
    first_name = fields.Char(related="buyer_id.first_name")
    phone = fields.Char("Teléfono")
    address = fields.Char("Dirección")
    zone = fields.Char("Zona o municipio")
    notes = fields.Char("Notas")
    line_ids = fields.One2many("andrho.live.sale.line", "card_id", "Artículos")
    item_count = fields.Integer("Nº de artículos", compute="_compute_totals", store=True)
    subtotal = fields.Float("Subtotal", compute="_compute_totals", store=True)
    discount_pct = fields.Float("Descuento (%)", default=0.0, help="Cliente frecuente.")
    total = fields.Float("Total", compute="_compute_totals", store=True)
    state = fields.Selection(
        [("data", "Esperando datos"), ("ready", "Lista para enviar"), ("printed", "Impresa"), ("delivered", "Entregada")],
        default="data", required=True, index=True,
    )
    picking_id = fields.Many2one("stock.picking", "Reserva en inventario", ondelete="set null")
    message = fields.Char("Mensaje", compute="_compute_message")
    show_logo = fields.Boolean(compute="_compute_message")

    @api.depends("buyer_id.name", "live_id.name")
    def _compute_name(self):
        for c in self:
            c.name = " · ".join(p for p in [c.buyer_id.name, c.live_id.name] if p)

    @api.depends("line_ids.price", "discount_pct")
    def _compute_totals(self):
        for c in self:
            c.item_count = len(c.line_ids)
            c.subtotal = sum(c.line_ids.mapped("price"))
            c.total = round(c.subtotal * (1 - (c.discount_pct or 0) / 100.0), 2)

    def _compute_message(self):
        get = self.env["ir.config_parameter"].sudo().get_param
        template = get(MESSAGE_PARAM) or DEFAULT_MESSAGE
        show = get(SHOW_LOGO_PARAM, "1") not in ("0", "false", "False")
        for c in self:
            c.message = template.replace("{nombre}", c.first_name or "")
            c.show_logo = show

    # -- stock -------------------------------------------------------------

    def _picking_type(self):
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        return warehouse.out_type_id

    def _reserve(self, line):
        """Adds line's product to this card's transfer and reserves it."""
        self.ensure_one()
        ptype = self._picking_type()
        if not ptype:
            return
        self.buyer_id._ensure_partner()
        if not self.picking_id or self.picking_id.state in ("done", "cancel"):
            self.picking_id = self.env["stock.picking"].create({
                "picking_type_id": ptype.id,
                "partner_id": self.buyer_id.partner_id.id,
                "location_id": ptype.default_location_src_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "origin": self.name,
            })
        picking = self.picking_id
        self.env["stock.move"].create({
            "product_id": line.product_id.id,
            "product_uom_qty": 1,
            "product_uom": line.product_id.uom_id.id,
            "picking_id": picking.id,
            "location_id": picking.location_id.id,
            "location_dest_id": picking.location_dest_id.id,
        })
        if picking.state == "draft":
            picking.action_confirm()
        picking.action_assign()

    def _unreserve(self, line):
        self.ensure_one()
        picking = self.picking_id
        if not picking or picking.state in ("done", "cancel"):
            return
        moves = picking.move_ids.filtered(lambda m: m.product_id == line.product_id and m.state not in ("done", "cancel"))[:1]
        moves._action_cancel()
        if all(m.state == "cancel" for m in picking.move_ids):
            picking.action_cancel()

    # -- called by andrho-api ---------------------------------------------

    def andrho_set_shipping(self, phone=None, address=None, zone=None, notes=None):
        """Shipping data from Messenger; the card is ready once complete."""
        for c in self:
            vals = {k: v for k, v in {"phone": phone, "address": address, "zone": zone, "notes": notes}.items() if v}
            c.write(vals)
            c.buyer_id.write({k: v for k, v in vals.items() if k in ("phone", "address", "zone")})
            c.buyer_id._ensure_partner()
            if c.phone and c.address and c.state == "data":
                c.state = "ready"
        return True

    def action_print_cards(self):
        cards = self.filtered(lambda c: c.state in ("ready", "printed", "data"))
        cards.filtered(lambda c: c.state == "ready").write({"state": "printed"})
        return self.env.ref("andrho_live_sale.action_report_shipping_cards").report_action(cards)

    def action_delivered(self):
        for c in self:
            if c.picking_id and c.picking_id.state not in ("done", "cancel"):
                for move in c.picking_id.move_ids.filtered(lambda m: m.state not in ("done", "cancel")):
                    move.quantity = move.product_uom_qty
                    move.picked = True
                # skip_sms: Odoo would text the buyer through its own servers;
                # AndRho talks to buyers only through the seller's Messenger.
                c.picking_id.with_context(skip_backorder=True, skip_sms=True)._action_done()
            c.state = "delivered"
        return True
