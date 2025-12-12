from odoo import models, fields


class TransportGoodsType(models.Model):
    _name = "transport.goods.type"
    _description = "Transport Goods Type Master"
    _order = "name"

    name = fields.Char(string="Goods Type Name", required=True)
    code = fields.Char(string="Code")
    active = fields.Boolean(default=True)

    # ✅ Business Control Fields (for future automation)
    is_hazardous = fields.Boolean(string="Hazardous / Dangerous")
    default_unit_id = fields.Many2one("uom.uom", string="Default Unit")

    default_risk_type = fields.Selection(
        [
            ("owner", "Owner's Risk"),
            ("carrier", "Carrier's Risk"),
        ],
        string="Default Risk",
    )

    note = fields.Text(string="Remarks")

    _sql_constraints = [("unique_name", "unique(name)", "Goods Type must be unique!")]
