from odoo import models, fields, api

class SocietyMember(models.Model):
    _name = 'society.member'
    _inherits = {'res.partner': 'partner_id'}
    _description = 'Society Member'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade')
    flat_ids = fields.One2many('society.flat', 'member_id', string='Flats')
    role = fields.Selection([('owner','Owner'), ('tenant','Tenant')], default='owner')

    # Optional: set defaults on creation
    @api.model
    def create(self, vals):
        # If partner_id not given, Odoo will automatically create one
        if 'partner_id' not in vals:
            partner_vals = {
                'name': vals.get('name'),
                'email': vals.get('email'),
                'phone': vals.get('phone'),
                'l10n_in_gst_treatment': 'consumer', 
                'customer_rank': 1,                   # Default Partner Type = Customer
                'supplier_rank': 0,
            }
            partner = self.env['res.partner'].create(partner_vals)
            vals['partner_id'] = partner.id

        else:
            partner = self.env['res.partner'].browse(vals['partner_id'])
            partner.write({
                'l10n_in_gst_treatment': 'consumer',
                'customer_rank': 1,
                'supplier_rank': 0,
            })    
        return super(SocietyMember, self).create(vals)
        
    def name_get(self):
        return [(member.id, member.partner_id.name or "Member") for member in self] 

    def hgt(self):
        fields  