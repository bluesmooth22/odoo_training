from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    pcf_ok = fields.Boolean(default=False, string='Has Perpetual Care')

