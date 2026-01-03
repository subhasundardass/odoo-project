from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # partner_type = fields.Selection(
    #     [
    #         ("customer", "Customer"),
    #         ("vendor", "Vendor"),
    #         ("driver", "Driver"),
    #     ],
    #     string="Partner Type",
    # )

    # =========================
    # TRANSPORT ROLE FLAGS
    # =========================
    is_driver = fields.Boolean(string="Is Driver", tracking=True)
    is_transporter = fields.Boolean(string="Is Transporter", tracking=True)
    is_consignee = fields.Boolean(string="Is Consignee")
    is_consignor = fields.Boolean(string="Is Consignor")

    # =========================
    # DRIVER DETAILS
    # =========================
    driver_license_no = fields.Char(string="Driving License No")
    driver_license_expiry = fields.Date(string="License Expiry Date")
    driver_aadhar_no = fields.Char(string="Aadhar No")
    driver_pan_no = fields.Char(string="PAN No")

    # =========================
    # TRANSPORT VENDOR DETAILS
    # =========================
    transport_company_name = fields.Char(string="Transport Company Name")
    vehicle_count = fields.Integer(string="No of Vehicles")

    # =========================
    # UI HELPERS
    # =========================
    is_transport_person = fields.Boolean(
        string="Is Transport Person", compute="_compute_is_transport_person", store=True
    )

    # =========================
    # COMPUTED METHODS
    # =========================
    @api.depends("is_driver", "is_transporter")
    def _compute_is_transport_person(self):
        for rec in self:
            rec.is_transport_person = bool(rec.is_driver or rec.is_transporter)

    # =========================
    # DATA VALIDATION
    # =========================
    @api.constrains("is_driver", "driver_license_no")
    def _check_driver_license(self):
        for rec in self:
            if rec.is_driver and not rec.driver_license_no:
                # Warning only for now (not blocking)
                pass

    # =========================
    # AUTO TITLE BASED ON ROLE
    # =========================
    @api.onchange("is_driver", "is_transporter")
    def _onchange_partner_role(self):
        if self.is_driver:
            self.company_type = "person"
        elif self.is_transporter:
            self.company_type = "company"
