from odoo import fields, models
from odoo.exceptions import ValidationError, UserError


class TransportRoutePlan(models.Model):
    _name = "transport.route.plan"
    _description = "Goods Movement Route Plan"

    name = fields.Char(required=True)

    line_ids = fields.One2many(
        "transport.route.plan.line",
        "route_plan_id",
        string="Route Plan Lines",
    )
    line_count = fields.Integer(
        string="Lines",
        compute="_compute_line_count",
        store=True,
    )

    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
