from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class TransportInboundManifestLine(models.Model):
    _name = "transport.inbound.manifest.line"
    _description = "Inbound Consignment Line"

    manifest_id = fields.Many2one(
        "transport.inbound.manifest",
        required=True,
        ondelete="cascade",
    )

    delivery_location_id = fields.Many2one(
        "transport.location",
        string="Delivery Address",
        required=True,
    )

    goods_type_id = fields.Many2one(
        "transport.goods.type",
        string="Goods Type",
        required=True,
        ondelete="cascade",
    )
    goods_docket_number = fields.Char(string="Docket No")
    description = fields.Char(string="Description")

    weight = fields.Float()
    unit_id = fields.Many2one("uom.uom", string="Unit", required=True)
    qty = fields.Integer()

    # -------------------------
    # Freight calculation fields
    # -------------------------
    rate = fields.Float(string="Rate", readonly=True)
    amount = fields.Float(string="Amount", compute="_compute_amount", store=True)

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("booked", "Booked"),
            ("fail", "Fail"),
        ],
        string="Status",
        default="pending",
    )

    @api.depends("qty", "weight", "unit_id", "manifest_id.partner_id")
    def _compute_amount(self):
        Rate = self.env["transport.b2b.rate"]

        for line in self:
            line.amount = 0.0

            if not line.manifest_id or not line.manifest_id.partner_id:
                continue

            rate = Rate.get_b2b_rate(
                transporter_id=line.manifest_id.partner_id.id,
                uom_id=line.unit_id.id,
            )

            if not rate:
                continue
            line.rate = rate.rate
            line.amount = rate.rate * (line.weight or 1)
