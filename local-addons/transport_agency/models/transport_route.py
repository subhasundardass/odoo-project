from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TransportRoute(models.Model):
    _name = "transport.route"
    _description = "Transport Route / Lane"
    _rec_name = "display_name"

    # ---------------------------------------------------------
    # BASIC FIELDS
    # ---------------------------------------------------------
    source_location_id = fields.Many2one(
        "transport.location",
        string="From Location",
        required=True,
        domain="[('active','=',True)]",
    )

    destination_location_id = fields.Many2one(
        "transport.location",
        string="To Location",
        required=True,
        domain="[('active','=',True)]",
    )

    active = fields.Boolean(default=True)

    # ---------------------------------------------------------
    # RESPONSIBILITY
    # ---------------------------------------------------------
    responsible_by = fields.Selection(
        [
            ("own", "Own Transport"),
            ("third_party", "Third Party"),
        ],
        string="Responsibility",
        required=True,
        default="own",
        help="Determines whether a leg should be created beyond this route.",
    )

    # Example:
    # Pickup → HubA = own
    # HubA → HubB = own
    # HubB → Spoke = third_party (so stop generating legs)

    # ---------------------------------------------------------
    # COST / PRIORITY (Used by Dijkstra)
    # ---------------------------------------------------------
    transit_time = fields.Float(
        string="Transit Time (Hrs)",
        help="Used in routing to find fastest route",
        default=0,
    )

    cost = fields.Float(
        string="Operational Cost",
        help="Used by Dijkstra for cheapest route calculation",
        default=0,
    )

    distance_km = fields.Float(
        string="Distance (KM)",
        help="Optional, useful for calculating freight",
    )

    # ---------------------------------------------------------
    # COMPUTED FIELDS
    # ---------------------------------------------------------
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    @api.depends("source_location_id", "destination_location_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.source_location_id and rec.destination_location_id:
                rec.display_name = f"{rec.source_location_id.name} → {rec.destination_location_id.name}"
            else:
                rec.display_name = "Route"

    # ---------------------------------------------------------
    # VALIDATIONS
    # ---------------------------------------------------------
    @api.constrains("source_location_id", "destination_location_id")
    def _check_route_validity(self):
        for rec in self:

            # A → A not allowed
            if rec.source_location_id == rec.destination_location_id:
                raise ValidationError("Source and destination cannot be the same.")

            # Duplicate check
            existing = self.search(
                [
                    ("source_location_id", "=", rec.source_location_id.id),
                    ("destination_location_id", "=", rec.destination_location_id.id),
                    ("id", "!=", rec.id),
                ]
            )
            if existing:
                raise ValidationError("This route already exists.")

            # If source is a spoke, it must have a parent hub
            if (
                rec.source_location_id.location_type == "spoke"
                and not rec.source_location_id.parent_hub_id
            ):
                raise ValidationError(
                    f"Spoke '{rec.source_location_id.name}' must have a parent hub."
                )

            # Responsibility rule
            # If third-party hub is connected, it must be responsible_by = 'third_party'
            if (
                rec.destination_location_id.owner_type == "third_party"
                and rec.responsible_by == "own"
            ):
                raise ValidationError(
                    f"Route to third-party hub '{rec.destination_location_id.name}' "
                    "must be marked as Third Party responsibility."
                )
