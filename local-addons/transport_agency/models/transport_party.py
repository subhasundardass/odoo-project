from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TransportParty(models.Model):
    _name = "transport.party"
    _description = "Transport Party"

    name = fields.Char(string="Name", required=True)

    partner_id = fields.Many2one(
        "res.partner", string="Related Customer", required=True, ondelete="cascade"
    )

    party_type = fields.Selection(
        [
            ("consignor", "Consignor"),
            ("consignee", "Consignee"),
        ],
        required=True,
    )

    phone = fields.Char(string="Phone")
    email = fields.Char(string="Email")

    gst_no = fields.Char(string="GST Number")

    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    state = fields.Char()
    pincode = fields.Char()

    active = fields.Boolean(default=True)

    full_address = fields.Text(
        string="Full Address",
        compute="_compute_address",
        store=True,
        readonly=True,
    )

    @api.constrains("partner_id")
    def _check_partner_required(self):
        for rec in self:
            if not rec.partner_id:
                raise ValidationError(
                    "Customer must be selected before creating a Party."
                )

    @api.depends(
        "street",
        "street2",
        "city",
        "state",
        "pincode",
        "phone",
    )
    def _compute_address(self):
        for rec in self:
            parts = filter(
                None,
                [
                    rec.street,
                    rec.street2,
                    rec.city,
                    rec.state,
                    rec.pincode,
                    f"Ph: {rec.phone}" if rec.phone else None,
                ],
            )
            rec.full_address = ", ".join(parts)
