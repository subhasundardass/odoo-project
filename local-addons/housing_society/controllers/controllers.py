# -*- coding: utf-8 -*-
# from odoo import http


# class HousingSociety(http.Controller):
#     @http.route('/housing_society/housing_society', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/housing_society/housing_society/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('housing_society.listing', {
#             'root': '/housing_society/housing_society',
#             'objects': http.request.env['housing_society.housing_society'].search([]),
#         })

#     @http.route('/housing_society/housing_society/objects/<model("housing_society.housing_society"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('housing_society.object', {
#             'object': obj
#         })
