from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TransportForwardingManifoldLine(models.Model):
    _name = "transport.forwarding.manifold.line"
    _description = "Forwarding Manifold Line"
    _order = "id asc"

    manifold_id = fields.Many2one(
        "transport.forwarding.manifold",
        string="Manifold",
        ondelete="cascade",
        required=True,
    )
    transporter_id = fields.Many2one(
        related="manifold_id.from_transporter_id", store=True, readonly=True
    )
    hub_location_id = fields.Many2one(
        related="manifold_id.hub_id", store=True, readonly=True
    )

    goods_type_id = fields.Many2one(
        "transport.goods.type",
        string="Goods Type",
        required=True,
        ondelete="cascade",
    )

    goods_invoice_number = fields.Char(string="Invoice No")
    goods_description = fields.Char(string="Description")
    qty = fields.Float(
        string="Quantity",
        default=1,
        required=True,
    )
    weight = fields.Float(
        string="Weight",
        required=True,
    )
    unit_id = fields.Many2one("uom.uom", string="Unit", required=True)
    goods_value = fields.Float()
    delivery_location_id = fields.Many2one(
        "transport.location",
        string="Delivery Location",
        required=True,
        domain="[('location_type','=','spoke')]",
        help="Final delivery spoke / customer location",
    )

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("received", "Received"),
            ("booked", "Booked"),
            ("damaged", "Damaged"),
            ("returned", "Returned"),
        ],
        string="Status",
        default="pending",
    )

    booking_id = fields.Many2one(
        "transport.booking",
        string="Booking",
    )

    # -------------------------
    # Freight calculation fields
    # -------------------------
    amount = fields.Float(
        string="Freight Amount", compute="_compute_amount", store=True
    )
    rate = fields.Float(string="Rate per UOM", readonly=True)

    @api.onchange("qty", "unit_id", "manifold_id")
    def _onchange_qty_unit(self):
        _logger.warning("🔥 ONCHANGE FIRED for line %s", self)

        # for line in self:
        # rate = line.manifold_id.from_transporter_id
        # line.amount = rate
        #     if not line.manifold_id or not line.manifold_id.rate_id:
        #         line.amount = 0.0
        #         line.rate = 0.0
        #         continue
        #     rate = line.manifold_id.rate_id
        #     qty = line.qty
        #     if line.unit_id != rate.uom_id:
        #         qty = line.unit_id._compute_quantity(qty, rate.uom_id)
        #     line.amount = qty * rate.rate
        #     line.rate = rate.rate

    @api.depends("qty", "weight", "unit_id", "manifold_id.from_transporter_id")
    def _compute_amount(self):
        Rate = self.env["transport.b2b.rate"]

        for line in self:
            line.amount = 0.0

            if not line.manifold_id or not line.manifold_id.from_transporter_id:
                continue

            rate = Rate.get_b2b_rate(
                transporter_id=line.manifold_id.from_transporter_id.id,
                uom_id=line.unit_id.id,
            )

            if not rate:
                continue

            line.amount = rate.rate * (line.weight or 1)
