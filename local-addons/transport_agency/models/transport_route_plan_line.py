from odoo import fields, models, api
from odoo.exceptions import ValidationError, UserError


class TransportRoutePlanLine(models.Model):
    _name = "transport.route.plan.line"
    _order = "sequence"

    route_plan_id = fields.Many2one(
        "transport.route.plan",
        required=True,
        ondelete="cascade",
    )

    sequence = fields.Integer(required=True)
    sequence_label = fields.Char(
        string="Seq",
        compute="_compute_sequence_label",
        store=False,
    )

    origin_location_id = fields.Many2one(
        "transport.location",
        required=True,
        # domain=[("location_type", "=", "hub")],
    )
    destination_location_id = fields.Many2one(
        "transport.location",
        required=True,
        # domain=[("location_type", "=", "hub")],
    )

    @api.depends("sequence")
    def _compute_sequence_label(self):
        for rec in self:
            rec.sequence_label = f"Seq {rec.sequence}" if rec.sequence else ""
