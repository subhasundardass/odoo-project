from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, time


class TransportAssignManifestWizard(models.TransientModel):
    _name = "transport.assign.manifest.wizard"
    _description = "Assign Movement Leg to Manifest"

    leg_id = fields.Many2one(
        "transport.movement.leg",
        required=True,
        readonly=True,
    )

    good_line_ids = fields.One2many(
        "transport.assign.manifest.line.wizard", "wizard_id", string="Goods to Load"
    )

    manifest_id = fields.Many2one(
        "transport.manifest",
        # required=True,
        domain=[("state", "in", ("draft", "confirmed"))],
        placeholder="Leave empty to create / reuse manifest",
    )

    # Execution inputs (stored on Manifest)
    vehicle_id = fields.Many2one("fleet.vehicle", required=True)
    driver_id = fields.Many2one("res.partner", string="Driver", required=True)

    from_location_id = fields.Many2one(
        "transport.location",
        required=True,
    )
    to_location_id = fields.Many2one(
        "transport.location",
        required=True,
    )

    departure_datetime = fields.Datetime(required=True)
    expected_arrival_datetime = fields.Datetime(string="Expected Arrival")
    estimated_cost = fields.Float()

    def action_confirm(self):
        self.ensure_one()
        leg = self.leg_id

        if leg.state != "planned":
            raise ValidationError("Only planned legs can be assigned.")

        manifest = self.manifest_id

        if not manifest:
            manifest_vals = {
                "vehicle_id": self.vehicle_id.id,
                "driver_id": self.driver_id.id,
                "source_location_id": self.from_location_id.id,
                "destination_location_id": self.to_location_id.id,
                "departure_time": self.departure_datetime,
                "arrival_time": self.expected_arrival_datetime,
                "estimated_cost": self.estimated_cost,
            }

            # Add datetime fields ONLY if they exist
            if hasattr(self.env["transport.manifest"], "_fields"):
                fields_map = self.env["transport.manifest"]._fields

                if "dispatch_datetime" in fields_map:
                    manifest_vals["departure_time"] = self.departure_datetime

                if "expected_arrival_datetime" in fields_map:
                    manifest_vals["arrival_time"] = self.expected_arrival_datetime

                if "estimated_cost" in fields_map:
                    manifest_vals["estimated_cost"] = self.estimated_cost

            # Create Manifest
            manifest = self.env["transport.manifest"].create(manifest_vals)

        leg.manifest_id = manifest.id
        # leg.state = "assigned"

        # 2️⃣ Link leg
        manifest.leg_ids = [(4, self.leg_id.id)]
        # 3️⃣ Create manifest goods lines
        for line in self.good_line_ids:
            if line.load_qty <= 0:
                continue

            self.env["transport.manifest.good.line"].create(
                {
                    "manifest_id": manifest.id,
                    "booking_id": line.booking_id.id,
                    "movement_leg_id": self.leg_id.id,
                    "qty_loaded": line.load_qty,
                    "from_location_id": self.leg_id.from_location_id.id,
                    "to_location_id": self.leg_id.to_location_id.id,
                }
            )

        self.leg_id.state = "assigned"

        return {"type": "ir.actions.act_window_close"}

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        leg_id = self.env.context.get("default_leg_id")
        if not leg_id:
            return res

        leg = self.env["transport.movement.leg"].browse(leg_id)

        if leg.state != "planned":
            raise ValidationError("Only planned legs can be assigned to a manifest.")

        movement = leg.movement_id

        res.update(
            {
                "leg_id": leg.id,
                "from_location_id": leg.from_location_id.id,
                "to_location_id": leg.to_location_id.id,
            }
        )

        lines = []

        # Goods come from movement → bookings
        for booking in movement.booking_id:
            for good in booking.goods_line_ids:
                lines.append(
                    (
                        0,
                        0,
                        {
                            "booking_id": booking.id,
                            "docket_no": booking.docket_no,
                            "goods_type_id": good.goods_type_id.id,
                            "weight": good.actual_weight,
                            "unit_id": good.unit_id.id,
                            "available_qty": good.qty,
                            "load_qty": good.qty,  # default full load
                        },
                    )
                )

        res["good_line_ids"] = lines
        return res
