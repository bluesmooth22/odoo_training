# -*- coding: utf-8 -*-
from odoo import http

# class Installment(http.Controller):
#     @http.route('/installment/installment/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/installment/installment/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('installment.listing', {
#             'root': '/installment/installment',
#             'objects': http.request.env['installment.installment'].search([]),
#         })

#     @http.route('/installment/installment/objects/<model("installment.installment"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('installment.object', {
#             'object': obj
#         })