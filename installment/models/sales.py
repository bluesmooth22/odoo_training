from odoo import api, fields, models, _


class InstallmentSales(models.Model):
    _inherit = 'sale.order'

    product_category_id = fields.Many2one('product.category', 'Category', domain=[('parent_id', '=', False)], default=0)
    purchase_type = fields.Selection([('install', 'Installment'), ('cash', 'Cash')], default='install', string='Purchase Type')

    @api.onchange('product_category_id', 'purchase_type')
    def _revenue_domain(self):
        ids = []
        for order in self:
            revenue_category = order.env['deferred.revenue.category'].search([('product_category_id', '=', order.product_category_id.id)])
        for rev in revenue_category:
            ids.append(rev.id)
        domain = [('covered_category_ids', 'in', ids), ('purchase_type', '=', self.purchase_type)]
        self.deferred_revenue_id = False if not ids else ids[0]
        return {'domain': {'deferred_revenue_id': domain}}

    deferred_revenue_id = fields.Many2one('deferred.revenue.custom', 'Purchase Term',)


class InstallmentSaleLine(models.Model):
    _inherit = 'sale.order.line'

