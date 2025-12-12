# -*- coding: utf-8 -*-
{
    "name": "Transport Agency",
    "summary": "Transport Agency Management",
    "description": """
        Long description of module's purpose
    """,
    "author": "Subha Sundar Das",
    "website": "",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    # 'category': 'Uncategorized',
    "version": "0.1",
    # any module necessary for this one to work correctly
    "depends": [
        "base",
        "web",
        "base_address_extended",
        "mail",
        "contacts",
        "account",
        "fleet",
        "hr",
        "hr_expense",
    ],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        # views
        "views/dummy.xml",
        "views/transport_booking.xml",
        # "views/transport_vehicle.xml",
        # "views/transport_goods_type_views.xml",
        # ---------------------------------------------
        "views/transport_city_views.xml",
        "views/transport_location_views.xml",
        "views/transport_movement_views.xml",
        "views/transport_route_views.xml",
        "views/transport_delivery_views.xml",
        # ---------------------------------------------
        # Report (TEMPLATE FIRST, THEN REPORT)
        "reports/external_layout_custom.xml",
        "reports/transport_booking_bill.xml",
        # menu
        "views/navigation.xml",
        # data
        "data/vehicle_manufacturer.xml",
        "data/vehicle_model.xml",
        "data/vehicle_category.xml",
        "data/transport_goods_type_data.xml",
        # sequences
        "data/sequences.xml",
        # "data/movement_sequences.xml",
    ],
    # only loaded in demonstration mode
    "demo": [
        "demo/fleet_vehicle_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "transport_agency/static/src/styles/base.scss",
            "transport_agency/static/src/styles/form.scss",
        ],
    },
    "installable": True,
    "application": True,
}
