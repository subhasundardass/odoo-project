from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from lxml import etree


class TransportInboundManifest(models.Model):
    """
    Inbound Manifest represents a consolidated shipment received
    from a third-party transporter (3PL) or carrier.

    Examples:
    - Blue Dart drops multiple consignments at Hub
    - Goods received at Railway Station / Bus Stand / Airport
    - Mixed destinations received in a single arrival

    One Inbound Manifest can contain multiple consignments
    meant for different final delivery locations.
    """

    _name = "transport.inbound.manifest"
    _description = "Inbound 3PL Manifest"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "arrival_date desc, id desc"

    # ---------------------------------------------------------
    # Identification
    # ---------------------------------------------------------
    name = fields.Char(
        string="Inbound Manifest No",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="3PL / Transporter",
        required=True,
        tracking=True,
        domain=[("is_transporter", "=", True)],
        help="Third-party transporter (Blue Dart, VRL, etc.)",
    )

    partner_manifest_no = fields.Char(
        string="Carrier Manifest No",
        required=True,
        tracking=True,
        help="Manifest / CN No provided by the transporter",
    )

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )

    # ---------------------------------------------------------
    # Arrival Information
    # ---------------------------------------------------------
    arrival_location_id = fields.Many2one(
        "transport.location",
        string="Arrival Location",
        required=True,
        tracking=True,
        domain="""
    [
        ('owner_type', '=', 'own'),
        ('routing_type', '=', 'spoke'),
        ('operational_type', '=', 'pickup_point'),
        ('is_handover_point', '=', True),
    ]
    """,
        help="External location where third-party hands over goods",
    )

    arrival_date = fields.Datetime(
        string="Arrival Date & Time",
        required=True,
        tracking=True,
    )

    route_plan_id = fields.Many2one(
        "transport.route.plan",
        string="Movement Plan",
        copy=False,
        ondelete="restrict",
        tracking=True,
        required=True,
        help="Movement plan generated from this inbound manifest for onward transportation",
    )
    # receiving_hub_id = fields.Many2one(
    #     "transport.location",
    #     string="Receiving Hub",
    #     required=True,
    #     tracking=True,
    #     domain="[('routing_type', '=', 'hub')]",
    #     help="Internal hub where goods are finally received and processed",
    # )

    # ---------------------------------------------------------
    # Lines (Consignments)
    # ---------------------------------------------------------
    line_ids = fields.One2many(
        "transport.inbound.manifest.line",
        "manifest_id",
        string="Inbound Consignments",
        copy=False,
    )

    total_qty = fields.Integer(
        compute="_compute_totals",
        string="Total Qty",
        store=True,
    )

    total_weight = fields.Float(
        compute="_compute_totals",
        string="Total Weight",
        store=True,
    )

    # ---------------------------------------------------------
    # State Management
    # ---------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("booked", "Booking Generated"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )

    is_booked = fields.Boolean(default=False)

    # ---------------------------------------------------------
    # Sequence
    # ---------------------------------------------------------
    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("transport.inbound.manifest")
                or "New"
            )
        return super().create(vals)

    # ---------------------------------------------------------
    # Computations
    # ---------------------------------------------------------
    @api.depends("line_ids.qty", "line_ids.weight")
    def _compute_totals(self):
        for rec in self:
            rec.total_qty = sum(rec.line_ids.mapped("qty"))
            rec.total_weight = sum(rec.line_ids.mapped("weight"))

    # ---------------------------------------------------------
    # Constraints & Validations
    # ---------------------------------------------------------
    @api.constrains("arrival_date")
    def _check_arrival_date(self):
        for rec in self:
            if rec.arrival_date and rec.arrival_date > fields.Datetime.now():
                raise ValidationError("Arrival date cannot be in the future.")

    @api.constrains("line_ids")
    def _check_lines(self):
        for rec in self:
            if rec.state != "draft" and not rec.line_ids:
                raise ValidationError(
                    _("Inbound Manifest must have at least one line.")
                )

    # ---------------------------------------------------------
    # Lifecycle Actions
    # ---------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft manifests can be confirmed.")

            if not rec.line_ids:
                raise UserError("You cannot confirm a manifest without consignments.")

            if not rec.route_plan_id:
                raise ValidationError("Please select a Route Plan before confirming.")

            missing = rec.line_ids.filtered(
                lambda l: not l.qty or not l.weight or not l.delivery_location_id
            )
            if missing:
                raise UserError(
                    "All consignment lines must have Quantity, Weight, Delivery location"
                )

            rec.state = "confirmed"

    def action_return_to_draft(self):
        for rec in self:
            if rec.state != "confirmed":
                continue

            if rec.is_booked:
                raise UserError(
                    "You cannot return to Draft because bookings are already created."
                )

            rec.state = "draft"

    def action_create_booking(self):
        for manifest in self:
            # Check if the manifest is confirmed
            if manifest.state != "confirmed":
                raise UserError(
                    "Booking can only be created when the manifest is confirmed."
                )

            # Check if there are any lines
            if not manifest.line_ids:
                raise UserError(
                    "Cannot create booking because there are no consignment lines."
                )

            # Prevent double booking
            # if hasattr(manifest, "booking_id") and manifest.booking_id:
            #     raise UserError("Booking already created for this manifest.")

            self._generate_bookings_from_line()
            # manifest.write(
            #     {
            #         "state": "booked",
            #         "is_booked": True,
            #     }
            # )

        return True

    def action_cancel_manifest(self):
        for manifest in self:
            # Only allow cancelling if not already cancelled
            if manifest.state == "cancelled":
                raise UserError("Manifest is already cancelled.")

            # Reset booked flag
            manifest.is_booked = False

            # Update state
            manifest.state = "cancelled"

            # Persist changes
            manifest.write(
                {
                    "state": "cancelled",
                    "is_booked": False,
                }
            )

    # ---------------------------------------------------------
    # Functions
    # ---------------------------------------------------------
    def _generate_bookings_from_line(self):
        """
        Generate separate bookings for each delivery location based on manifest lines.
        """
        Booking = self.env["transport.booking"]
        GoodsLine = self.env["transport.goods.line"]

        for manifest in self:
            # ----------------------------
            # Preconditions
            # ----------------------------
            if manifest.state != "confirmed":
                raise UserError(
                    "Booking can only be created when the manifest is confirmed."
                )

            if not manifest.line_ids:
                raise UserError(
                    "Cannot create booking because there are no consignment lines."
                )

            if manifest.is_booked:
                raise UserError("Booking has already been created for this manifest.")

            if not manifest.route_plan_id:
                raise UserError("Route plan is required to create booking.")

            # -----------------------------------
            # Group lines by delivery location
            # -----------------------------------
            grouped_lines = {}
            for line in manifest.line_ids:
                if not line.delivery_location_id:
                    raise UserError("Delivery location missing in one of the lines.")

                grouped_lines.setdefault(line.delivery_location_id.id, []).append(line)

            # ----------------------------
            # Create bookings per delivery location
            # ----------------------------
            for delivery_location_id, lines in grouped_lines.items():
                delivery_location = self.env["transport.location"].browse(
                    delivery_location_id
                )

                # 🔹 Calculate freight
                freight_amount = sum(line.amount for line in lines)

                # docket no
                for line in lines:
                    docket_no = line.goods_docket_number

                booking_vals = {
                    # -----------------------------
                    # Parties
                    # -----------------------------
                    "partner_id": manifest.partner_id.id,  # 3PL / Transporter (if exists)
                    "docket_no": docket_no or f"{manifest.name}",
                    # -----------------------------
                    # Planning & Locations
                    # -----------------------------
                    "route_plan_id": manifest.route_plan_id.id,
                    "pickup_location_id": manifest.arrival_location_id.id,
                    "delivery_location_id": delivery_location.id,
                    # -----------------------------
                    # Commercial
                    # -----------------------------
                    "freight_amount": freight_amount,
                    "currency_id": manifest.company_id.currency_id.id,
                    # -----------------------------
                    # Source tracking
                    # -----------------------------
                    # "booking_source": "inbound_manifest",
                    # "booking_source_ref": f"{manifest._name},{manifest.id}",
                    # "inbound_manifest_id": manifest.id,
                    # -----------------------------
                    # Dates
                    # -----------------------------
                    # "pickup_date": manifest.arrival_date,
                    # -----------------------------
                    # Company
                    # -----------------------------
                    # "company_id": manifest.company_id.id,
                }
                # ✅ VERY IMPORTANT CONTEXT
                booking = Booking.with_context(booking_from_manifold=True).create(
                    booking_vals
                )

                # Create booking lines
                for line in lines:
                    GoodsLine.create_transport_good_line(
                        booking_id=booking.id,
                        goods_type_id=line.goods_type_id.id,
                        unit_id=line.unit_id.id,
                        qty=line.qty,
                        actual_weight=line.weight,
                        charged_weight=line.weight,  # or your rule
                    )

            manifest.write({"is_booked": True, "state": "booked"})
