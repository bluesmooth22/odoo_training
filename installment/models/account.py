from odoo import api, fields, models, _

class InstallmentAccountInvoice(models.Model):
    _name = 'installment.account.invoice'
    _inherit = 'account.invoice'

