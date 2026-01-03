from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class TransportHubMovement(models.Model):
    _name = "transport.hub.inventory"
    _description = "Hub Goods Inventory (Ledger)"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "transport.hub.inventory"
        ),
    )

    date = fields.Datetime(
        string="Date",
        default=fields.Datetime.now,
        required=True,
    )

    booking_id = fields.Many2one(
        "transport.booking",
        string="Booking",
        index=True,
        ondelete="restrict",
    )

    hub_id = fields.Many2one(
        "transport.location",
        string="Hub",
        required=True,
        domain="[('owner_type','=','own')]",
        index=True,
    )

    movement_type = fields.Selection(
        [
            ("in", "Inward"),
            ("out", "Outward"),
        ],
        required=True,
        index=True,
    )

    source_location_id = fields.Many2one(
        "transport.location",
        string="From Location",
    )

    destination_location_id = fields.Many2one(
        "transport.location",
        string="To Location",
    )

    # -- Good detail
    goods_type_id = fields.Many2one(
        "transport.goods.type",
        string="Goods Type",
        required=True,
        ondelete="cascade",
    )
    goods_description = fields.Char(string="Description")
    qty = fields.Float(string="Quantity")
    weight = fields.Float(string="Weight")
    unit_id = fields.Many2one("uom.uom", string="Unit", required=True)

    remarks = fields.Text()

    user_id = fields.Many2one(
        "res.users",
        string="Recorded By",
        default=lambda self: self.env.user,
        readonly=True,
    )

    state = fields.Selection(
        [
            ("valid", "Valid"),
            ("cancelled", "Cancelled"),
        ],
        default="valid",
    )

    # ==========================================================
    # CORE INVENTORY UPDATE METHOD
    # ==========================================================
    @api.model
    def update_hub_inventory(
        self,
        *,
        movement_type,
        hub,
        booking,
        goods_lines,
        source_location=None,
        destination_location=None,
        remarks=None,
    ):
        """
        Generic Hub Inventory Creator

        movement_type: 'in' or 'out'
        hub: transport.location (hub)
        booking: transport.booking
        goods_lines: iterable of goods lines (booking line / manifold line)
        """

        if movement_type not in ("in", "out"):
            raise UserError("Invalid movement type")

        if not hub:
            raise UserError("Hub is required for inventory movement")

        if not booking:
            raise UserError("Booking is required for inventory movement")

        if not goods_lines:
            raise UserError("No goods lines provided")

        inventory_records = []

        for line in goods_lines:
            if not line.goods_type_id:
                raise UserError("Goods type missing in line")

            inventory_records.append(
                {
                    "booking_id": booking.id,
                    "hub_id": hub.id,
                    "movement_type": movement_type,
                    "source_location_id": (
                        source_location.id if source_location else False
                    ),
                    "destination_location_id": (
                        destination_location.id if destination_location else False
                    ),
                    "goods_type_id": line.goods_type_id.id,
                    "goods_description": getattr(line, "description", False)
                    or getattr(line, "goods_description", False),
                    "qty": line.qty,
                    "weight": getattr(line, "charged_weight", line.charged_weight),
                    "unit_id": line.unit_id.id,
                    "remarks": remarks,
                    "state": "valid",
                }
            )

        return self.create(inventory_records)
