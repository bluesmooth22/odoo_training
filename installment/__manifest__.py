# -*- coding: utf-8 -*-
{
    'name': "installment",
    'summary': """
        """,
    'description': """
    """,
    'author': "My Company",
    'website': "http://www.yourcompany.com",
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['base','sale','account','product', 'account_accountant', 'stock'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/view.xml',
        'views/sales.xml',
        'views/revenue.xml',
        'views/tax.xml',
        'views/product.xml',
    ],
}