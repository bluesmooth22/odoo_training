from itertools import groupby
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import formatLang

import odoo.addons.decimal_precision as dp

class InstallmentSaleLine(models.Model):
    _inherit = 'sale.order.line'

    # installment_order_id = fields.Many2one('installment.sale', string='Order Reference', required=True,
    #                                        ondelete='cascade', index=True,
    #                                        copy=False)
    installment_price_subtotal = fields.Monetary(string='Subtotal', readonly=True, store=True)
    installment_price_tax = fields.Monetary(string='Taxes', readonly=True, store=True)
    installment_price_total = fields.Monetary(string='Total', readonly=True, store=True)

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_installment_amount(self):
        for line in self:

            line.update({
                'installment_price_tax': '',
                'installment_price_total': '',
            })


