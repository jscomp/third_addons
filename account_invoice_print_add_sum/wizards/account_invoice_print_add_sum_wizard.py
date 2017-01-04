# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import api, fields, models, _
from openerp.exceptions import UserError, ValidationError

class account_invoice_print_add(models.TransientModel):
    """
        打印对账单
    """
    _name = 'account.invoice.print.add'

    name = fields.Many2one('account.invoice',u'发票', default=lambda self:self._context.get('active_id'))
    invoice_line_ids = fields.One2many('account.invoice.print.add.line','add_id',u'发票明细')

    @api.multi
    def btn_done(self):
        invoice_line_dict = {} #{源单据:[line_ids]}
        for line in self.name.invoice_line_ids:
            if line.purchase_id in invoice_line_dict:
                invoice_line_dict[line.purchase_id].append((4,line.id))
            else:
                invoice_line_dict[line.purchase_id] = [(4,line.id)]
        if invoice_line_dict:
            line_obj = self.env['account.invoice.print.add.line']
            for key, value in invoice_line_dict.items():
                line_obj.create({'name':key.id if key else '','add_id':self.id,'invoice_line_ids':value})

        return self.env['report'].get_action(self, 'account_invoice_print_add_sum.account_invoice_tfs')

class account_invoice_print_add_line(models.TransientModel):
    """
        对账单明细
    """
    _name = 'account.invoice.print.add.line'

    add_id = fields.Many2one('account.invoice.print.add',u'对账单')
    invoice_line_ids = fields.Many2many('account.invoice.line','line_line_rel','print_line_id','line_id',u'发票明细')
    all_quantity = fields.Float(u'数量', compute="_get_all_info")
    all_price_subtotal = fields.Float(u'金额', compute="_get_all_info")
    name = fields.Many2one('purchase.order',u'源单据')

    # 获取小计数据
    def _get_all_info(self):
        for ids in self:
            ids.all_quantity = 0
            ids.all_price_subtotal = 0
            for line in ids.invoice_line_ids:
                ids.all_quantity += line.quantity
                ids.all_price_subtotal += line.price_subtotal