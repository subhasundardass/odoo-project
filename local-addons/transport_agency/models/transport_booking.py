from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
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

    risk_type = fields.Selection(
        [
            ("owner", "Owner's Risk"),
            ("carrier", "Carrier's Risk"),
        ],
        string="Risk Coverage",
        required=True,
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
    freight_amount = fields.Monetary(string="Charged Amount")
    advance_amount = fields.Monetary(currency_field="currency_id", default=0.0)
    balance_amount = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_balance",
        store=True,
    )
    docket_charge = fields.Monetary(currency_field="currency_id", default=0)
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

    route_template_id = fields.Many2one(
        "transport.route.template",
        string="Route Template",
        help="Optional: Predefined route template to generate movement legs.",
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("in_transit", "In Transit"),
            ("delivered", "Delivered"),
            ("cancelled", "Cancelled"),
            ("delivery_failed", "Delivery Failed"),
        ],
        default="draft",
        string="Status",
        tracking=True,
    )
    movement_id = fields.Many2one("transport.movement", string="Movement")
    movement_leg_ids = fields.One2many(
        "transport.movement.leg",
        compute="_compute_movement_legs",
        string="Movement Legs",
    )

    note = fields.Text()

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

    def action_cancel(self):
        for rec in self:
            if rec.state == "delivered":
                raise ValidationError(_("Delivered bookings cannot be cancelled."))
            rec.state = "cancelled"
            rec.message_post(body="❌ Booking Cancelled")

    def action_make_draft(self):
        for rec in self:
            # if not self.env.user.has_group("your_module_name.group_transport_manager"):
            #     raise ValidationError(_("Only Transport Managers can revert to Draft."))

            # Optional safeguard: remove movement when reverting
            if self.movement_id:
                self.movement_id.unlink()
                self.movement_id = False

            if rec.state == "delivered":
                raise ValidationError(_("Delivered bookings cannot be reverted."))

            rec.state = "draft"
            rec.message_post(body="↩️ Booking moved back to Draft")

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        self.pickup_location_id = False
        self.delivery_location_id = False

    # added later----------------------------
    pickup_location_id = fields.Many2one(
        "transport.location",
        string="Pickup Location",
        domain="[('partner_id','=',partner_id), ('location_type','=','spoke')]",
        required=True,
    )

    delivery_location_id = fields.Many2one(
        "transport.location",
        string="Delivery Location",
        domain="[('partner_id','=',partner_id), ('location_type','=','spoke')]",
        required=True,
    )

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

        # Create movement
        movement = booking.env["transport.movement"].create(
            {
                "pickup_location_id": booking.pickup_location_id.id,
                "delivery_location_id": booking.delivery_location_id.id,
                "customer_id": booking.partner_id.id,  # IMPORTANT
                # add more fields if required
            }
        )

        # -----------------------------
        # Generate legs (Template > BFS)
        # -----------------------------
        if booking.route_template_id:
            movement.route_template_id = booking.route_template_id.id
            movement.action_apply_route_template()  # template legs
        else:
            movement.action_generate_legs()  # BFS legs

        # Link movement to booking if needed
        booking.movement_id = movement.id

        if not booking.goods_line_ids:
            raise ValidationError("Cannot confirm without Goods details.")

        # create movement...
        if not movement.leg_ids:
            raise ValidationError(
                "Movement legs could not be generated. Check route configuration."
            )

        # update state
        booking.state = "confirmed"
        # booking.message_post(body=_("✅ Booking Confirmed"))

        return True


# ----------------------------
# Delivery Workflow
# -------------------------------
delivery_ids = fields.One2many(
    "transport.delivery",
    "booking_id",
    string="Deliveries",
)
