from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TransportLocation(models.Model):
    _name = "transport.location"
    _description = "Transport Location (Hub / Spoke / Handover)"
    _rec_name = "name"

    # ---------------------------------------------------------
    # BASIC INFO
    # ---------------------------------------------------------
    name = fields.Char(string="Location Name", required=True)
    code = fields.Char(string="Short Code", help="3-6 character code for routing maps")

    address = fields.Text(string="Address")
    city_id = fields.Many2one("transport.city", string="City", required=True)
    # auto loaded from city
    state_id = fields.Many2one(
        "res.country.state", related="city_id.state_id", store=True
    )
    country_id = fields.Many2one(
        "res.country", related="city_id.country_id", store=True
    )

    # ---------------------------------------------------------
    # OWNERSHIP
    # ---------------------------------------------------------
    owner_type = fields.Selection(
        [
            ("own", "Own Hub / Office"),
            ("customer", "Customer Spoke"),
            ("third_party", "Third Party Hub"),
        ],
        string="Location Owned By",
        required=True,
        default="own",
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer/Agency",
        help="Required for customer or third-party locations",
    )

    # ---------------------------------------------------------
    # LOCATION CLASSIFICATION
    # ---------------------------------------------------------
    location_type = fields.Selection(
        [
            ("hub", "Hub"),
            ("spoke", "Spoke"),
        ],
        string="Location Type",
        required=True,
        default="spoke",
    )

    # Parent hub for spokes (optional)
    parent_hub_id = fields.Many2one(
        "transport.location",
        string="Parent Hub (Optional)",
        domain="[('location_type','=','hub')]",
    )

    # ---------------------------------------------------------
    # RESPONSIBILITY CONTROL
    # ---------------------------------------------------------
    is_handover_point = fields.Boolean(
        string="Final Handover Point",
        help="If enabled, routing will not generate legs beyond this location.",
    )

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------
    active = fields.Boolean(default=True)

    # ---------------------------------------------------------
    # VALIDATIONS
    # ---------------------------------------------------------
    @api.onchange("owner_type")
    def _onchange_owner_type(self):
        """Automatically set location type & clear parent hub."""
        if self.owner_type == "own":
            self.location_type = "hub"

        if self.owner_type == "customer":
            self.location_type = "spoke"

        if self.owner_type == "third_party":
            self.location_type = "hub"

        # Customer locations or own hubs don't need parent hub by default
        self.parent_hub_id = False

    @api.constrains("owner_type", "location_type", "parent_hub_id")
    def _check_consistency(self):
        for rec in self:

            # Own = Hub always
            if rec.owner_type == "own" and rec.location_type != "hub":
                raise ValidationError("Own locations must be Hubs.")

            # Customer = Spoke always
            if rec.owner_type == "customer" and rec.location_type != "spoke":
                raise ValidationError("Customer-owned locations must be Spokes.")

            # Third party = Hub always
            if rec.owner_type == "third_party" and rec.location_type != "hub":
                raise ValidationError("Third-party locations must be Hubs.")

            # Hub cannot have parent hub
            if rec.location_type == "hub" and rec.parent_hub_id:
                raise ValidationError("Hub cannot have a parent hub.")

            # Spoke cannot be handover point
            if rec.location_type == "spoke" and rec.is_handover_point:
                raise ValidationError("Only hubs can be handover points.")

            # Customer locations require partner
            if rec.owner_type == "customer" and not rec.partner_id:
                raise ValidationError("Customer locations must have a linked Customer.")

    # ------------------------------------------
    # Hooks
    # ---------------------------------------------------------
    def name_get(self):
        result = []
        for rec in self:
            name = rec.name
            # Append city if available
            if rec.city_id:
                name = f"{name} - {rec.city_id.name}"

            result.append((rec.id, name))
        return result

    @api.model
    def create(self, vals):
        rec = super().create(vals)

        # ------------------------------------------------------------
        # RULE 1: SPOKE LOCATION → Parent hub required ONLY IF
        #         the city has hub locations
        # ------------------------------------------------------------
        if rec.location_type == "spoke":

            # Check if this city already has hub locations
            hub_locations = self.search(
                [
                    ("city_id", "=", rec.city_id.id),
                    ("location_type", "=", "hub"),
                ],
                limit=1,
            )

            if hub_locations:
                # City has hubs → parent hub is required
                if not rec.parent_hub_id:
                    raise ValidationError(
                        f"Spoke location '{rec.name}' must have a parent hub because "
                        f"city '{rec.city_id.name}' has hub locations."
                    )
            else:
                # City has NO hubs → parent hub must NOT be required
                # (Business case: direct delivery from main hub)
                pass

            # Auto-create spoke → hub route (ONLY if parent hub exists)
            if rec.parent_hub_id:
                self.env["transport.route.template"].create(
                    {
                        "name": f"{rec.name} → {rec.parent_hub_id.name}",
                        "source_location_id": rec.id,
                        "destination_location_id": rec.parent_hub_id.id,
                    }
                )

        # ------------------------------------------------------------
        # RULE 2: HUB LOCATION → Create hub↔hub routes with existing hubs
        # ------------------------------------------------------------
        if rec.location_type == "hub":
            all_hubs = self.search([("location_type", "=", "hub")]) - rec

            for hub in all_hubs:
                # Hub → Existing hubs
                self.env["transport.route.template"].create(
                    {
                        "name": f"{rec.name} → {hub.name}",
                        "source_location_id": rec.id,
                        "destination_location_id": hub.id,
                    }
                )
                # Existing hubs → new hub
                self.env["transport.route.template"].create(
                    {
                        "name": f"{hub.name} → {rec.name}",
                        "source_location_id": hub.id,
                        "destination_location_id": rec.id,
                    }
                )

        return rec
