from odoo import models, fields, api
from odoo.exceptions import UserError


class TransportForwardingManifold(models.Model):
    _name = "transport.forwarding.manifold"
    _description = "Forwarding Schedule cum Manifold"
    _order = "date desc, id desc"

    name = fields.Char(string="FSCM No", required=True, copy=False, default="New")
    date = fields.Date(
        string="Manifold Date", default=fields.Date.context_today, required=True
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("received", "Good Received"),
            ("booked", "Booked"),
        ],
        default="draft",
    )

    from_transporter_id = fields.Many2one(
        "res.partner",
        string="From Transporter",
        domain=[("is_transporter", "=", True)],
        context={"default_is_transporter": True},
        required=True,
    )
    manifold_no = fields.Char(string="Manifold No", required=True)
    transport_mode = fields.Selection(
        [
            ("bus", "Bus"),
            ("train", "Train"),
            ("truck", "Truck"),
            ("air", "Air"),
            ("ship", "Ship"),
        ],
        string="Transport Mode",
        required=True,
    )
    hub_id = fields.Many2one(
        "transport.location",
        string="Receiving Hub",
        domain="[('owner_type', '=', 'own')]",
        required=True,
    )

    # Rate per UOM
    # rate_id = fields.Many2one(
    #     "transport.b2b.rate",
    #     string="Applied B2B Rate",
    #     readonly=True,
    # )
    # rate = fields.Float(string="Rate", readonly=True)

    total_amount = fields.Float(
        string="Total Amount", compute="_compute_total_amount", store=True
    )

    line_ids = fields.One2many(
        "transport.forwarding.manifold.line", "manifold_id", string="Manifold Lines"
    )
    # total_qty = fields.Float(
    #     string="Total Quantity", compute="_compute_totals", store=True
    # )
    # total_weight = fields.Float(
    #     string="Total Weight", compute="_compute_totals", store=True
    # )

    remarks = fields.Text(string="Remarks")

    # ------------------------
    # Compute totals for grid
    # ------------------------
    @api.depends("line_ids.qty", "line_ids.weight")
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped("amount"))

    # ------------------------
    # Assign sequence on create
    # ------------------------
    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("transport.forwarding.manifold")
                or "New"
            )
        return super().create(vals)

    # ------------------------
    # Actions
    # ------------------------
    def action_return_to_draft(self):
        for manifold in self:
            if manifold.state in ("received", "booked"):
                raise UserError(
                    "You cannot return a manifold to draft once it is received or booked."
                )
            manifold.state = "draft"

    def action_mark_confirm(self):
        for manifold in self:
            if manifold.state != "draft":
                raise UserError("Only draft manifolds can be confirmed.")
            if not manifold.line_ids:
                raise UserError("Cannot confirm a manifold without any lines.")
            for line in manifold.line_ids:
                if not line.qty or not line.weight:
                    raise UserError(
                        f"Line {line.id} must have quantity and weight set."
                    )
            manifold.state = "confirmed"

    def action_mark_received(self):
        for manifold in self:
            if manifold.state != "confirmed":
                raise UserError("Only confirmed manifolds can be received.")
            for line in manifold.line_ids:
                if line.state == "received":
                    continue
                self.env["transport.hub.inventory"].create(
                    {
                        "hub_id": manifold.hub_id.id,
                        "movement_type": "in",
                        "goods_type_id": line.goods_type_id.id,
                        "goods_description": line.goods_description,
                        "qty": line.qty,
                        "weight": line.weight,
                        "unit_id": line.unit_id.id,
                        "source_location_id": None,
                        "destination_location_id": manifold.hub_id.id,
                        "remarks": f"Received via Manifold {manifold.name}",
                    }
                )
                line.state = "received"
            manifold.state = "received"

    def action_create_booking(self):
        for manifold in self:
            if not manifold.line_ids:
                raise UserError("Cannot create booking without any lines.")
            for line in manifold.line_ids:
                if not line.qty or not line.weight:
                    raise UserError(
                        f"Line {line.id} must have quantity and weight set."
                    )
                if not line.booking_id:
                    booking = (
                        self.env["transport.booking"]
                        .with_context(booking_from_manifold=True)
                        .create(
                            {
                                "partner_id": manifold.from_transporter_id.id,
                                "pickup_location_id": manifold.hub_id.id,
                                "freight_amount": line.amount,
                                "delivery_location_id": line.delivery_location_id.id,
                                "booking_source_ref": f"transport.forwarding.manifold,{manifold.id}",
                            }
                        )
                    )
                    line.booking_id = booking.id
                    # Create booking line
                    self.env["transport.goods.line"].create(
                        {
                            "booking_id": booking.id,
                            "goods_invoice_number": line.goods_invoice_number,
                            "goods_type_id": line.goods_type_id.id,
                            "description": line.goods_description,
                            "qty": line.qty,
                            "actual_weight": line.weight,
                            "charged_weight": line.weight,
                            "unit_id": line.unit_id.id,
                            "goods_value": line.goods_value,
                        }
                    )
            manifold.state = "booked"
