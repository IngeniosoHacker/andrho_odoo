import logging

from odoo import models

_logger = logging.getLogger(__name__)


class IrMailServer(models.Model):
    """No mail leaves the instance: AndRho's platform notifies the users.
    Messages are logged and reported as sent, so nothing piles up as failed."""

    _inherit = "ir.mail_server"

    def send_email(self, message, *args, **kwargs):
        _logger.info("andrho_core: outgoing mail suppressed (%s)", message["Subject"])
        return message["Message-Id"] or "andrho-suppressed"
