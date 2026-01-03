from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TransportGoodsLine(models.Model):
    _name = "transport.goods.line"

    booking_id = fields.Many2one("transport.booking", required=True, ondelete="cascade")

    goods_invoice_number = fields.Char(string="Invoice No")
    goods_type_id = fields.Many2one(
        "transport.goods.type",
        string="Goods Type",
        required=True,
        ondelete="cascade",
    )

    description = fields.Char()
    qty = fields.Integer(default=1)
    actual_weight = fields.Float()
    charged_weight = fields.Float()
    goods_value = fields.Monetary()
    unit_id = fields.Many2one("uom.uom", string="Unit", required=True)

    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("cancelled", "cancelled"),
        ],
        string="Status",
        default="draft",
    )
    delivery_location_id = fields.Many2one(
        "transport.location",
        string="Delivery Location",
        help="Final delivery spoke / customer location",
    )

    @api.model
    def create_transport_good_line(
        self,
        booking_id,
        goods_type_id,
        unit_id,
        qty,
        actual_weight=0.0,
        charged_weight=0.0,
        goods_value=0.0,
        goods_invoice_number=False,
        description=False,
        delivery_location_id=False,
    ):
        """
        Generic Transport Goods Line Creator
        Used from:
        - Direct Booking
        - Third-party inward via Manifold
        """

        # 1️⃣ Mandatory checks (cannot be skipped)
        if not booking_id:
            raise ValidationError(_("Booking is mandatory."))

        if not goods_type_id:
            raise ValidationError(_("Goods Type is mandatory."))

        if not unit_id:
            raise ValidationError(_("Unit is mandatory."))

        if qty <= 0:
            raise ValidationError(_("Quantity must be greater than zero."))

        # 2️⃣ Weight rules
        if actual_weight <= 0 and charged_weight <= 0:
            raise ValidationError(
                _("Either Actual Weight or Charged Weight is required.")
            )

        if actual_weight and charged_weight and charged_weight < actual_weight:
            raise ValidationError(
                _("Charged Weight cannot be less than Actual Weight.")
            )

        # 3️⃣ Create
        return self.create(
            {
                "booking_id": booking_id,
                "goods_type_id": goods_type_id,
                "unit_id": unit_id,
                "qty": qty,
                "actual_weight": actual_weight,
                "charged_weight": charged_weight,
                "goods_value": goods_value,
                "goods_invoice_number": goods_invoice_number,
                "description": description,
                "delivery_location_id": delivery_location_id,
            }
        )
