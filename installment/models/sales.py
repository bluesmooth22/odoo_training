from odoo import api, fields, models, _


class InstallmentSales(models.Model):
    _inherit = 'sale.order'

    order_line = fields.One2many('sale.order.line', 'order_id', string='Order Lines',
                                 states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True, limit=1)
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

    installment_amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_compute_installment_amount',
                                     track_visibility='always')
    installment_amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_compute_installment_amount',
                                 track_visibility='always')
    installment_amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_compute_installment_amount',
                                   track_visibility='always')

    advance_payment = fields.Monetary(string='Advance', store=True, readonly=True, compute='_compute_installment_amount',
                                 track_visibility='always')
    spot_advance = fields.Monetary(string='Paid-up Advance', store=True, readonly=True, compute='_compute_installment_amount',
                                 track_visibility='always', help='Paidup Advance')
    is_spot_advance = fields.Boolean(default=False)
    deferred_advance = fields.Monetary(string='Deferred Advance', store=True, readonly=True, compute='_compute_installment_amount',
                                 track_visibility='always', help='Deferred Advance')
    is_deferred_advance = fields.Boolean(default=False)

    balance = fields.Monetary(string='Balance', store=True, readonly=True, compute='_compute_installment_amount',
                                 track_visibility='always')
    monthly_amortization = fields.Monetary(string='Monthly Amortization', store=True, readonly=True, compute='_compute_installment_amount',
                                 track_visibility='always')
    perpetual = fields.Monetary(string='PCF', store=True, readonly=True, compute='_compute_installment_amount',
                                 track_visibility='always')


    @api.depends('product_category_id', 'purchase_type', 'deferred_revenue_id', 'order_line', 'is_spot_advance', 'is_deferred_advance')
    def _compute_installment_amount(self):
        for order in self:
            company_id = order.env.user.company_id
            categ = self.env['deferred.revenue.category'].search([('product_category_id', '=', order.product_category_id.id), ('deferred_revenue_id', '=', order.deferred_revenue_id.id)])
            advance = 0.0
            unit_price = sum(line.price_unit for line in order.order_line)
            if categ.advance_payment_type == 'perc':
                advance = unit_price * (categ.advance_payment / 100)
            elif categ.advance_payment_type == 'fix':
                advance = categ.advance_payment
            else:
                advance = 0.0
            balance = unit_price - advance
            balance_with_interest = float(balance) * (1 + (categ.interest_rate / 100))
            monthly_amortization = balance_with_interest / order.deferred_revenue_id.number_of_months
            # print amort if (amort % 1 == 0) else round(amort + 0.5)
            deferred_adv = 0.0 if not advance else advance * (1 - (
                            order.deferred_revenue_id.deferred_adv_discount / 100.0))
            deferred_val = 0.0
            if not order.deferred_revenue_id.deferred_adv_count:
                deferred_val = deferred_adv
            elif order.deferred_revenue_id.deferred_adv_count:
                deferred_val = deferred_adv / order.deferred_revenue_id.deferred_adv_count,

            order.advance_payment = advance
            order.spot_advance = 0.0 if not advance else advance * (1 - (order.deferred_revenue_id.spot_adv_discount / 100.0))
            order.deferred_advance = deferred_val
            order.monthly_amortization = monthly_amortization

    @api.onchange('is_spot_advance')
    def _onchange_is_spot_advance(self):
        for order in self:
            if order.is_spot_advance and order.spot_advance:
                order.update({
                    'is_spot_advance': True, 'is_deferred_advance': False, 'note': 'Paid-up Downpayment'
                })
            else:
                order.update({
                    'is_spot_advance': False, 'is_deferred_advance': False, 'note': ''
                })

    @api.onchange('is_deferred_advance')
    def _onchange_is_deferred_advance(self):
        for order in self:
            if order.is_deferred_advance and order.deferred_advance:
                order.update({
                    'is_spot_advance': False, 'is_deferred_advance': True, 'note': 'Deferred Downpayment'
                })
            else:
                order.update({
                    'is_spot_advance': False, 'is_deferred_advance': False, 'note': ''
                })



class InstallmentSaleLine(models.Model):
    _inherit = 'sale.order.line'

    installment_price_subtotal = fields.Monetary(compute='_compute_installment_amount', string='Subtotal', readonly=True, store=True)
    installment_price_tax = fields.Monetary(compute='_compute_installment_amount', string='Taxes', readonly=True, store=True)
    installment_price_total = fields.Monetary(compute='_compute_installment_amount', string='Total', readonly=True, store=True)

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_installment_amount(self):
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)

            line.update({
                'installment_price_tax': '',
                'installment_price_total': '',
                'installment_price_subtotal': '',
            })

