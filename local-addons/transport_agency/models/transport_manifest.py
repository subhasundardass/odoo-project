from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class TransportManifest(models.Model):
    _name = "transport.manifest"
    _description = "Internal Transfer Manifest"
    _order = "id desc"

    name = fields.Char(
        string="Manifest No",
        required=True,
        copy=False,
        readonly=True,
        default="New",
    )

    manifest_type = fields.Selection(
        [
            ("internal", "Internal Transfer"),
            ("vendor", "Vendor Inbound"),
        ],
        default="internal",
        required=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("in_transit", "In Transit"),
            ("received", "Received"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
    )

    source_location_id = fields.Many2one("transport.location", string="From")
    destination_location_id = fields.Many2one("transport.location", string="To")

    vehicle_id = fields.Many2one("fleet.vehicle", string="Vehicle")
    driver_id = fields.Many2one("res.partner", string="Driver")

    leg_ids = fields.Many2many("transport.movement.leg", string="Movement Legs")
    goods_line_ids = fields.Many2many(
        "transport.goods.line",
        string="Goods Lines",
        compute="_compute_goods_lines",
    )
    estimated_cost = fields.Float()

    departure_time = fields.Datetime()
    arrival_time = fields.Datetime()

    @api.depends("leg_ids")
    def _compute_goods_lines(self):
        for manifest in self:
            manifest.goods_line_ids = manifest.leg_ids.mapped(
                "movement_id.booking_id.goods_line_ids"
            )

    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("transport.manifest") or "New"
            )
            return super().create(vals)

    # ---Actions ---------------------------
    def action_confirm(self):
        for manifest in self:
            if manifest.state != "draft":
                continue

            if not manifest.vehicle_id:
                raise ValidationError("Please assign a vehicle before confirming.")

            if not manifest.driver_id:
                raise ValidationError("Please assign a driver before confirming.")

            if not manifest.leg_ids:
                raise ValidationError("Manifest must have at least one movement leg.")

            if not manifest.goods_line_ids:
                raise ValidationError("Manifest must contain goods.")

            manifest.state = "confirmed"
