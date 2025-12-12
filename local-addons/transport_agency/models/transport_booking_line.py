from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TransportBookingLine(models.Model):
    _name = "transport.booking.line"
    _description = "Transport Booking Billing Line"

    booking_id = fields.Many2one(
        "transport.booking", string="Booking", required=True, ondelete="cascade"
    )
    charge_type = fields.Selection(
        [
            ("freight", "Freight"),
            ("advance", "Advance"),
            ("docket", "Docket Charge"),
            ("handling", "Handling Charge"),
            ("oda", "ODA Charge"),
            ("fuel", "Fuel Surcharge"),
            ("value_surcharge", "Value Surcharge"),
            ("other", "Other Charge"),
        ],
        string="Charge Type",
        required=True,
    )
    amount = fields.Monetary(
        string="Amount", currency_field="currency_id", required=True
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
