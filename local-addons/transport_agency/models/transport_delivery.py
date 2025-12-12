from odoo import api, fields, models


class TransportDelivery(models.Model):
    _name = "transport.delivery"
    _description = "Goods Delivery"
    _order = "delivery_date desc, id desc"

    # -------------------------
    # BASIC LINKS
    # -------------------------
    booking_id = fields.Many2one(
        "transport.booking",
        string="Booking",
        required=True,
        ondelete="cascade",
    )

    movement_id = fields.Many2one(
        "transport.movement",
        string="Movement",
        help="Final line-haul or branch transfer movement",
    )

    # -------------------------
    # DELIVERY DETAILS
    # -------------------------
    delivery_date = fields.Datetime(
        string="Delivery Date",
        default=fields.Datetime.now,
    )

    delivered_by_id = fields.Many2one(
        "res.users",
        string="Delivered By",
        default=lambda self: self.env.user,
    )

    destination_hub_id = fields.Many2one(
        "transport.location",
        string="Destination Hub",
    )

    # consignee_id = fields.Many2one(
    #     "res.partner",
    #     string="Consignee",
    #     related="booking_id.consignee_id",
    #     store=True,
    #     readonly=True,
    # )

    consignee_acknowledged = fields.Boolean(string="Acknowledged by Consignee")

    pod_attachment = fields.Binary(string="POD Document")
    pod_filename = fields.Char(string="POD Filename")

    # -------------------------
    # DELIVERY STATUS
    # -------------------------
    delivery_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("arrived", "Arrived at Destination"),
            ("unloading", "Unloading in Progress"),
            ("delivered", "Delivered"),
            ("issue", "Issue"),
        ],
        string="Delivery Status",
        default="pending",
    )

    delivery_issue_reason = fields.Text(string="Issue Notes")

    # -------------------------
    # AUTOMATION
    # -------------------------
    ready_for_billing = fields.Boolean(string="Ready for Billing", default=False)

    # -------------------------
    # BUTTON LOGIC
    # -------------------------

    def action_arrived(self):
        self.delivery_status = "arrived"

    def action_unloading(self):
        self.delivery_status = "unloading"

    def action_delivered(self):
        self.delivery_status = "delivered"
        self.ready_for_billing = True
        self.booking_id.state = "delivered"  # optional

    def action_issue(self, reason=None):
        self.delivery_status = "issue"
        if reason:
            self.delivery_issue_reason = reason
