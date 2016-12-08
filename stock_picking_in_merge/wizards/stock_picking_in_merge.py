# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import api, fields, models, _
from openerp.exceptions import UserError, ValidationError

class stock_picking_in_merge(models.TransientModel):
    """
        合并处理入库单
    """
    _name = 'stock.picking.in.merge'

    # 获取业务伙伴默认值
    @api.multi
    def _get_partner_id(self):
        picking_obj = self.env['stock.picking']
        picking_ids = picking_obj.browse(self._context.get('active_ids'))
        partner_id = ''
        for picking_id in picking_ids:
            if partner_id and picking_id.partner_id != partner_id:
                raise UserError(_(u'只有相同业务伙伴的入库单才能合并入库！'))
            partner_id = picking_id.partner_id
        return partner_id

    # 获取目标库位默认值
    @api.multi
    def _get_location_id(self):
        picking_obj = self.env['stock.picking']
        picking_ids = picking_obj.browse(self._context.get('active_ids'))
        location = ''
        for picking_id in picking_ids:
            if location and picking_id.location_dest_id != location:
                raise UserError(_(u'只有相同目的库位的入库单才能合并入库！'))
            location = picking_id.location_dest_id
        return location

    # 获取产品列表
    @api.multi
    def _get_line_ids(self):
        picking_obj = self.env['stock.picking']
        picking_ids = picking_obj.browse(self._context.get('active_ids'))
        product_dict = {} #{产品:数量}
        for picking_id in picking_ids:
            if picking_id.state not in ('assigned','partially'):
                raise UserError(_(u'只有部分可用和可用状态的的入库单才能合并入库！'))
            if picking_id.picking_type_id.code != 'incoming':
                raise UserError(_(u'只有入库单才能合并入库！'))
            for line in picking_id.move_lines_related:
                if line.state == 'assigned':
                    if line.product_id in product_dict:
                        product_dict[line.product_id] += line.product_uom_qty
                    else:
                        product_dict[line.product_id] = line.product_uom_qty
        line_ids = []
        for key, value in product_dict.items():
            line_ids.append((0,0,{'product_id':key.id,'qty_done':value,'product_qty':value}))
        return line_ids

    partner_id = fields.Many2one('res.partner',u'业务伙伴', default=_get_partner_id)
    location_id = fields.Many2one('stock.location',u'目标库位', default=_get_location_id)
    line_ids = fields.One2many('stock.picking.in.merge.line','merge_id',u'产品', default=_get_line_ids)

    # 合并入库
    @api.multi
    def btn_merge(self):
        # 按照id顺序排序需要处理的入库单
        picking_ids = self.env['stock.picking'].search([('id','in',self._context.get('active_ids'))], order="id")
        # 获取入库的产品及数量
        product_dict = {} #{产品:数量}
        product_list = []
        for line in self.line_ids:
            if line.product_qty > line.qty_done:
                raise UserError(_(u'产品完成数量不能大于待办数量！'))
            if line.product_qty <= 0:
                raise UserError(_(u'产品完成数量不能小于或等于零！'))
            product_dict[line.product_id] = line.product_qty
            product_list.append(line.product_id.id)
        operation_obj = self.env['stock.pack.operation']
        # 循环处理所有的入库单
        for picking_id in picking_ids:
            operation_ids = operation_obj.search([('picking_id','=',picking_id.id),('product_id','in',product_list)])
            for operation_id in operation_ids:
                if operation_id.product_qty < product_dict.get(operation_id.product_id):
                    operation_id.write({'qty_done':operation_id.product_qty})
                    product_dict[operation_id.product_id] = product_dict.get(operation_id.product_id) - operation_id.product_qty
                else:
                    operation_id.write({'qty_done':product_dict.get(operation_id.product_id)})
                    product_dict[operation_id.product_id] = 0
                    product_list.remove(operation_id.product_id.id)
            return_res = picking_id.do_new_transfer()
            if type(return_res) == dict:
                if return_res.get('res_model') == 'stock.backorder.confirmation':
                    self.env['stock.backorder.confirmation'].browse(return_res.get('res_id')).process()
        return True

class stock_picking_in_merge_line(models.TransientModel):
    """
        合并处理入库单产品明细
    """
    _name = 'stock.picking.in.merge.line'

    merge_id = fields.Many2one('stock.picking.in.merge',u'合并入库单')
    product_id = fields.Many2one('product.product',u'产品明细')
    qty_done = fields.Float(u'待办')
    product_qty = fields.Float(u'完成')


