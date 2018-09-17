from odoo import api, fields, models, _

class DeferredRevenue(models.Model):
    _name = 'deferred.revenue.custom'

    name = fields.Char('Name')
    number_of_months = fields.Integer('Number of Months', default=0)
    covered_category_ids = fields.One2many('deferred.revenue.category', 'deferred_revenue_id', 'Covered Categories')
    purchase_type = fields.Selection([('install', 'Installment'), ('cash', 'Cash')], default='install',
                                     string='Purchase Type')

    spot_adv_discount = fields.Float(default=0.0, string='Paid-up Advances')
    deferred_adv_discount = fields.Float(default=0.0, string='Deferred Advances')
    deferred_adv_count = fields.Integer(default=0, string='Deferred Advances Count')

class DeferredRevenueCategory(models.Model):
    _name = 'deferred.revenue.category'

    deferred_revenue_id = fields.Many2one('deferred.revenue.custom')
    product_category_id = fields.Many2one('product.category', string='Category')
    interest_type = fields.Selection([('simple', 'Simple'), ('compound', 'Compound')], default='simple')
    interest_rate = fields.Float(string='Interest rate (%)')
    advance_payment_type = fields.Selection([('perc', '% of Selling Price'), ('fix', 'Fixed'), ('none', 'None')], default='perc', string='Advance Payment')
    advance_payment = fields.Float(default=0.0)

