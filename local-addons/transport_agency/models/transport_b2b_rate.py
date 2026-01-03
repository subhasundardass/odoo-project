from odoo import models, fields, api


class TransportB2BRate(models.Model):
    _name = "transport.b2b.rate"
    _description = "B2B Transport Rate"
    _order = "valid_from desc"

    name = fields.Char(string="Rate Reference", default="New", copy=False)

    transporter_id = fields.Many2one(
        "res.partner",
        string="Transporter",
        domain=[("is_transporter", "=", True)],
        required=True,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="Rate UoM",
        required=True,
        help="Rate applicable per selected unit",
    )

    rate = fields.Float(string="Rate Amount", required=True)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )

    valid_from = fields.Date(string="Valid From", required=True)
    valid_upto = fields.Date(string="Valid Upto", required=True)
    active = fields.Boolean(default=True)

    remarks = fields.Text(string="Remarks")

    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("transport.b2b.rate") or "New"
            )
        return super().create(vals)

    @api.model
    def get_b2b_rate(self, transporter_id, uom_id):
        """
        Returns rate record or False
        """
        return self.search(
            [
                ("transporter_id", "=", transporter_id),
                ("uom_id", "=", uom_id),
                ("active", "=", True),
            ],
            limit=1,
        )
