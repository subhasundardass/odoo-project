from odoo import models, fields


class TransportMovementExpense(models.Model):
    _name = "transport.movement.expense"
    _description = "Driver Expense / Advance"

    movement_id = fields.Many2one(
        "transport.movement", string="Movement", required=True, ondelete="cascade"
    )
    paid_to = fields.Many2one(
        "res.partner", string="Driver", domain=[("is_driver", "=", True)], required=True
    )
    amount = fields.Monetary(
        string="Amount", required=True, currency_field="currency_id"
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    payment_date = fields.Datetime(default=fields.Datetime.now)
    note = fields.Text(string="Note")
    created_by = fields.Many2one("res.users", default=lambda self: self.env.user)
