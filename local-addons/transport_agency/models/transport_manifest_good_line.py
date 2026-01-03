from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_compare


class TransportManifestGoodLine(models.Model):
    _name = "transport.manifest.good.line"
    _description = "Manifest Goods Line"

    manifest_id = fields.Many2one(
        "transport.manifest", required=True, ondelete="cascade"
    )

    booking_id = fields.Many2one("transport.booking", required=True)
    movement_leg_id = fields.Many2one("transport.movement.leg", required=True)
    good_line_id = fields.Many2one("transport.goods.line", required=True)

    qty_loaded = fields.Float(required=True)
    # weight_loaded = fields.Float()

    from_location_id = fields.Many2one()
    to_location_id = fields.Many2one()
