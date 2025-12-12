from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TransportGoodsLine(models.Model):
    _name = "transport.goods.line"

    booking_id = fields.Many2one("transport.booking", required=True, ondelete="cascade")

    goods_invoice_number = fields.Char(string="Goods Invoice No")
    goods_type_id = fields.Many2one(
        "transport.goods.type",
        string="Goods Type",
        required=True,
        ondelete="cascade",
    )

    description = fields.Char()
    qty = fields.Integer(default=1)
    actual_weight = fields.Float()
    charged_weight = fields.Float()
    goods_value = fields.Monetary()
    unit_id = fields.Many2one("uom.uom", string="Unit", required=True)

    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id.id
    )
