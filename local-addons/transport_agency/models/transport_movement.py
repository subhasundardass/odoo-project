from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from collections import deque
import logging

_logger = logging.getLogger(__name__)


class TransportMovement(models.Model):
    _name = "transport.movement"
    _description = "Transport Shipment / Movement"
    _order = "id desc"

    name = fields.Char(
        string="Movement Number",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env["ir.sequence"].next_by_code("transport.movement"),
    )

    movement_type = fields.Selection(
        [
            ("outbound", "Outbound"),
            ("inbound", "Inbound (Third Party)"),
            ("internal", "Internal Transfer"),
        ],
        default="outbound",
        required=True,
    )

    booking_id = fields.Many2one(
        "transport.booking",
        string="Booking No",
        required=True,
        ondelete="restrict",
        index=True,
    )
    docket_no = fields.Char(
        string="Docket No",
        related="booking_id.docket_no",
        store=True,
        readonly=True,
    )

    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        help="Customer associated with this movement",
    )

    booking_date = fields.Datetime(
        related="booking_id.create_date",
        string="Booking Date",
        readonly=True,
    )

    pickup_location_id = fields.Many2one(
        "transport.location",
        string="Pickup Location",
        required=True,
    )

    delivery_location_id = fields.Many2one(
        "transport.location",
        string="Delivery Location",
        required=True,
    )

    movement_date = fields.Datetime(
        string="Movement Date",
        default=fields.Datetime.now,
        required=True,
    )

    route_plan_id = fields.Many2one(
        "transport.route.plan",
        string="Route Plan",
        required=True,
        ondelete="restrict",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("planned", "Planned"),
            ("in_transit", "In Transit"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    leg_ids = fields.One2many(
        "transport.movement.leg",
        "movement_id",
        string="Movement Legs",
        copy=True,
        default=lambda self: self.env["transport.movement.leg"],  # // Always return
    )

    total_cost = fields.Float(
        string="Total Cost",
        compute="_compute_total_cost",
        store=True,
    )

    # ----------------------------------------
    # CREATE
    # ----------------------------------------
    @api.model
    def create(self, vals):
        # Movement number
        if not vals.get("name") or vals.get("name") == "New":
            vals["name"] = (
                self.env["ir.sequence"].next_by_code(
                    "transport.movement", sequence_date=fields.Date.today()
                )
                or "New"
            )

        # Auto-fill customer from pickup if not provided
        if not vals.get("customer_id") and vals.get("pickup_location_id"):
            pickup = self.env["transport.location"].browse(vals["pickup_location_id"])
            if pickup.owner_type == "customer" and pickup.partner_id:
                vals["customer_id"] = pickup.partner_id.id
            else:
                raise ValidationError(
                    "Customer must be set for movement. Pickup location does not have a customer."
                )

        return super().create(vals)

    @api.depends("leg_ids.cost")
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum(rec.leg_ids.mapped("cost"))

    # -------------------------
    # Onchange to auto-fill customer from pickup
    # -------------------------
    @api.onchange("pickup_location_id")
    def _onchange_pickup_customer(self):
        for rec in self:
            if (
                rec.pickup_location_id
                and rec.pickup_location_id.owner_type == "customer"
            ):
                rec.customer_id = rec.pickup_location_id.partner_id

    @api.onchange("pickup_location_id", "delivery_location_id")
    def _onchange_locations(self):
        for rec in self:
            if rec.pickup_location_id == rec.delivery_location_id:
                rec.delivery_location_id = False
                return {
                    "warning": {
                        "title": "Invalid Location",
                        "message": "Pickup and delivery cannot be same",
                    }
                }

    # -------------------------
    # Apply route template to generate legs
    # -------------------------
    def action_apply_route_template(self):
        for rec in self:
            if not rec.route_template_id:
                raise ValidationError("Please select a route template first.")
            if not rec.customer_id:
                raise ValidationError("Customer is required before generating legs.")
            rec.route_template_id.generate_legs_for_movement(rec)
            rec.state = "planned"

    # ----------------------------------------
    # VALIDATIONS
    # ----------------------------------------
    @api.constrains("pickup_location_id", "delivery_location_id")
    def _check_pickup_delivery(self):
        for rec in self:
            if rec.pickup_location_id == rec.delivery_location_id:
                raise ValidationError("Pickup and Delivery cannot be the same.")

    # # --------------------PLANNED-----------------------------------------
    # # Planning / Assignment Info
    # vehicle_id = fields.Many2one(
    #     "fleet.vehicle", string="Vehicle", help="Vehicle assigned for this movement"
    # )
    # driver_id = fields.Many2one(
    #     "res.partner",
    #     string="Driver",
    #     domain=[("is_driver", "=", True)],
    #     help="Driver responsible for this movement",
    # )

    # planned_by = fields.Many2one(
    #     "res.users",
    #     string="Planned By",
    #     readonly=True,
    # )

    # planned_date = fields.Datetime(
    #     string="Planned Date",
    #     readonly=True,
    # )

    # ----------------------------------------
    # STATE ACTIONS
    # ----------------------------------------
    def action_confirm(self):
        self.state = "confirmed"

    def action_complete(self):
        for rec in self:
            # Ensure all legs are done
            incomplete = rec.leg_ids.filtered(lambda l: l.state != "completed")
            if incomplete:
                raise ValidationError(
                    "All legs must be completed before marking movement completed."
                )
        self.state = "completed"

    def action_cancel(self):
        for move in self:
            move.state = "cancelled"

            reversals = self.env["transport.hub.inventory"].search(
                [
                    ("movement_leg_id", "in", move.leg_ids.ids),
                    ("state", "=", "valid"),
                ]
            )
            reversals.write({"state": "cancelled"})

    # -------------------------------------
    # Generate Legs from Movement Plan
    # -------------------------------------
    def action_generate_legs_from_plan(self):
        for movement in self:

            # --------------------------------------------------
            # BASIC VALIDATIONS
            # --------------------------------------------------
            if movement.state != "confirmed":
                raise ValidationError("Confirm movement before generating legs.")

            if movement.leg_ids:
                raise ValidationError("Movement legs already generated.")

            plan = movement.route_plan_id
            if not plan or not plan.line_ids:
                raise ValidationError("Valid Route Plan required.")

            pickup_location = movement.pickup_location_id
            delivery_location = movement.delivery_location_id

            if not pickup_location or not delivery_location:
                raise ValidationError("Pickup and Delivery locations are required.")

            plan_lines = plan.line_ids.sorted("sequence")
            first_hub = plan_lines[0].origin_location_id
            last_hub = plan_lines[-1].destination_location_id

            legs = []
            seq = 1

            # --------------------------------------------------
            # 1️⃣ RESOLVE ACTUAL PICKUP LOCATION
            # --------------------------------------------------
            # Rules:
            # - Customer pickup → customer location
            # - Own pickup → own location
            # - Third-party pickup → same pickup point (NO remap)
            actual_pickup = pickup_location

            # ❗ Prevent invalid Customer → Customer
            if (
                actual_pickup.owner_type == "customer"
                and first_hub.owner_type == "customer"
            ):
                raise ValidationError(
                    "Customer pickup must move to a hub, not another customer."
                )

            # --------------------------------------------------
            # 2️⃣ PICKUP → FIRST HUB
            # --------------------------------------------------
            if actual_pickup != first_hub:
                legs.append(
                    (
                        0,
                        0,
                        {
                            "sequence": seq,
                            "from_location_id": actual_pickup.id,
                            "to_location_id": first_hub.id,
                        },
                    )
                )
                seq += 1

            # --------------------------------------------------
            # 3️⃣ HUB → HUB (LINEHAUL)
            # --------------------------------------------------
            for line in plan_lines:
                if line.origin_location_id == line.destination_location_id:
                    continue

                legs.append(
                    (
                        0,
                        0,
                        {
                            "sequence": seq,
                            "from_location_id": line.origin_location_id.id,
                            "to_location_id": line.destination_location_id.id,
                        },
                    )
                )
                seq += 1

            # --------------------------------------------------
            # 4️⃣ LAST HUB → DELIVERY
            # --------------------------------------------------
            if last_hub != delivery_location:
                # ❗ Prevent invalid Customer → Customer
                if (
                    last_hub.owner_type == "customer"
                    and delivery_location.owner_type == "customer"
                ):
                    raise ValidationError(
                        "Customer to Customer direct delivery is not allowed."
                    )

                legs.append(
                    (
                        0,
                        0,
                        {
                            "sequence": seq,
                            "from_location_id": last_hub.id,
                            "to_location_id": delivery_location.id,
                        },
                    )
                )

            # --------------------------------------------------
            # 5️⃣ WRITE RESULT
            # --------------------------------------------------
            movement.write(
                {
                    "leg_ids": legs,
                    "state": "planned",
                }
            )

            if movement.booking_id:
                movement.booking_id.write({"state": "planned"})
