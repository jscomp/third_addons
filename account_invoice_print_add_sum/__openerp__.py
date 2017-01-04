# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': '账单打印根据源单据增加合计行',
    'version': '1.1',
    'summary': 'account_invoice_print_add_sum',
    'description': """
        1：账单打印中增加“对账单打印”
        2：在原有发票打印的基础上，按照源单据增加合计行
    """,
    'author': "linyinhuan@139.com",
    'website': "http://www.jscomp.cn",
    'depends': ['base','account','report','purchase'],
    'category': 'account',
    'sequence': 13,
    'demo': [
    ],
    'data': [
        'report/account_invoice_print_add_sum_report.xml',
        'views/account_invoice_tfs.xml',
        'wizards/account_invoice_print_add_sum_wizard.xml',
    ],
    'test': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
