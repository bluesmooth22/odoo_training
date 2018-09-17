from odoo import api, fields, models, _

class DeferredRevenue(models.Model):
    _name = 'deferred.revenue.custom'

    name = fields.Char('Name')
    number_of_months = fields.Integer('Number of Months', default=0)
    covered_category_ids = fields.One2many('deferred.revenue.category', 'deferred_revenue_id', 'Covered Categories')


class DeferredRevenueCategory(models.Model):
    _name = 'deferred.revenue.category'

    deferred_revenue_id = fields.Many2one('deferred.revenue.custom')
    product_category_id = fields.Many2one('product.category')
    interest_rate_type = fields.Selection([('month', 'Compute per Month'), ('whole', 'Compute from Balance')])
    interest_rate = fields.Float()
    advance_payment_type = fields.Selection([('perc', '% of Selling Price'), ('fix', 'Fixed'), ('none', 'None')], default='perc', string='Advance Payment')
    advance_payment = fields.Float(default=0.0)