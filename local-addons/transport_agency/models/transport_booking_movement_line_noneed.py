from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class TransportBookingMovementLine(models.Model):
    _name = "transport.booking.movement.line"
    _order = "sequence"

    booking_id = fields.Many2one("transport.booking", required=True)
    sequence = fields.Integer()
    sequence_label = fields.Char(
        string="Seq",
        compute="_compute_sequence_label",
        store=False,
    )

    planned_origin_id = fields.Many2one("transport.location")
    planned_destination_id = fields.Many2one("transport.location")

    actual_origin_id = fields.Many2one("transport.location")
    actual_destination_id = fields.Many2one("transport.location")

    transporter_id = fields.Many2one("res.partner")
    vehicle_id = fields.Many2one("fleet.vehicle")

    dispatch_date = fields.Datetime()
    arrival_date = fields.Datetime()

    state = fields.Selection(
        [
            ("planned", "Planned"),
            ("dispatched", "Dispatched"),
            ("arrived", "Arrived"),
            ("completed", "Completed"),
        ],
        default="planned",
    )

    @api.depends("sequence")
    def _compute_sequence_label(self):
        for rec in self:
            rec.sequence_label = f"Seq {rec.sequence}" if rec.sequence else ""
