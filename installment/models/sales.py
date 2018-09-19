from itertools import groupby
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import formatLang

import odoo.addons.decimal_precision as dp


class InstallmentSales(models.Model):
    _name = 'installment.sale'
    _inherits = {'sale.order': 'sale_order_id'}

    sale_order_id = fields.Many2one(
        'sale.order', 'Installment Sale Reference',
        auto_join=True, index=True, ondelete="cascade", required=True)

    @api.depends('state', 'order_line.invoice_status')
    def _get_invoiced(self):
        for order in self:
            invoice_ids = order.order_line.mapped('invoice_lines').mapped('invoice_id').filtered(
                lambda r: r.type in ['out_invoice', 'out_refund'])
            refunds = invoice_ids.search(
                [('origin', 'like', order.name), ('company_id', '=', order.company_id.id)]).filtered(
                lambda r: r.type in ['out_invoice', 'out_refund'])
            invoice_ids |= refunds.filtered(lambda r: order.name in [origin.strip() for origin in r.origin.split(',')])
            refund_ids = self.env['account.invoice'].browse()
            if invoice_ids:
                for inv in invoice_ids:
                    refund_ids += refund_ids.search(
                        [('type', '=', 'out_refund'), ('origin', '=', inv.number), ('origin', '!=', False),
                         ('journal_id', '=', inv.journal_id.id)])

            deposit_product_id = self.env['sale.advance.payment.inv']._default_product_id()
            line_invoice_status = [line.invoice_status for line in order.order_line if
                                   line.product_id != deposit_product_id]

            if order.state not in ('sale', 'done'):
                invoice_status = 'no'
            elif any(invoice_status == 'to invoice' for invoice_status in line_invoice_status):
                invoice_status = 'to invoice'
            elif all(invoice_status == 'invoiced' for invoice_status in line_invoice_status):
                invoice_status = 'invoiced'
            elif all(invoice_status in ['invoiced', 'upselling'] for invoice_status in line_invoice_status):
                invoice_status = 'upselling'
            else:
                invoice_status = 'no'

            order.update({
                'invoice_count': len(set(invoice_ids.ids + refund_ids.ids)),
                'invoice_ids': invoice_ids.ids + refund_ids.ids,
                'invoice_status': invoice_status
            })

    @api.model
    def _default_note(self):
        return self.env.user.company_id.sale_note

    @api.model
    def _get_default_team(self):
        return self.env['crm.team']._get_default_team_id()

    @api.onchange('fiscal_position_id')
    def _compute_tax_id(self):
        for order in self:
            order.order_line._compute_tax_id()

    def _inverse_project_id(self):
        self.project_id = self.related_project_id

    name = fields.Char(string='Order Reference', required=True, copy=False, readonly=True,
                       states={'draft': [('readonly', False)]}, index=True, default=lambda self: _('New'))
    origin = fields.Char(string='Source Document',
                         help="Reference of the document that generated this sales order request.")
    client_order_ref = fields.Char(string='Customer Reference', copy=False)

    state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
    date_order = fields.Datetime(string='Order Date', required=True, readonly=True, index=True,
                                 states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, copy=False,
                                 default=fields.Datetime.now)
    validity_date = fields.Date(string='Expiration Date', readonly=True, copy=False,
                                states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                help="Manually set the expiration date of your quotation (offer), or it will set the date automatically based on the template if online quotation is installed.")
    create_date = fields.Datetime(string='Creation Date', readonly=True, index=True,
                                  help="Date on which sales order is created.")
    confirmation_date = fields.Datetime(string='Confirmation Date', readonly=True, index=True,
                                        help="Date on which the sale order is confirmed.", oldname="date_confirm",
                                        copy=False)
    user_id = fields.Many2one('res.users', string='Salesperson', index=True, track_visibility='onchange',
                              default=lambda self: self.env.user)

    partner_invoice_id = fields.Many2one('res.partner', string='Invoice Address', readonly=True, required=True,
                                         states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                         help="Invoice address for current sales order.")
    partner_shipping_id = fields.Many2one('res.partner', string='Delivery Address', readonly=True, required=True,
                                          states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                          help="Delivery address for current sales order.")

    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, readonly=True,
                                   states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                   help="Pricelist for current sales order.")
    currency_id = fields.Many2one("res.currency", related='pricelist_id.currency_id', string="Currency", readonly=True,
                                  required=True)
    project_id = fields.Many2one('account.analytic.account', 'Analytic Account', readonly=True,
                                 states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
                                 help="The analytic account related to a sales order.", copy=False)
    related_project_id = fields.Many2one('account.analytic.account', inverse='_inverse_project_id',
                                         related='project_id', string='Analytic Account',
                                         help="The analytic account related to a sales order.")

    order_line = fields.One2many('sale.order.line', 'order_id', string='Order Lines',
                                 states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True, limit=1)

    invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoiced', readonly=True)
    invoice_ids = fields.Many2many("account.invoice", string='Invoices', compute="_get_invoiced", readonly=True,
                                   copy=False)
    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
    ], string='Invoice Status', compute='_get_invoiced', store=True, readonly=True)

    note = fields.Text('Terms and conditions', default=_default_note)

    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms', oldname='payment_term')
    fiscal_position_id = fields.Many2one('account.fiscal.position', oldname='fiscal_position', string='Fiscal Position')
    company_id = fields.Many2one('res.company', 'Company',
                                 default=lambda self: self.env['res.company']._company_default_get('sale.order'))
    team_id = fields.Many2one('crm.team', 'Sales Team', change_default=True, default=_get_default_team,
                              oldname='section_id')
    procurement_group_id = fields.Many2one('procurement.group', 'Procurement Group', copy=False)

    # product_id = fields.Many2one('product.product', related='order_line.product_id', string='Product')

    product_category_id = fields.Many2one('product.category', 'Category', default=1, domain=[('parent_id', '=', False)])
    purchase_type = fields.Selection([('install', 'Installment'), ('cash', 'Cash')], default='install', string='Purchase Type')

    @api.multi
    @api.onchange('product_category_id', 'purchase_type')
    def _revenue_domain(self):
        ids = []
        for order in self:
            revenue_category = order.env['deferred.revenue.category'].search([('product_category_id', '=', order.product_category_id.id)])
        for rev in revenue_category:
            ids.append(rev.id)
        domain = [('covered_category_ids', 'in', ids), ('purchase_type', '=', self.purchase_type)]
        if self.product_category_id:
            self.deferred_revenue_id = False if not ids else ids[0]
        return {
            'domain': {'deferred_revenue_id': domain},
                }

    deferred_revenue_id = fields.Many2one('deferred.revenue.custom', 'Purchase Term',)

    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_compute_installment_amount',
                                     track_visibility='always')
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_compute_installment_amount',
                                 track_visibility='always')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_compute_installment_amount',
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

    @api.multi
    def _compute_order_line(self):
        price_subtotal = 0.0
        for order in self:
            if order.is_spot_advance:
                price_subtotal = order.spot_advance + (
                        order.monthly_amortization * order.deferred_revenue_id.number_of_months)
            elif order.is_deferred_advance:
                price_subtotal = (order.deferred_advance * order.deferred_revenue_id.deferred_adv_count) + (
                            order.monthly_amortization * order.deferred_revenue_id.number_of_months)
            for line in order.order_line:
                line.update({
                    'installment_price_subtotal': price_subtotal,
                })


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
            balance_with_interest = float(balance) * (1 + categ.interest_rate / 100)

            monthly_amortization = 0.0 if not order.deferred_revenue_id else balance_with_interest / int(order.deferred_revenue_id.number_of_months)
            # print amort if (amort % 1 == 0) else round(amort + 0.5)
            deferred_adv = 0.0 if not advance else advance * (1 - order.deferred_revenue_id.deferred_adv_discount / 100)
            def_val = deferred_adv / (1 if not order.deferred_revenue_id.deferred_adv_count else int(order.deferred_revenue_id.deferred_adv_count))

            order.update({
                'advance_payment': advance,
                'spot_advance': 0.0 if not advance else advance * (1 - order.deferred_revenue_id.spot_adv_discount / 100),
                'deferred_advance': def_val,
                'monthly_amortization': monthly_amortization,
            })
            order._compute_order_line()

    @api.onchange('is_spot_advance')
    def _onchange_is_spot_advance(self):
        for order in self:
            if order.is_spot_advance and order.spot_advance:
                order.update({
                    'is_spot_advance': True, 'is_deferred_advance': False, 'note': 'Paid-up Downpayment'
                })
            elif order.is_spot_advance and not order.spot_advance:
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
            elif order.is_deferred_advance and not order.deferred_advance:
                order.update({
                    'is_spot_advance': False, 'is_deferred_advance': False, 'note': ''
                })

    @api.model
    def _get_customer_lead(self, product_tmpl_id):
        return False

    @api.multi
    def button_dummy(self):
        return True

    @api.multi
    def unlink(self):
        for order in self:
            if order.state not in ('draft', 'cancel'):
                raise UserError(_('You can not delete a sent quotation or a sales order! Try to cancel it before.'))
        return super(InstallmentSales, self).unlink()

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'sale':
            return 'sale.mt_order_confirmed'
        elif 'state' in init_values and self.state == 'sent':
            return 'sale.mt_order_sent'
        return super(InstallmentSales, self)._track_subtype(init_values)

    @api.multi
    @api.onchange('partner_shipping_id', 'partner_id')
    def onchange_partner_shipping_id(self):
        """
        Trigger the change of fiscal position when the shipping address is modified.
        """
        self.fiscal_position_id = self.env['account.fiscal.position'].get_fiscal_position(self.partner_id.id,
                                                                                          self.partner_shipping_id.id)
        return {}

    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        """
        Update the following fields when the partner is changed:
        - Pricelist
        - Payment term
        - Invoice address
        - Delivery address
        """
        if not self.partner_id:
            self.update({
                'partner_invoice_id': False,
                'partner_shipping_id': False,
                'payment_term_id': False,
                'fiscal_position_id': False,
            })
            return

        addr = self.partner_id.address_get(['delivery', 'invoice'])
        values = {
            'pricelist_id': self.partner_id.property_product_pricelist and self.partner_id.property_product_pricelist.id or False,
            'payment_term_id': self.partner_id.property_payment_term_id and self.partner_id.property_payment_term_id.id or False,
            'partner_invoice_id': addr['invoice'],
            'partner_shipping_id': addr['delivery'],
        }
        if self.env.user.company_id.sale_note:
            values['note'] = self.with_context(lang=self.partner_id.lang).env.user.company_id.sale_note

        if self.partner_id.user_id:
            values['user_id'] = self.partner_id.user_id.id
        if self.partner_id.team_id:
            values['team_id'] = self.partner_id.team_id.id
        self.update(values)

    @api.onchange('partner_id')
    def onchange_partner_id_warning(self):
        if not self.partner_id:
            return
        warning = {}
        title = False
        message = False
        partner = self.partner_id

        # If partner has no warning, check its company
        if partner.sale_warn == 'no-message' and partner.parent_id:
            partner = partner.parent_id

        if partner.sale_warn != 'no-message':
            # Block if partner only has warning but parent company is blocked
            if partner.sale_warn != 'block' and partner.parent_id and partner.parent_id.sale_warn == 'block':
                partner = partner.parent_id
            title = ("Warning for %s") % partner.name
            message = partner.sale_warn_msg
            warning = {
                'title': title,
                'message': message,
            }
            if partner.sale_warn == 'block':
                self.update({'partner_id': False, 'partner_invoice_id': False, 'partner_shipping_id': False,
                             'pricelist_id': False})
                return {'warning': warning}

        if warning:
            return {'warning': warning}

    # @api.model
    # def create(self, vals):
    #     if vals.get('name', _('New')) == _('New'):
    #         if 'company_id' in vals:
    #             vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(
    #                 'installment.sale') or _('New')
    #         else:
    #             vals['name'] = self.env['ir.sequence'].next_by_code('installment.sale') or _('New')
    #
    #     # Makes sure partner_invoice_id', 'partner_shipping_id' and 'pricelist_id' are defined
    #     if any(f not in vals for f in ['partner_invoice_id', 'partner_shipping_id', 'pricelist_id']):
    #         partner = self.env['res.partner'].browse(vals.get('partner_id'))
    #         addr = partner.address_get(['delivery', 'invoice'])
    #         vals['partner_invoice_id'] = vals.setdefault('partner_invoice_id', addr['invoice'])
    #         vals['partner_shipping_id'] = vals.setdefault('partner_shipping_id', addr['delivery'])
    #         vals['pricelist_id'] = vals.setdefault('pricelist_id',
    #                                                partner.property_product_pricelist and partner.property_product_pricelist.id)
    #     result = super(InstallmentSales, self).create(vals)
    #     return result

    @api.multi
    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
        if not journal_id:
            raise UserError(_('Please define an accounting sale journal for this company.'))
        invoice_vals = {
            'name': self.client_order_ref or '',
            'origin': self.name,
            'type': 'out_invoice',
            'account_id': self.partner_invoice_id.property_account_receivable_id.id,
            'partner_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'journal_id': journal_id,
            'currency_id': self.pricelist_id.currency_id.id,
            'comment': self.note,
            'payment_term_id': self.payment_term_id.id,
            'fiscal_position_id': self.fiscal_position_id.id or self.partner_invoice_id.property_account_position_id.id,
            'company_id': self.company_id.id,
            'user_id': self.user_id and self.user_id.id,
            'team_id': self.team_id.id
        }
        return invoice_vals

    @api.multi
    def print_quotation(self):
        self.filtered(lambda s: s.state == 'draft').write({'state': 'sent'})
        return self.env['report'].get_action(self, 'sale.report_saleorder')

    @api.multi
    def action_view_invoice(self):
        invoices = self.mapped('invoice_ids')
        action = self.env.ref('account.action_invoice_tree1').read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def action_invoice_create(self, grouped=False, final=False):
        """
        Create the invoice associated to the SO.
        :param grouped: if True, invoices are grouped by SO id. If False, invoices are grouped by
                        (partner_invoice_id, currency)
        :param final: if True, refunds will be generated if necessary
        :returns: list of created invoices
        """
        inv_obj = self.env['account.invoice']
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        invoices = {}
        references = {}
        invoices_origin = {}
        invoices_name = {}

        for order in self:
            group_key = order.id if grouped else (order.partner_invoice_id.id, order.currency_id.id)
            for line in order.order_line.sorted(key=lambda l: l.qty_to_invoice < 0):
                if float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    continue
                if group_key not in invoices:
                    inv_data = order._prepare_invoice()
                    invoice = inv_obj.create(inv_data)
                    references[invoice] = order
                    invoices[group_key] = invoice
                    invoices_origin[group_key] = [invoice.origin]
                    invoices_name[group_key] = [invoice.name]
                elif group_key in invoices:
                    if order.name not in invoices_origin[group_key]:
                        invoices_origin[group_key].append(order.name)
                    if order.client_order_ref and order.client_order_ref not in invoices_name[group_key]:
                        invoices_name[group_key].append(order.client_order_ref)

                if line.qty_to_invoice > 0:
                    line.invoice_line_create(invoices[group_key].id, line.qty_to_invoice)
                elif line.qty_to_invoice < 0 and final:
                    line.invoice_line_create(invoices[group_key].id, line.qty_to_invoice)

            if references.get(invoices.get(group_key)):
                if order not in references[invoices[group_key]]:
                    references[invoice] = references[invoice] | order

        for group_key in invoices:
            invoices[group_key].write({'name': ', '.join(invoices_name[group_key]),
                                       'origin': ', '.join(invoices_origin[group_key])})

        if not invoices:
            raise UserError(_('There is no invoicable line.'))

        for invoice in invoices.values():
            if not invoice.invoice_line_ids:
                raise UserError(_('There is no invoicable line.'))
            # If invoice is negative, do a refund invoice instead
            if invoice.amount_untaxed < 0:
                invoice.type = 'out_refund'
                for line in invoice.invoice_line_ids:
                    line.quantity = -line.quantity
            # Use additional field helper function (for account extensions)
            for line in invoice.invoice_line_ids:
                line._set_additional_fields(invoice)
            # Necessary to force computation of taxes. In account_invoice, they are triggered
            # by onchanges, which are not triggered when doing a create.
            invoice.compute_taxes()
            invoice.message_post_with_view('mail.message_origin_link',
                                           values={'self': invoice, 'origin': references[invoice]},
                                           subtype_id=self.env.ref('mail.mt_note').id)
        return [inv.id for inv in invoices.values()]

    @api.multi
    def action_draft(self):
        orders = self.filtered(lambda s: s.state in ['cancel', 'sent'])
        orders.write({
            'state': 'draft',
            'procurement_group_id': False,
        })
        return orders.mapped('order_line').mapped('procurement_ids').write({'sale_line_id': False})

    @api.multi
    def action_cancel(self):
        return self.write({'state': 'cancel'})

    @api.multi
    def action_done(self):
        return self.write({'state': 'done'})

    def _prepare_procurement_group(self):
        return {'name': self.name}

    @api.multi
    def action_confirm(self):
        for order in self:
            order.state = 'sale'
            order.confirmation_date = fields.Datetime.now()
            if self.env.context.get('send_email'):
                self.force_quotation_send()
            order.order_line._action_procurement_create()
        if self.env['ir.values'].get_default('sale.config.settings', 'auto_done_setting'):
            self.action_done()
        return True

    @api.multi
    def _create_analytic_account(self, prefix=None):
        for order in self:
            name = order.name
            if prefix:
                name = prefix + ": " + order.name
            analytic = self.env['account.analytic.account'].create({
                'name': name,
                'code': order.client_order_ref,
                'company_id': order.company_id.id,
                'partner_id': order.partner_id.id
            })
            order.project_id = analytic

    @api.multi
    def order_lines_layouted(self):
        self.ensure_one()
        report_pages = [[]]
        for category, lines in groupby(self.order_line, lambda l: l.layout_category_id):
            if report_pages[-1] and report_pages[-1][-1]['pagebreak']:
                report_pages.append([])
            # Append category to current report page
            report_pages[-1].append({
                'name': category and category.name or _('Uncategorized'),
                'subtotal': category and category.subtotal,
                'pagebreak': category and category.pagebreak,
                'lines': list(lines)
            })

        return report_pages

    @api.multi
    def _get_tax_amount_by_group(self):
        self.ensure_one()
        res = {}
        currency = self.currency_id or self.company_id.currency_id
        for line in self.order_line:
            price_reduce = line.price_unit * (1.0 - line.discount / 100.0)
            taxes = line.tax_id.compute_all(price_reduce, quantity=line.product_uom_qty, product=line.product_id,
                                            partner=self.partner_shipping_id)['taxes']
            for tax in line.tax_id:
                group = tax.tax_group_id
                res.setdefault(group, 0.0)
                for t in taxes:
                    if t['id'] == tax.id or t['id'] in tax.children_tax_ids.ids:
                        res[group] += t['amount']
        res = sorted(res.items(), key=lambda l: l[0].sequence)
        res = map(lambda l: (l[0].name, l[1]), res)
        return res


