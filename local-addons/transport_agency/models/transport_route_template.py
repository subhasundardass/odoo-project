from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TransportRouteTemplate(models.Model):
    _name = "transport.route.template"
    _description = "Transport Route Template"
    _order = "name asc"

    name = fields.Char(string="Route Name", required=True)

    active = fields.Boolean(default=True)

    source_location_id = fields.Many2one(
        "transport.location",
        string="Source",
        required=True,
        help="Pickup spoke location",
        domain="[('location_type','=','spoke')]",
    )

    destination_location_id = fields.Many2one(
        "transport.location",
        string="Destination",
        required=True,
        help="Delivery spoke location",
        domain="[('location_type','=','spoke')]",
    )

    line_ids = fields.One2many(
        "transport.route.template.line",
        "template_id",
        string="Route Legs",
        copy=True,
    )

    total_legs = fields.Integer(
        string="Total Legs",
        compute="_compute_total_legs",
        store=True,
    )

    @api.depends("line_ids")
    def _compute_total_legs(self):
        for rec in self:
            rec.total_legs = len(rec.line_ids)

    # VALIDATION -----------------------------
    @api.constrains("source_location_id", "destination_location_id")
    def _check_source_destination(self):
        for rec in self:
            if rec.source_location_id == rec.destination_location_id:
                raise ValidationError("Source and destination cannot be the same.")

    # AUTO-GENERATE LEGS FOR MOVEMENT ---------
    def generate_legs_for_movement(self, movement):
        """
        Creates movement legs based on this route template.
        This is called from movement.action_apply_route_template()
        """
        self.ensure_one()

        # Clear existing legs
        movement.leg_ids.unlink()

        for seq, line in enumerate(self.line_ids, start=1):
            movement.env["transport.movement.leg"].create(
                {
                    "movement_id": movement.id,
                    "sequence": seq,
                    "from_location_id": line.from_location_id.id,
                    "to_location_id": line.to_location_id.id,
                    "carrier_type": line.carrier_type,
                    "third_party_partner_id": line.third_party_partner_id.id,
                }
            )

        # Change movement status
        movement.state = "planned"
