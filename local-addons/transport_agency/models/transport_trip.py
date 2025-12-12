from odoo import api, fields, models, _
from odoo.exceptions import UserError

class TransportTrip(models.Model):
    _name = 'transport.trip'
    _description = 'Transport Trip'

    name = fields.Char(string='Trip Reference', required=True, copy=False, default='New')
    booking_id = fields.Many2one('transport.booking', string='Booking', required=True, ondelete='cascade')
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True)
    driver_id = fields.Many2one('hr.employee', string='Driver')
    trip_date = fields.Date(default=fields.Date.context_today)
    expected_delivery_date = fields.Date()
    delivery_date = fields.Date()
    is_hired = fields.Boolean(string='Hired Vehicle', compute='_compute_is_hired', store=True)
    vehicle_owner_id = fields.Many2one('res.partner', string='Vehicle Owner', compute='_compute_vehicle_owner', store=True)
    hire_amount = fields.Monetary(currency_field='currency_id', string='Hire Amount', help='If vehicle is hired, how much vendor charges')
    diesel_amount = fields.Monetary(currency_field='currency_id', string='Diesel Amount', help='Diesel cost (if not included in hire)')
    driver_cost = fields.Monetary(currency_field='currency_id', string='Driver Cost')
    toll_amount = fields.Monetary(currency_field='currency_id', string='Toll & Other')
    other_expense = fields.Monetary(currency_field='currency_id', string='Other Expense')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # computed fields
    total_cost = fields.Monetary(currency_field='currency_id', compute='_compute_total_cost', store=True)
    freight_amount = fields.Monetary(related='booking_id.freight_amount', readonly=True)
    profit = fields.Monetary(currency_field='currency_id', compute='_compute_profit', store=True)

    # accounting links
    vendor_bill_id = fields.Many2one('account.move', string='Vendor Bill', readonly=True)
    customer_invoice_id = fields.Many2one('account.move', string='Customer Invoice', readonly=True)
    

    state = fields.Selection([
        ('assigned', 'Assigned'),
        ('in_transit', 'In Transit'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='assigned')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('transport.trip') or '/'
        return super().create(vals)

    @api.depends('vehicle_id')
    def _compute_is_hired(self):
        for rec in self:
            owner = rec.vehicle_id.owner_id if rec.vehicle_id else False
            # If vehicle owner is not the company -> hired
            rec.is_hired = bool(owner and owner != rec.env.company.partner_id)

    @api.depends('vehicle_id')
    def _compute_vehicle_owner(self):
        for rec in self:
            rec.vehicle_owner_id = rec.vehicle_id.owner_id if rec.vehicle_id else False

    @api.depends('hire_amount', 'diesel_amount', 'driver_cost', 'toll_amount', 'other_expense')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum([
                rec.hire_amount or 0.0,
                rec.diesel_amount or 0.0,
                rec.driver_cost or 0.0,
                rec.toll_amount or 0.0,
                rec.other_expense or 0.0,
            ])

    @api.depends('total_cost', 'freight_amount')
    def _compute_profit(self):
        for rec in self:
            rec.profit = (rec.freight_amount or 0.0) - (rec.total_cost or 0.0)

    def action_start_trip(self):
        for rec in self:
            rec.state = 'in_transit'

    def action_close_trip(self):
        """Main automation:
         - Create vendor bill for hired vehicle (if hired)
         - Create customer invoice for freight (if not already)
         - Apply advance if booking.advance_amount exists (create invoice with residual)
         - Mark trip as done and store references
        """
        AccountMove = self.env['account.move']
        AccountPayment = self.env['account.payment']

        for rec in self:
            # create vendor bill for hired vehicles
            if rec.is_hired and not rec.vendor_bill_id:
                if not rec.vehicle_owner_id:
                    raise UserError(_('Hired vehicle must have an owner (vendor).'))
                vendor_vals = {
                    'move_type': 'in_invoice',
                    'partner_id': rec.vehicle_owner_id.id,
                    'invoice_line_ids': [(0, 0, {
                        'name': _('Hire charge for trip %s') % rec.name,
                        'quantity': 1,
                        'price_unit': rec.hire_amount or 0.0,
                    })],
                }
                bill = AccountMove.create(vendor_vals)
                bill.action_post()
                rec.vendor_bill_id = bill.id

            # create customer invoice (freight)
            if not rec.customer_invoice_id:
                inv_vals = {
                    'move_type': 'out_invoice',
                    'partner_id': rec.booking_id.partner_id.id,
                    'invoice_origin': rec.booking_id.name,
                    'invoice_line_ids': [(0, 0, {
                        'name': _('Freight for %s -> %s (LR: %s)') % (rec.booking_id.from_city, rec.booking_id.to_city, rec.booking_id.name),
                        'quantity': 1,
                        'price_unit': rec.freight_amount or 0.0,
                    })],
                }
                invoice = AccountMove.create(inv_vals)
                # handle advance: record a payment or create invoice with residual?
                invoice.action_post()
                rec.customer_invoice_id = invoice.id

                # If booking had advance, register payment against invoice
                adv = rec.booking_id.advance_amount or 0.0
                if adv > 0.0:
                    pay_vals = {
                        'payment_type': 'inbound',
                        'amount': adv,
                        'partner_id': rec.booking_id.partner_id.id,
                        'partner_type': 'customer',
                        'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                        'currency_id': rec.currency_id.id,
                        # optional link to invoice
                    }
                    payment = AccountPayment.create(pay_vals)
                    payment.action_post()
                    # reconcile payment with invoice
                    # create payment register lines by calling invoice - keep simple: register payment on invoice
                    invoice.js_assign_outstanding_line(payment.id) if hasattr(invoice, 'js_assign_outstanding_line') else None

            # close trip
            rec.state = 'done'
            rec.delivery_date = fields.Date.context_today(rec)
