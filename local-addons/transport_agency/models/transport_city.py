from odoo import models, fields, api


class TransportCity(models.Model):
    _name = "transport.city"
    _description = "Transport City"
    _order = "name"

    name = fields.Char("City Name", required=True)
    state_id = fields.Many2one("res.country.state", string="State", required=True)
    country_id = fields.Many2one(
        "res.country",
        string="Country",
        related="state_id.country_id",
        store=True,
        readonly=True,
    )

    # # Hub / Spoke classification
    is_hub = fields.Boolean("Is Hub?", default=False)

    # # For Spokes → which Hub they belong to
    hub_id = fields.Many2one(
        "transport.city",
        string="Parent Hub",
        domain="[('is_hub', '=', True)]",
        help="If this is a spoke, select its parent hub.",
    )

    # Used by location/address
    location_ids = fields.One2many("transport.location", "city_id", string="Locations")

    # Prevent duplicates
    _sql_constraints = [
        ("unique_city", "unique(name, state_id)", "City already exists in this state!")
    ]
