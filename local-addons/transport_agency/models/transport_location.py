from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TransportLocation(models.Model):
    _name = "transport.location"
    _description = "Transport Location"
    _rec_name = "display_name"

    # ---------------------------------------------------------
    # BASIC INFO
    # ---------------------------------------------------------
    name = fields.Char(string="Name", required=True)
    code = fields.Char(
        string="Short Code",
        help="3–6 character code used in routing and documents",
    )

    address = fields.Text(string="Address")

    city_id = fields.Many2one("transport.city", string="City", required=True)

    state_id = fields.Many2one(
        "res.country.state",
        related="city_id.state_id",
        store=True,
    )

    country_id = fields.Many2one(
        "res.country",
        related="city_id.country_id",
        store=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer / Agency",
        help="Required for customer or third-party locations",
    )

    # ---------------------------------------------------------
    # OWNERSHIP (LEGAL / COMMERCIAL)
    # ---------------------------------------------------------
    owner_type = fields.Selection(
        [
            ("own", "Own"),
            ("customer", "Customer"),
            ("third_party", "Third Party (Courier / Transporter)"),
        ],
        string="Ownership",
        required=True,
        default="customer",
    )

    # ---------------------------------------------------------
    # ROUTING ROLE (NETWORK STRUCTURE)
    # ---------------------------------------------------------
    routing_type = fields.Selection(
        [
            ("hub", "Hub"),
            ("spoke", "Spoke"),
        ],
        string="Network Role",
        required=True,
        default="spoke",
        help="Hub = central operational hub, Spoke = pickup/delivery points",
    )

    # ---------------------------------------------------------
    # OPERATIONAL ROLE (REAL WORLD)
    # This field is used for routing, leg generation, and TMS logic
    # ---------------------------------------------------------
    operational_type = fields.Selection(
        [
            ("hub", "Hub Operations"),
            ("pickup_point", "Pickup "),
            ("delivery_point", "Delivery"),
            ("handover_point", "Handover"),
        ],
        string="Operational Role",
        required=True,
        default="pickup_point",
        help="What your team does at this location",
    )

    facility_type = fields.Selection(
        [
            ("warehouse", "Warehouse / Hub"),
            ("customer_site", "Customer Address"),
            ("railway", "Railway Station"),
            ("airport", "Airport"),
            ("bus_stand", "Bus Stand"),
            ("dock", "Dock / Port"),
            ("yard", "Open Yard"),
        ],
        string="Category",
        help="Physical nature of this location",
    )

    # ---------------------------------------------------------
    # RESPONSIBILITY CONTROL
    # ---------------------------------------------------------
    is_handover_point = fields.Boolean(
        string="Handover Point",
        help=(
            "Marks responsibility boundary. "
            "Movement plans can start or end here, "
            "but routing will NOT auto-extend beyond this point."
        ),
    )

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------
    active = fields.Boolean(default=True)

    # ---------------------------------------------------------
    # DISPLAY
    # ---------------------------------------------------------
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    # ---------------------------------------------------------
    # COMPUTES
    # ---------------------------------------------------------
    @api.depends("name", "city_id")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f"{rec.name} - {rec.city_id.name}" if rec.city_id else rec.name
            )

    # ---------------------------------------------------------
    # ONCHANGE
    # ---------------------------------------------------------
    @api.onchange("owner_type")
    def _onchange_owner_type(self):
        """
        Ownership should not force routing hubs.
        """
        if self.owner_type == "own":
            self.routing_type = "hub"
        else:
            self.routing_type = "spoke"

    # ---------------------------------------------------------
    # VALIDATIONS
    # ---------------------------------------------------------
    @api.onchange("owner_type", "operational_type")
    def _onchange_owner_and_operation(self):
        for rec in self:
            # Reset first (important)
            rec.is_handover_point = False

            # -------------------------
            # CUSTOMER LOCATIONS
            # -------------------------
            if rec.owner_type == "customer":
                rec.routing_type = "spoke"
                rec.operational_type = "pickup_point"

            # -------------------------
            # THIRD PARTY LOCATIONS
            # -------------------------
            elif rec.owner_type == "third_party":
                rec.routing_type = "spoke"

                # Handover only when operational pickup/drop
                if rec.operational_type in ("pickup_point", "drop_point"):
                    rec.is_handover_point = True

            # -------------------------
            # OWN LOCATIONS
            # -------------------------
            elif rec.owner_type == "own":
                # Do NOT force hub
                rec.is_handover_point = False

    @api.constrains("owner_type", "partner_id")
    def _check_partner_requirement(self):
        for rec in self:
            if rec.owner_type in ("customer", "third_party") and not rec.partner_id:
                raise ValidationError(
                    "Customer or Third-Party locations must have a linked partner."
                )

    @api.constrains("is_handover_point", "routing_type")
    def _check_handover_rules(self):
        for rec in self:
            if rec.is_handover_point and rec.routing_type == "hub":
                raise ValidationError("Handover points cannot be routing hubs.")

    @api.constrains("operational_type", "owner_type")
    def _check_operational_validity(self):
        for rec in self:

            # if rec.owner_type == "own" and rec.operational_type != "hub":
            #     raise ValidationError("Own locations must have operational type 'Hub'.")

            if rec.owner_type == "customer" and rec.operational_type == "hub":
                raise ValidationError(
                    "Customer locations cannot be operational hubs by default."
                )

    @api.constrains("routing_type", "owner_type")
    def _check_routing_hub(self):
        for rec in self:
            if rec.routing_type == "hub" and rec.owner_type != "own":
                raise ValidationError(
                    "Only own locations can be routing hubs by default. "
                    "Use admin override for exceptions."
                )

    @api.constrains("operational_type", "facility_type")
    def _check_operational_vs_facility(self):
        for rec in self:
            # pickup_point should not be hub
            if (
                rec.operational_type == "pickup_point"
                and rec.facility_type == "warehouse"
            ):
                raise ValidationError(
                    "Pickup points should not be marked as warehouse."
                )
            # hub must be own
            if rec.operational_type == "hub" and rec.owner_type != "own":
                raise ValidationError("Only own locations can be operational hubs.")

    # ---------------------------------------------------------
    # CREATE HOOK (SAFE)
    # ---------------------------------------------------------
    def unlink(self):
        for rec in self:
            used = self.env["transport.movement"].search_count(
                [("location_ids", "in", rec.id)]
            )
            if used:
                raise ValidationError(
                    "Location is already used in movements and cannot be deleted."
                )
        return super().unlink()

    @api.model
    def create(self, vals):
        rec = super().create(vals)

        # IMPORTANT:
        # No auto route creation here.
        # Routes must be explicit via transport.route.template

        return rec
