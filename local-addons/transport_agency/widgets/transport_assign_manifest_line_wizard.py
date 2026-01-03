from odoo import models, fields


class AssignManifestLineWizard(models.TransientModel):
    _name = "transport.assign.manifest.line.wizard"

    wizard_id = fields.Many2one("transport.assign.manifest.wizard", required=True)

    booking_id = fields.Many2one("transport.booking")
    docket_no = fields.Char()
    goods_type_id = fields.Char()
    weight = fields.Float()
    unit_id = fields.Char()

    available_qty = fields.Float()
    load_qty = fields.Float(required=True)
