from odoo import fields, models


class TransportAccountMove(models.Model):
    _inherit = "account.move"

    booking_id = fields.Many2one(
        "transport.booking",
        string="Transport Booking",
        index=True,
    )
