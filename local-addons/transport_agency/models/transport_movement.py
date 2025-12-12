from odoo import models, fields, api
from odoo.exceptions import ValidationError
from collections import deque
import logging

_logger = logging.getLogger(__name__)


class TransportMovement(models.Model):
    _name = "transport.movement"
    _description = "Transport Shipment / Movement"
    _order = "id desc"

    name = fields.Char(
        string="Movement Number",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env["ir.sequence"].next_by_code("transport.movement"),
    )

    customer_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        help="Customer associated with this movement",
    )

    pickup_location_id = fields.Many2one(
        "transport.location",
        string="Pickup Location",
        required=True,
        domain="[('owner_type','=','customer'), ('location_type','=','spoke')]",
    )

    delivery_location_id = fields.Many2one(
        "transport.location",
        string="Delivery Location",
        required=True,
        domain="[('owner_type','=','customer'), ('location_type','=','spoke')]",
    )

    movement_date = fields.Datetime(
        string="Movement Date",
        default=fields.Datetime.now,
        required=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("planned", "Planned"),
            ("in_transit", "In Transit"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
    )

    leg_ids = fields.One2many(
        "transport.movement.leg",
        "movement_id",
        string="Movement Legs",
        copy=True,
    )

    total_cost = fields.Float(
        string="Total Cost",
        compute="_compute_total_cost",
        store=True,
    )

    # ----------------------------------------
    # CREATE
    # ----------------------------------------
    @api.model
    def create(self, vals):
        # Movement number
        if not vals.get("name") or vals.get("name") == "New":
            vals["name"] = (
                self.env["ir.sequence"].next_by_code(
                    "transport.movement", sequence_date=fields.Date.today()
                )
                or "New"
            )

        # Auto-fill customer from pickup if not provided
        if not vals.get("customer_id") and vals.get("pickup_location_id"):
            pickup = self.env["transport.location"].browse(vals["pickup_location_id"])
            if pickup.owner_type == "customer" and pickup.partner_id:
                vals["customer_id"] = pickup.partner_id.id
            else:
                raise ValidationError(
                    "Customer must be set for movement. Pickup location does not have a customer."
                )

        return super().create(vals)

    @api.depends("leg_ids.cost")
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum(rec.leg_ids.mapped("cost"))

    # -------------------------
    # Onchange to auto-fill customer from pickup
    # -------------------------
    @api.onchange("pickup_location_id")
    def _onchange_pickup_customer(self):
        for rec in self:
            if (
                rec.pickup_location_id
                and rec.pickup_location_id.owner_type == "customer"
            ):
                rec.customer_id = rec.pickup_location_id.partner_id

    @api.onchange("pickup_location_id", "delivery_location_id")
    def _onchange_locations(self):
        for rec in self:
            if rec.pickup_location_id == rec.delivery_location_id:
                rec.delivery_location_id = False
                return {
                    "warning": {
                        "title": "Invalid Location",
                        "message": "Pickup and delivery cannot be same",
                    }
                }

    # -------------------------
    # Apply route template to generate legs
    # -------------------------
    def action_apply_route_template(self):
        for rec in self:
            if not rec.route_template_id:
                raise ValidationError("Please select a route template first.")
            if not rec.customer_id:
                raise ValidationError("Customer is required before generating legs.")
            rec.route_template_id.generate_legs_for_movement(rec)
            rec.state = "planned"

    # ----------------------------------------
    # VALIDATIONS
    # ----------------------------------------
    @api.constrains("pickup_location_id", "delivery_location_id")
    def _check_pickup_delivery(self):
        for rec in self:
            if rec.pickup_location_id == rec.delivery_location_id:
                raise ValidationError("Pickup and Delivery cannot be the same.")

    # ----------------------------------------
    # STATE ACTIONS
    # ----------------------------------------
    def action_start(self):
        self.state = "in_transit"

    def action_complete(self):
        for rec in self:
            # Ensure all legs are done
            incomplete = rec.leg_ids.filtered(lambda l: l.state != "completed")
            if incomplete:
                raise ValidationError(
                    "All legs must be completed before marking movement completed."
                )
        self.state = "completed"

    def action_cancel(self):
        self.state = "cancelled"

    # -------------------------------------------------------------
    # BUTTON TO GENERATE LEGS
    # -------------------------------------------------------------
    def action_generate_legs(self):
        for movement in self:
            movement._create_movement_legs_without_bfs()

    # -------------------------------------------------------------
    # AUTO GENERATE WITHOUT BFS
    # -------------------------------------------------------------
    def _create_movement_legs_without_bfs(self):
        self.ensure_one()
        self.leg_ids.unlink()

        legs = []
        seq = 1

        pickup = self.pickup_location_id
        delivery = self.delivery_location_id

        # 1. Pickup → Pickup parent hub (if any)
        if pickup.location_type == "spoke" and pickup.parent_hub_id:
            legs.append((pickup.id, pickup.parent_hub_id.id))
            current = pickup.parent_hub_id
        else:
            current = pickup

        # 2. Hub → Hub (if delivery has parent hub different from pickup hub)
        if delivery.location_type == "spoke" and delivery.parent_hub_id:
            if current != delivery.parent_hub_id:
                legs.append((current.id, delivery.parent_hub_id.id))
            current = delivery.parent_hub_id

        # 3. Hub → Delivery (if delivery is a spoke)
        if delivery.location_type == "spoke":
            legs.append((current.id, delivery.id))

        # 4. Create leg records
        for src, dst in legs:
            self.env["transport.movement.leg"].create(
                {
                    "movement_id": self.id,
                    "sequence": seq,
                    "from_location_id": src,
                    "to_location_id": dst,
                    "responsible_by": "own",
                }
            )
            seq += 1

    # -------------------------------------------------------------
    # BFS PATH FINDING + LEG CREATION
    # -------------------------------------------------------------

    def _create_movement_legs(self):
        """Finds multi-leg path using BFS and creates legs."""
        self.ensure_one()

        # Clear previous legs
        self.leg_ids.unlink()

        graph = self._build_graph()

        path = self._bfs_find_path(
            graph,
            start=self.pickup_location_id.id,
            end=self.delivery_location_id.id,
        )

        if not path:
            raise ValidationError(
                "No route found between Pickup and Delivery locations."
            )

        # ---------------------------------------------------------
        # CREATE LEGS NOW
        # ---------------------------------------------------------
        for i in range(len(path) - 1):
            source_id = path[i]
            dest_id = path[i + 1]

            route = self.env["transport.route"].search(
                [
                    ("source_location_id", "=", source_id),
                    ("destination_location_id", "=", dest_id),
                ],
                limit=1,
            )

            if not route:
                raise ValidationError(
                    "Route missing between %s → %s" % (path[i], path[i + 1])
                )

            # Create leg
            leg = self.env["transport.movement.leg"].create(
                {
                    "movement_id": self.id,
                    "sequence": i + 1,
                    "from_location_id": source_id,
                    "to_location_id": dest_id,
                    "responsible_by": route.responsible_by,
                }
            )

            # STOP if third-party hub takes over
            if route.responsible_by == "third_party":
                break

    # -------------------------------------------------------------
    # BUILD GRAPH FROM ROUTES
    # -------------------------------------------------------------
    def _build_graph(self):
        """Returns adjacency list graph from transport.route records."""
        graph = {}

        for route in self.env["transport.route"].search([]):
            graph.setdefault(route.source_location_id.id, [])
            graph[route.source_location_id.id].append(route.destination_location_id.id)

        return graph

    # -------------------------------------------------------------
    # BFS PATH FINDER (Fast + Scalable)
    # -------------------------------------------------------------
    def _bfs_find_path(self, graph, start, end):
        """Returns shortest path list [A, B, C, D] using BFS."""

        _logger.info(
            "ROUTES========================================= = %s",
            self.env["transport.route"].search([]),
        )
        _logger.info(
            "======================================================GRAPH: %s", graph
        )
        _logger.info("Start: %s, End: %s", start, end)

        queue = deque([[start]])
        visited = set()

        while queue:
            path = queue.popleft()
            current = path[-1]

            # STOP if reached destination
            if current == end:
                return path

            if current in visited:
                continue

            visited.add(current)

            for neighbour in graph.get(current, []):
                new_path = path + [neighbour]
                queue.append(new_path)

        return None
