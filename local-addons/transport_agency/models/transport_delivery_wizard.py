from odoo import models, fields, _
from odoo.exceptions import ValidationError, UserError


class TransportDeliveryWizard(models.TransientModel):
    _name = "transport.delivery.wizard"
    _description = "Confirm Delivery Wizard"

    booking_id = fields.Many2one(
        "transport.booking",
        string="Booking",
        required=True,
        readonly=True,
    )

    pod_file = fields.Binary(
        string="POD Document",
        required=True,
    )
    pod_filename = fields.Char(string="POD Filename")

    received_by = fields.Char(
        string="Received By",
        required=True,
    )

    delivery_date = fields.Datetime(
        string="Delivery Date",
        required=True,
        default=fields.Datetime.now,
    )

    remark = fields.Text(string="Remarks")
    is_delivered = fields.Boolean(compute="_compute_is_delivered", store=True)

    def _compute_is_delivered(self):
        for rec in self:
            rec.is_delivered = rec.state == "delivered"

    def action_confirm_delivery(self):
        self.ensure_one()
        booking = self.booking_id

        # ---- State validations ----
        if booking.state == "delivered":
            raise ValidationError(_("This booking is already delivered."))

        if booking.state != "in_transit":
            raise ValidationError(
                _("Only bookings in 'In Transit' state can be delivered.")
            )

        # ---- Update booking with POD details ----
        booking.write(
            {
                "pod_file": self.pod_file,
                "pod_filename": self.pod_filename,
                "received_by": self.received_by,
                "delivery_date": self.delivery_date,
                "delivery_remark": self.remark,
            }
        )

        # ---- Mark booking delivered (single responsibility) ----
        booking.action_mark_delivered()

        return {"type": "ir.actions.act_window_close"}
