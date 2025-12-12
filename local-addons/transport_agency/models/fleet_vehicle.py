from odoo import models, fields


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    ownership_type = fields.Selection(
        [
            ("own", "Own Vehicle"),
            ("hired", "Third-Party / Hired"),
        ],
        string="Ownership",
        default="own",
        required=True,
    )

    vendor_id = fields.Many2one(
        "res.partner",
        string="Vehicle Vendor",
        domain=[("supplier_rank", ">", 0)],
        help="Only for Hired Vehicles",
    )

    fixed_rent = fields.Float(
        string="Fixed Monthly Rent", help="Only for hired vehicles if applicable"
    )

    commission_per_trip = fields.Float(
        string="Commission Per Trip", help="Optional commission for hired vehicles"
    )
