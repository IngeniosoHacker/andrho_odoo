"""What AndRho knows about how to reach a contact.

Filled by andrho-api from the conversations (live sales today): the channel
the person asked to be contacted on, the WhatsApp number they wrote from
(only when they wrote themselves) and when and where they accepted that
their data is kept to handle their orders.
"""
from odoo import fields, models

CHANNELS = [("messenger", "Messenger"), ("whatsapp", "WhatsApp")]


class ResPartner(models.Model):
    _inherit = "res.partner"

    andrho_preferred_channel = fields.Selection(CHANNELS, "Medio de comunicación preferido")
    andrho_whatsapp = fields.Char("WhatsApp", help="El número desde el que la persona escribió por WhatsApp.")
    andrho_consent_at = fields.Datetime("Aceptó el aviso de datos", readonly=True)
    andrho_consent_channel = fields.Selection(CHANNELS, "Canal del aviso", readonly=True)

    def andrho_set_reach(self, vals):
        """andrho-api's single write: {preferred_channel, whatsapp, consent_channel}.
        Consent keeps its first date."""
        out = {}
        if vals.get("preferred_channel") in ("messenger", "whatsapp"):
            out["andrho_preferred_channel"] = vals["preferred_channel"]
        if vals.get("whatsapp"):
            out["andrho_whatsapp"] = vals["whatsapp"]
        for p in self:
            row = dict(out)
            if vals.get("consent_channel") in ("messenger", "whatsapp") and not p.andrho_consent_at:
                row.update(andrho_consent_at=fields.Datetime.now(), andrho_consent_channel=vals["consent_channel"])
            if row:
                p.sudo().write(row)
        return True
