from odoo import fields, models

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    transport_booking_id = fields.Many2one(
        'transport.booking',
        string='Transport Booking'
    )
