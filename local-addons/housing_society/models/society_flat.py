from odoo import models, fields


class SocietyFlat(models.Model):
    _name = 'society.flat'
    _description = 'Flat / Unit'

    number = fields.Char(string='Flat Number', required=True)
    block = fields.Char(string='Block')
    floor = fields.Integer(string='Floor')
    type = fields.Selection([('1BHK','1BHK'),('2BHK','2BHK'),('3BHK','3BHK'),('4BHK','4BHK')])
    area_sqft = fields.Float(string='Area (sq ft)')
    status = fields.Selection([
        ('occupied','Occupied'),
        ('vacant','Vacant'),
        ('under_renovation','Under Renovation'),
        ('reserved','Reserved')
    ], default='vacant')
    member_id = fields.Many2one('society.member', string='Member', ondelete='set null')
    active = fields.Boolean(string='Active', default=True)

    def name_get(self):
        return [(flat.id, flat.number or "Flat") for flat in self]
