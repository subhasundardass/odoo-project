from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class TransportMovementLeg(models.Model):
    _name = "transport.movement.leg"
    _description = "Transport Movement Leg"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence asc"

    movement_id = fields.Many2one(
        "transport.movement",
        string="Movement",
        required=True,
        ondelete="cascade",
    )
    manifest_id = fields.Many2one(
        "transport.manifest",
        string="Manifest",
        readonly=True,
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

    completed_on = fields.Datetime(
        string="Completed On",
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("planned", "Planned"),
            ("assigned", "Assigned to Manifest"),
            ("completed", "Completed"),
        ],
        default="planned",
    )

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

            if (
                rec.from_location_id.owner_type == "customer"
                and rec.to_location_id.owner_type == "customer"
            ):
                raise ValidationError("Customer to Customer movement is not allowed.")

    # -------------------------------------
    # AUTO-NAME EACH LEG
    # -------------------------------------
    name = fields.Char(
        string="Leg Name",
        compute="_compute_leg_name",
        store=True,
    )

    @api.onchange("transporter_id")
    def _onchange_transporter(self):
        # If transporter has assigned vehicle or driver, you can auto-populate
        if self.transporter_id:
            vehicle = self.env["fleet.vehicle"].search(
                [
                    ("transporter_id", "=", self.transporter_id.id),
                    ("state", "=", "available"),
                ],
                limit=1,
            )
            driver = self.env["res.partner"].search(
                [
                    ("transporter_id", "=", self.transporter_id.id),
                    ("is_driver", "=", True),
                ],
                limit=1,
            )
            if vehicle:
                self.vehicle_id = vehicle.id
            if driver:
                self.driver_id = driver.id

    @api.constrains("state")
    def _check_assignment(self):
        for leg in self:
            if (
                leg.state in ("active", "in_transit")
                and leg.carrier_type == "third_party"
            ):
                if not leg.transporter_id:
                    raise ValidationError(
                        "Transporter must be assigned before activating the leg."
                    )

    @api.depends("sequence", "from_location_id", "to_location_id")
    def _compute_leg_name(self):
        for rec in self:
            if rec.from_location_id and rec.to_location_id:
                rec.name = f"Leg {rec.sequence}: {rec.from_location_id.name} → {rec.to_location_id.name}"
            else:
                rec.name = f"Leg {rec.sequence}"

    # -------------------------------------
    # ACTION - ASIGN TO MANIFEST
    # -------------------------------------
    def action_assign_to_manifest(self):
        self.ensure_one()

        if self.state != "planned":
            raise ValidationError("Only planned legs can be assigned to a manifest.")

        return {
            "type": "ir.actions.act_window",
            "name": "Assign to Manifest",
            "res_model": "transport.assign.manifest.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_leg_id": self.id,
                "default_from_location_id": self.from_location_id.id,
                "default_to_location_id": self.to_location_id.id,
            },
        }

    def action_view_manifest(self):
        self.ensure_one()

        if not self.manifest_id:
            raise ValidationError(_("This leg is not assigned to any manifest."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Manifest"),
            "res_model": "transport.manifest",
            "view_mode": "form",
            "res_id": self.manifest_id.id,
            "target": "current",
        }

    def action_unassign_manifest(self):
        self.ensure_one()

        # if not self.manifest_id:
        #     return

        if self.manifest_id.state not in ("draft", "confirmed"):
            raise ValidationError("Cannot unassign leg after manifest dispatch.")

        self.manifest_id = False
        self.state = "planned"
