from odoo import models, fields, api

class SocietyDashboard(models.Model):
    _name = 'society.dashboard'
    _description = 'Housing Society Dashboard'
    _rec_name = 'name'

    name = fields.Char(default="Housing Society Dashboard")
    total_flats = fields.Integer(compute="_compute_counts")
    total_members = fields.Integer(compute="_compute_counts")
    total_due = fields.Float(compute="_compute_counts")

    @api.depends()
    def _compute_counts(self):
        for rec in self:
            rec.total_flats = self.env['society.flat'].search_count([])
            rec.total_members = self.env['society.member'].search_count([])
            rec.total_due = sum(self.env['society.maintenance'].search([]).mapped('due_amount'))
