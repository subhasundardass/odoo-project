from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TransportLocation(models.Model):
    _name = "transport.location"
    _description = "Transport Hub / Spoke Location"

    name = fields.Char(string="Location Name", required=True)

    owner_type = fields.Selection(
        [
            ("agency", "Agency"),
            ("customer", "Customer"),
        ],
        string="Owned By",
        required=True,
        default="customer",
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        help="Required only for customer pickup / delivery locations",
    )

    address = fields.Text(string="Address")
    city = fields.Char(string="City", required=True)

    state_id = fields.Many2one(
        "res.country.state",
        string="State",
    )

    country_id = fields.Many2one(
        "res.country",
        string="Country",
    )

    location_type = fields.Selection(
        [
            ("hub", "Hub"),
            ("spoke", "Spoke"),
        ],
        required=True,
        default="spoke",
    )

    parent_hub_id = fields.Many2one(
        "transport.location",
        string="Agency Hub",
        domain="[('owner_type','=','agency'), ('location_type','=','hub')]",
        help="Required only for pickup spokes",
    )

    active = fields.Boolean(default=True)

    @api.onchange("owner_type")
    def _onchange_owner_type(self):
        if self.owner_type == "customer":
            self.location_type = "spoke"
            self.parent_hub_id = False  # may select later
        elif self.owner_type == "agency":
            self.location_type = "hub"
            self.parent_hub_id = False  # hub never has parent

    # ✅ BUSINESS RULES
    @api.constrains("owner_type", "location_type", "parent_hub_id")
    def _check_owner_location_rules(self):
        for rec in self:
            if rec.owner_type == "agency":
                # Force hub
                if rec.location_type != "hub":
                    raise ValidationError(
                        "For Agency-owned locations, Location Type must be Hub."
                    )
                if rec.parent_hub_id:
                    raise ValidationError("Agency hub cannot have a parent hub.")

            if rec.owner_type == "customer":
                # Force spoke
                if rec.location_type != "spoke":
                    raise ValidationError(
                        "For Customer-owned locations, Location Type must be Spoke."
                    )
