from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class TransportBooking(models.Model):
    _name = "transport.booking"
    _description = "Transport Booking (LR)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "id desc"

    invoice_id = fields.Many2one("account.move", string="Invoice")  # Invoice model
    name = fields.Char(
        string="Booking Number",
        required=True,
        copy=False,
        readonly=True,
        default="New",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        domain=[("customer_rank", ">", 0)],
        context={"default_customer_rank": 1},
    )

    # --
    docket_no = fields.Char(required=True)
    sales_person = fields.Char()

    risk_type = fields.Selection(
        [
            ("owner", "Owner's Risk"),
            ("carrier", "Carrier's Risk"),
        ],
        string="Risk Coverage",
        # required=True,
        default="owner",
    )
    dispatch_mode = fields.Selection(
        [
            ("road", "Road"),
            ("air", "Air"),
            ("rail", "Rail"),
            ("sea", "Sea"),
            ("courier", "Courier"),
            ("express", "Express"),
        ],
        string="Mode of Dispatch",
        default="road",
        required=True,
    )

    # Goods Line
    goods_line_ids = fields.One2many(
        "transport.goods.line", "booking_id", string="Goods Details"
    )

    # Billing Field
    freight_amount = fields.Monetary(
        string="Charged Amount",
        required=True,
    )
    advance_amount = fields.Monetary(currency_field="currency_id", default=0.0)
    balance_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_balance",
        store=True,
    )
    docket_charge = fields.Monetary(currency_field="currency_id", default=100)
    handling_charge = fields.Monetary(currency_field="currency_id", default=0)
    other_charge = fields.Monetary(currency_field="currency_id", default=0)
    fuel_surcharge = fields.Monetary(currency_field="currency_id", default=0)
    value_surcharge = fields.Monetary(currency_field="currency_id", default=0)
    oda_charge = fields.Monetary(string="ODA Charge")
    gst_rate = fields.Selection(
        [
            ("0", "0%"),
            ("5", "5%"),
            ("12", "12%"),
            ("18", "18%"),
        ],
        string="GST %",
        default="5",
        required=True,
    )
    gst_amount = fields.Monetary(
        string="GST Amount", compute="_compute_gst", store=True
    )

    total_amount = fields.Monetary(
        string="Total Amount", compute="_compute_gst", store=True
    )

    # route_template_id = fields.Many2one(
    #     "transport.route.template",
    #     string="Route Template",
    #     help="Optional: Predefined route template to generate movement legs.",
    # )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("planned", "Planned"),
            ("in_transit", "In Transit"),
            ("delivered", "Delivered"),
            ("cancelled", "Cancelled"),
            ("invoiced", "Invoiced"),
            ("delivery_failed", "Delivery Failed"),
        ],
        default="draft",
        string="Status",
        tracking=True,
    )

    pickup_location_id = fields.Many2one(
        "transport.location",
        string="Pickup Location",
        required=True,
    )

    delivery_location_id = fields.Many2one(
        "transport.location",
        string="Delivery Location",
        domain="[('partner_id','=',partner_id), ('location_type','=','spoke')]",
        required=True,
    )

    ##-- Route Plan --------------------
    route_plan_id = fields.Many2one(
        "transport.route.plan",
        string="Movement Plan",
        required=True,
        ondelete="restrict",
    )

    route_plan_line_ids = fields.One2many(
        comodel_name="transport.route.plan.line",
        inverse_name="route_plan_id",
        related="route_plan_id.line_ids",
        readonly=True,
    )

    ##-- Movement Legs --------------------
    movement_id = fields.Many2one(
        "transport.movement",
        string="Movement",
    )
    movement_leg_ids = fields.One2many(
        "transport.movement.leg",
        compute="_compute_movement_legs",
        string="Movement Legs",
        readonly=True,
    )

    note = fields.Text()

    ##-- Delivery --------------------
    pod_file = fields.Binary(required=True)
    pod_filename = fields.Char()
    received_by = fields.Char(
        string="Received By",
        tracking=True,
    )
    delivery_date = fields.Datetime(
        string="Delivered On",
        readonly=True,
    )
    delivery_remark = fields.Text()

    ##---Booking source
    booking_source_ref = fields.Reference(
        selection=[
            ("transport.forwarding.manifold", "Manifold"),
            ("transport.booking", "Booking"),
        ],
        string="Source Document",
        ondelete="cascade",
    )

    all_legs_completed = fields.Boolean(
        string="All Legs Completed",
        compute="_compute_all_legs_completed",
        store=True,
    )

    # --------------------------------------------------------
    # APIS
    # --------------------------------------------------------
    #
    @api.constrains(
        "partner_id",
        "pickup_location_id",
        "delivery_location_id",
        "goods_line_ids",
        "freight_amount",
    )
    def _check_required_fields(self):

        for rec in self:
            if not rec.partner_id:
                raise ValidationError("Customer is required.")

            if not rec.pickup_location_id:
                raise ValidationError("Pickup Location is required.")

            if not rec.delivery_location_id:
                raise ValidationError("Delivery Location is required.")

            if not rec.goods_line_ids:
                if self.env.context.get("booking_from_manifold"):
                    continue
                raise ValidationError("At least one Goods/Material entry is required.")

            if rec.freight_amount <= 0:
                raise ValidationError("Freight amount must be greater than 0.")

    @api.constrains("pickup_location_id", "delivery_location_id")
    def _check_location_difference(self):
        for rec in self:
            if rec.pickup_location_id and rec.delivery_location_id:
                if rec.pickup_location_id.id == rec.delivery_location_id.id:
                    raise ValidationError(
                        "Pickup and Delivery Location cannot be the same."
                    )

    @api.constrains("pickup_location_id", "delivery_location_id", "partner_id")
    def _check_location_customer(self):
        for rec in self:
            if self.env.context.get("booking_from_manifold"):
                continue
            if rec.pickup_location_id.partner_id != rec.partner_id:
                raise ValidationError("Pickup location does not belong to the customer")

            if rec.delivery_location_id.partner_id != rec.partner_id:
                raise ValidationError(
                    "Delivery location does not belong to the customer"
                )

    @api.constrains("qty", "actual_weight", "charged_weight", "goods_value")
    def _check_goods_line(self):
        for line in self:
            if line.qty <= 0:
                raise ValidationError("Quantity must be greater than 0.")

            if line.actual_weight < 0:
                raise ValidationError("Actual weight cannot be negative.")

            if line.charged_weight < 0:
                raise ValidationError("Charged weight cannot be negative.")

            if line.charged_weight < line.actual_weight:
                raise ValidationError(
                    "Charged weight cannot be less than actual weight."
                )

            if line.goods_value < 0:
                raise ValidationError("Goods value cannot be negative.")

    @api.constrains(
        "freight_amount",
        "advance_amount",
        "docket_charge",
        "handling_charge",
        "other_charge",
        "fuel_surcharge",
        "value_surcharge",
    )
    def _check_amounts(self):
        for rec in self:
            for field in [
                "freight_amount",
                "advance_amount",
                "docket_charge",
                "handling_charge",
                "other_charge",
                "fuel_surcharge",
                "value_surcharge",
            ]:
                if getattr(rec, field) < 0:
                    raise ValidationError(
                        f"{field.replace('_', ' ').title()} cannot be negative."
                    )

    @api.depends(
        "freight_amount",
        "value_surcharge",
        "docket_charge",
        "handling_charge",
        "oda_charge",
        "fuel_surcharge",
        "other_charge",
        "gst_rate",
    )
    def _compute_gst(self):
        for rec in self:
            base_amount = (
                rec.freight_amount
                + rec.value_surcharge
                + rec.docket_charge
                + rec.handling_charge
                + rec.oda_charge
                + rec.fuel_surcharge
                + rec.other_charge
            )

            gst_percent = float(rec.gst_rate or 0)
            rec.gst_amount = base_amount * (gst_percent / 100)
            rec.total_amount = base_amount + rec.gst_amount

    @api.depends("movement_id")
    def _compute_movement_legs(self):
        for rec in self:
            rec.movement_leg_ids = rec.movement_id.leg_ids if rec.movement_id else False

    # @api.depends("route_plan_id")
    # def _compute_route_plan_lines(self):
    #     for rec in self:
    #         rec.route_plan_line_ids = (
    #             rec.route_plan_id.line_ids if rec.route_plan_id else False
    #         )

    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "transport.booking", sequence_date=fields.Date.today()
            )
        return super().create(vals)

    @api.depends("total_amount", "advance_amount")  # total_amount is computed
    def _compute_balance(self):
        for rec in self:
            rec.balance_amount = (rec.total_amount or 0.0) - (rec.advance_amount or 0.0)

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        self.pickup_location_id = False
        self.delivery_location_id = False

    def action_cancel(self):
        for rec in self:
            if rec.state == "delivered":
                raise ValidationError(_("Delivered bookings cannot be cancelled."))
            rec.state = "cancelled"
            rec.message_post(body="❌ Booking Cancelled")

    def action_make_draft(self):
        self.ensure_one()

        if self.state in ("in_transit", "delivered"):
            raise ValidationError("Cannot revert once transit has started.")

        HubInventory = self.env["transport.hub.inventory"].sudo()
        Movement = self.env["transport.movement"].sudo()

        # 1️⃣ Delete hub inventory
        hub_inventory = HubInventory.search(
            [
                ("booking_id", "=", self.id),
                ("state", "=", "valid"),
            ]
        )
        if hub_inventory:
            hub_inventory.unlink()

        # 2️⃣ Delete movements and their legs
        movements = Movement.search([("booking_id", "=", self.id)])
        for move in movements:
            if move.leg_ids:
                move.leg_ids.unlink()
            move.unlink()

        # 3️⃣ Reset booking reference
        self.movement_id = False
        self.state = "draft"

        self.message_post(body="↩️ Booking reverted to Draft.")

    def action_confirm_booking(self):

        self.ensure_one()
        booking = self

        if booking.state != "draft":
            raise ValidationError(_("Only Draft bookings can be confirmed."))

        pickup = booking.pickup_location_id
        delivery = booking.delivery_location_id

        if not pickup:
            raise ValidationError("Pickup location is required")

        if not delivery:
            raise ValidationError("Delivery location is required")

        if not booking.goods_line_ids:
            raise ValidationError("Cannot confirm without Goods details.")

        if not booking.route_plan_line_ids:
            raise ValidationError("Cannot confirm without Rote plan.")

        # -----------------------------
        # Create movement
        # -----------------------------
        movement = booking.env["transport.movement"].create(
            {
                "booking_id": booking.id,
                "route_plan_id": booking.route_plan_id.id,
                "pickup_location_id": booking.pickup_location_id.id,
                "delivery_location_id": booking.delivery_location_id.id,
                "customer_id": booking.partner_id.id,  # IMPORTANT
                "state": "confirmed",
                # add more fields if required
            }
        )
        # Link movement to booking if needed
        booking.movement_id = movement.id

        # update state
        booking.state = "confirmed"

        return True

    # def _update_hub_inventory(self, movement_type, hub):
    #     """
    #     Create hub movement entries goods-wise from booking lines
    #     movement_type: 'in' or 'out'
    #     """
    #     self.ensure_one()

    #     if movement_type not in ("in", "out"):
    #         raise UserError("Invalid hub movement type.")

    #     if not self.goods_line_ids:
    #         raise UserError("Booking has no goods lines.")

    #     if (
    #         self.pickup_location_id
    #         and self.pickup_location_id.owner_type == "own"
    #         and self.pickup_location_id.location_type == "hub"
    #     ):
    #         hub = self.pickup_location_id
    #     else:
    #         hub = self.pickup_location_id.parent_hub_id

    #     if not hub:
    #         raise UserError(
    #             f"Hub not defined for this booking.{self.pickup_location_id.id}"
    #         )

    #     HubMovement = self.env["transport.hub.inventory"]

    #     existing = self.env["transport.hub.inventory"].search_count(
    #         [
    #             ("booking_id", "=", self.id),
    #             ("hub_id", "=", hub.id),
    #             ("movement_type", "=", movement_type),
    #             ("state", "=", "valid"),
    #         ]
    #     )

    #     if existing:
    #         raise UserError("Hub inventory already created for this booking.")

    #     for line in self.goods_line_ids:
    #         # if not line.goods_line_ids:
    #         #     continue

    #         HubMovement.create(
    #             {
    #                 "booking_id": self.id,
    #                 "hub_id": hub.id,
    #                 "goods_type_id": line.goods_type_id.id,
    #                 "qty": line.qty,
    #                 "weight": line.actual_weight,
    #                 "unit_id": line.unit_id.id,
    #                 "movement_type": movement_type,
    #                 "goods_description": line.description,
    #                 "source_location_id": (
    #                     self.pickup_location_id.id if movement_type == "in" else hub.id
    #                 ),
    #                 "destination_location_id": (
    #                     hub.id
    #                     if movement_type == "in"
    #                     else self.delivery_location_id.id
    #                 ),
    #                 "remarks": f"{movement_type.upper()} via Booking {self.name}",
    #             }
    #         )

    # def action_mark_arrived(self):
    #     for leg in self:
    #         if leg.state != "in_transit":
    #             raise ValidationError("Leg must be In Transit to arrive.")
    #         leg.state = "arrived"

    def action_start_transit(self):
        self.ensure_one()

        if self.state == "in_transit":
            raise ValidationError("Booking is already in transit.")

        if self.state != "confirmed":
            raise ValidationError("Only confirmed bookings can start transit.")

        if not self.movement_id or not self.movement_id.leg_ids:
            raise ValidationError("Movement legs not found.")

        # Change booking state
        self.write({"state": "in_transit"})

        # only first leg
        # Start first leg only
        first_leg = (
            self.movement_id.leg_ids.sorted("sequence")[0]
            if self.movement_id.leg_ids
            else False
        )
        if first_leg:
            if first_leg.state != "pending":
                raise ValidationError(f"First leg ({first_leg.name}) is not pending.")
            first_leg.write({"state": "in_transit"})
            # Optional: create hub inventory OUT here if you want automatic pickup logging
            # self.env['transport.hub.inventory'].update_hub_inventory(...)

        self.message_post(body="🚚 Transit started.")

    def action_mark_delivered(self):
        self.ensure_one()

        if self.state == "delivered":
            raise ValidationError("This booking is already delivered.")

        if self.state != "in_transit":
            raise ValidationError("Only In-Transit bookings can be delivered.")

        if not self.movement_id or not self.movement_id.leg_ids:
            raise ValidationError("No movement legs found.")

        # ------------------------------------------------
        # 1️⃣ Complete all movement legs safely
        # ------------------------------------------------
        for leg in self.movement_id.leg_ids:
            if leg.state != "completed":
                leg.action_complete_leg()

        # ------------------------------------------------
        # 2️⃣ Resolve final delivery hub
        # ------------------------------------------------
        delivery_location = self.delivery_location_id
        final_hub = (
            delivery_location.parent_hub_id
            if delivery_location.location_type != "hub"
            else delivery_location
        )

        if not final_hub:
            raise ValidationError("Final delivery hub not found.")

        # ------------------------------------------------
        # 3️⃣ Inventory OUT (FINAL delivery)
        # ------------------------------------------------
        self.env["transport.hub.inventory"].update_hub_inventory(
            movement_type="out",
            hub=final_hub,
            booking=self,
            goods_lines=self.goods_line_ids,
            source_location=final_hub,
            destination_location=delivery_location,
            remarks=f"Delivered - Booking {self.name}",
        )

        # ------------------------------------------------
        # 4️⃣ Mark booking delivered
        # ------------------------------------------------
        self.write(
            {
                "state": "delivered",
                "delivery_date": fields.Datetime.now(),
            }
        )

        # ------------------------------------------------
        # 5️⃣ Create invoice (single source)
        # ------------------------------------------------
        invoice = self._create_invoice()

        # ------------------------------------------------
        # 6️⃣ Chatter log
        # ------------------------------------------------
        self.message_post(
            body=_(
                "📦 <b>Delivered successfully</b><br/>" "🧾 Invoice Created: <b>%s</b>"
            )
            % (invoice.name if invoice else "N/A")
        )

    def action_delivery_failed(self):
        self.ensure_one()

        if self.state != "in_transit":
            raise ValidationError(
                "Delivery can be marked failed only when booking is In Transit."
            )

        # Safety: movement must exist
        if not self.movement_id:
            raise ValidationError("No movement found for this booking.")

        # Mark state
        self.state = "delivery_failed"

        # Optional audit fields
        self.delivery_date = fields.Datetime.now()
        self.delivered_by_id = self.env.user.id

        self.message_post(
            body="❌ Delivery failed. Goods are still in company custody."
        )

        return True

    def action_open_movement_legs(self):
        self.ensure_one()

        if not self.movement_id:
            raise ValidationError("No movement created for this booking.")

        return {
            "name": "Movement Legs",
            "type": "ir.actions.act_window",
            "res_model": "transport.movement.leg",
            "view_mode": "tree,form",
            "domain": [("movement_id", "=", self.movement_id.id)],
            "context": {
                "default_movement_id": self.movement_id.id,
            },
        }

    def action_open_delivery_wizard(self):
        self.ensure_one()

        if self.state != "in_transit":
            raise ValidationError("Only In Transit bookings can be delivered.")

        return {
            "name": "Confirm Delivery",
            "type": "ir.actions.act_window",
            "res_model": "transport.delivery.wizard",
            "view_mode": "form",
            "target": "new",  # ✅ THIS LINE IS THE KEY
            "context": {
                "default_booking_id": self.id,
            },
        }

    def _create_invoice(self):
        self.ensure_one()

        if self.invoice_id:
            return self.invoice_id

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_id.id,
                "invoice_date": fields.Date.today(),
                "invoice_origin": self.name,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": f"Transport Charges - {self.name}",
                            "quantity": 1,
                            "price_unit": self.total_amount,
                        },
                    )
                ],
            }
        )

        self.invoice_id = invoice.id
        return invoice

    def _log_delivery_inventory(self):
        self.ensure_one()

        destination_hub = self.destination_hub_id
        if not destination_hub:
            raise UserError("Destination hub not defined.")

        self.env["transport.hub.inventory"].update_hub_inventory(
            movement_type="out",
            hub=destination_hub,
            booking=self,
            goods_lines=self.goods_line_ids,
            remarks=f"Delivered - Booking {self.name}",
        )

    @api.depends("movement_id.leg_ids.state")
    def _compute_all_legs_completed(self):
        for booking in self:
            legs = booking.movement_id.leg_ids
            booking.all_legs_completed = all(leg.state == "completed" for leg in legs)
