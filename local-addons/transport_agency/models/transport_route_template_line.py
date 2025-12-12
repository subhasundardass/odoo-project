from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TransportRouteTemplateLine(models.Model):
    _name = "transport.route.template.line"
    _description = "Transport Route Template Leg"
    _order = "sequence asc"

    template_id = fields.Many2one(
        "transport.route.template",
        string="Route Template",
        required=True,
        ondelete="cascade",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=1,
        help="1 = First leg, 2 = Next, etc.",
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

    carrier_type = fields.Selection(
        [
            ("own", "Own Transport"),
            ("third_party", "Third Party"),
        ],
        string="Carrier",
        default="own",
        required=True,
    )

    third_party_partner_id = fields.Many2one(
        "res.partner",
        string="3rd Party Vendor",
        help="Required when leg is outsourced to third-party.",
    )

    @api.constrains("carrier_type", "third_party_partner_id")
    def _check_vendor(self):
        for rec in self:
            if rec.carrier_type == "third_party" and not rec.third_party_partner_id:
                raise ValidationError("Third Party Vendor is required for this leg.")

    @api.constrains("from_location_id", "to_location_id")
    def _check_locations(self):
        for rec in self:
            if rec.from_location_id == rec.to_location_id:
                raise ValidationError("From and To cannot be the same.")
