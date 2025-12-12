from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TransportMovementLeg(models.Model):
    _name = "transport.movement.leg"
    _description = "Transport Movement Leg"
    _order = "sequence asc"

    movement_id = fields.Many2one(
        "transport.movement",
        string="Movement",
        required=True,
        ondelete="cascade",
    )

    sequence = fields.Integer(
        string="Leg Sequence",
        default=1,
        help="Order of execution: 1 = first leg, 2 = next leg, etc.",
    )

    from_location_id = fields.Many2one(
        "transport.location",
        string="From Location",
        required=True,
    )

    to_location_id = fields.Many2one(
        "transport.location",
        string="To Location",
        required=True,
    )

    leg_type = fields.Selection(
        [
            ("pickup", "Pickup → Hub"),
            ("hub_to_hub", "Hub → Hub"),
            ("hub_to_spoke", "Hub → Spoke"),
            ("spoke_delivery", "Spoke Delivery"),
        ],
        string="Leg Type",
        compute="_compute_leg_type",
        store=True,
    )

    carrier_type = fields.Selection(
        [
            ("own", "Own Transport"),
            ("third_party", "Third Party"),
        ],
        string="Carrier",
        required=True,
        default="own",
        help="Specify if this leg is done by your transport or outsourced.",
    )

    responsible_by = fields.Selection(
        [
            ("own", "Own Transport"),
            ("third_party", "Third Party"),
        ],
        string="Responsibility",
    )

    third_party_partner_id = fields.Many2one(
        "res.partner",
        string="3rd Party Vendor",
        help="Required only if carrier is third-party.",
    )

    distance_km = fields.Float(string="Distance (KM)")

    travel_time_hours = fields.Float(string="Expected Duration (Hours)")

    cost = fields.Float(string="Cost")

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_transit", "In Transit"),
            ("completed", "Completed"),
        ],
        default="pending",
        string="Status",
    )

    # -------------------------------------
    # AUTO DETECT LEG TYPE
    # -------------------------------------
    @api.depends("from_location_id", "to_location_id")
    def _compute_leg_type(self):
        for rec in self:
            if not rec.from_location_id or not rec.to_location_id:
                rec.leg_type = False
                continue

            f, t = rec.from_location_id, rec.to_location_id

            if f.location_type == "spoke" and t.location_type == "hub":
                rec.leg_type = "pickup"
            elif f.location_type == "hub" and t.location_type == "hub":
                rec.leg_type = "hub_to_hub"
            elif f.location_type == "hub" and t.location_type == "spoke":
                rec.leg_type = "hub_to_spoke"
            elif f.location_type == "spoke" and t.location_type == "spoke":
                rec.leg_type = "spoke_delivery"
            else:
                rec.leg_type = False

    # -------------------------------------
    # BUSINESS RULES
    # -------------------------------------
    @api.constrains("carrier_type", "third_party_partner_id")
    def _check_third_party_rules(self):
        for rec in self:
            if rec.carrier_type == "third_party" and not rec.third_party_partner_id:
                raise ValidationError("Third Party Vendor must be selected.")

    @api.constrains("from_location_id", "to_location_id")
    def _check_location_logic(self):
        for rec in self:
            if rec.from_location_id == rec.to_location_id:
                raise ValidationError("From and To Locations cannot be the same.")

            # Prevent invalid combinations
            if (
                rec.from_location_id.owner_type == "customer"
                and rec.to_location_id.owner_type == "customer"
            ):
                raise ValidationError(
                    "Customer to Customer movement is not valid directly."
                )

    # -------------------------------------
    # AUTO-NAME EACH LEG
    # -------------------------------------
    name = fields.Char(
        string="Leg Name",
        compute="_compute_leg_name",
        store=True,
    )

    @api.depends("sequence", "from_location_id", "to_location_id")
    def _compute_leg_name(self):
        for rec in self:
            if rec.from_location_id and rec.to_location_id:
                rec.name = f"Leg {rec.sequence}: {rec.from_location_id.name} → {rec.to_location_id.name}"
            else:
                rec.name = f"Leg {rec.sequence}"
