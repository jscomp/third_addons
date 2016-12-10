# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import api, fields, models, _
from openerp.exceptions import UserError, ValidationError


class stock_picking_in_merge(models.TransientModel):
    """
        合并处理入库单
    """
    _name = 'stock.picking.in.merge'

    partner_id = fields.Many2one('res.partner', u'业务伙伴')
    location_id = fields.Many2one('stock.location', u'目标库位')
    line_ids = fields.One2many('stock.picking.in.merge.line', 'merge_id', u'产品')
    select_ids = fields.Char(u'选中的调拨单')

    # 合并入库
    @api.multi
    def btn_merge(self):
        # 按照id顺序排序需要处理的入库单
        res_pick_ids = []
        for res_pick_id in self.select_ids.strip('[').strip(']').split(','):
            res_pick_ids.append(int(res_pick_id))
        picking_ids = self.env['stock.picking'].search([('id', 'in', res_pick_ids)], order="id")
        # 获取入库的产品及数量
        product_dict = {}  # {产品:数量}
        product_list = []
        product_lot_dict = {}  # {入库单:{产品:批次}}
        for line in self.line_ids:
            if line.product_qty > line.qty_done:
                raise UserError(_(u'产品完成数量不能大于待办数量！'))
            if line.product_qty <= 0:
                raise UserError(_(u'产品完成数量不能小于或等于零！'))
            product_dict[line.product_id] = line.product_qty
            product_list.append(line.product_id.id)
            for line_1 in line.order_line:
                for line_2 in line_1.order_line:
                    if line_2.picking_id in product_lot_dict:
                        product_lot_dict[line_2.picking_id][line_1.product_id] = line_2.lot_name
                    else:
                        product_lot_dict[line_2.picking_id] = {line_1.product_id: line_2.lot_name}
        operation_obj = self.env['stock.pack.operation']
        operation_lot_obj = self.env['stock.pack.operation.lot']
        # 循环处理所有的入库单
        for picking_id in picking_ids:
            operation_ids = operation_obj.search(
                [('picking_id', '=', picking_id.id), ('product_id', 'in', product_list)])
            if operation_ids:
                for operation_id in operation_ids:
                    print
                    if operation_id.product_qty < product_dict.get(operation_id.product_id):
                        product_dict[operation_id.product_id] = product_dict.get(
                            operation_id.product_id) - operation_id.product_qty
                        if operation_id.product_id.tracking == 'lot':
                            operation_lot_obj.create({'operation_id': operation_id.id,
                                                  'lot_name': product_lot_dict[picking_id][operation_id.product_id],
                                                  'qty': operation_id.product_qty})
                        else:
                            operation_id.write({'qty_done':operation_id.product_qty})
                    else:
                        product_list.remove(operation_id.product_id.id)
                        if operation_id.product_id.tracking == 'lot':
                            operation_lot_obj.create({'operation_id': operation_id.id,
                                                  'lot_name': product_lot_dict[picking_id][operation_id.product_id],
                                                  'qty': product_dict.get(operation_id.product_id)})
                        else:
                            operation_id.write({'qty_done':product_dict.get(operation_id.product_id)})
                        product_dict[operation_id.product_id] = 0
                    if operation_id.product_id.tracking == 'lot':
                        operation_id.save()
                return_res = picking_id.do_new_transfer()
                if type(return_res) == dict:
                    if return_res.get('res_model') == 'stock.backorder.confirmation':
                        self.env['stock.backorder.confirmation'].browse(return_res.get('res_id')).process()
        return True

    # 确认合并
    @api.multi
    def btn_done(self):
        picking_obj = self.env['stock.picking']
        purchase_obj = self.env['purchase.order']
        picking_ids = picking_obj.browse(self._context.get('active_ids'))
        partner_id = ''
        location = ''
        product_dict = {}  # {产品:数量}
        purchase_dict = {}  # {产品:{入库单:数量}}
        select_ids = str(self._context.get('active_ids'))
        for picking_id in picking_ids:
            # 获取业务伙伴默认值
            if partner_id and picking_id.partner_id != partner_id:
                raise UserError(_(u'只有相同业务伙伴的入库单才能合并入库！'))
            partner_id = picking_id.partner_id
            # 获取目标库位默认值
            if location and picking_id.location_dest_id != location:
                raise UserError(_(u'只有相同目的库位的入库单才能合并入库！'))
            location = picking_id.location_dest_id
            # 获取产品列表
            if picking_id.state not in ('assigned', 'partially'):
                raise UserError(_(u'只有部分可用和可用状态的的入库单才能合并入库！'))
            if picking_id.picking_type_id.code != 'incoming':
                raise UserError(_(u'只有入库单才能合并入库！'))

            for line in picking_id.move_lines_related:
                if line.state == 'assigned':
                    if line.product_id in product_dict:
                        product_dict[line.product_id] += line.product_uom_qty
                        if picking_id in purchase_dict[line.product_id]:
                            purchase_dict[line.product_id][picking_id] += line.product_uom_qty
                        else:
                            purchase_dict[line.product_id][picking_id] = line.product_uom_qty
                    else:
                        product_dict[line.product_id] = line.product_uom_qty
                        purchase_dict[line.product_id] = {picking_id: line.product_uom_qty}
        line_ids = []
        for key, value in product_dict.items():
            line_ids.append((0, 0, {'product_id': key.id, 'qty_done': value, 'product_qty': value}))
        res_id = self.create({'select_ids':select_ids,'partner_id': partner_id.id, 'location_id': location.id, 'line_ids': line_ids})
        # 循环产品，为产品创建对应的批次
        lot_obj = self.env['stock.picking.in.merge.lot']
        move_obj = self.env['stock.move']
        lot_line_obj = self.env['stock.picking.in.merge.lot.line']
        for line in res_id.line_ids:
            if line.product_id.tracking:
                lot_id = lot_obj.create({'line_id': line.id, 'product_id': line.product_id.id, 'qty_done': line.qty_done})
                for key, value in purchase_dict[line.product_id].items():
                    # 获取每个入库单对应的采购单
                    purchase_id = purchase_obj.search([('name', '=', key.origin)])
                    if purchase_id:
                        if purchase_id[0].partner_ref:
                            if not key.backorder_id:
                                lot_line_obj.create(
                                    {'picking_id': key.id, 'lot_id': lot_id.id, 'lot_name': purchase_id[0].partner_ref,
                                     'qty_done': value})
                            else:
                                picking_id_obj = key.backorder_id
                                pick_res = 0
                                while picking_id_obj:
                                    move_ids = move_obj.search([('picking_id','=',picking_id_obj.id),('product_id','=',line.product_id.id)])
                                    if move_ids:
                                        pick_res += 1
                                    picking_id_obj = picking_id_obj.backorder_id
                                if pick_res:
                                    lot_name = purchase_id[0].partner_ref + '[' + str(pick_res) + ']'
                                else:
                                    lot_name = purchase_id[0].partner_ref
                                lot_line_obj.create({'picking_id': key.id, 'lot_id': lot_id.id,
                                                     'lot_name': lot_name,'qty_done': value})
                        else:
                            raise UserError(_(u'采购订单%s无法获取供应商参考，请手工指定批次号！')%purchase_id.name)

        view = self.env['ir.model.data'].xmlid_to_res_id('stock_picking_in_merge.form_stock_picking_in_merge')
        return {
            'name': _('合并入库'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.picking.in.merge',
            'views': [(view, 'form')],
            'view_id': view,
            'target': 'new',
            'res_id': res_id.id,
        }

class stock_picking_in_merge_line(models.TransientModel):
    """
        合并处理入库单产品明细
    """
    _name = 'stock.picking.in.merge.line'

    merge_id = fields.Many2one('stock.picking.in.merge', u'合并入库单')
    product_id = fields.Many2one('product.product', u'产品明细')
    tracking = fields.Selection([('serial', 'By Unique Serial Number'), ('lot', 'By Lots'), ('none', 'No Tracking')], related='product_id.tracking')
    qty_done = fields.Float(u'待办')
    product_qty = fields.Float(u'完成', compute="get_product_qty")
    order_line = fields.One2many('stock.picking.in.merge.lot', 'line_id', u'批次')

    # 计算批次中的数量
    def get_product_qty(self):
        for ids in self:
            ids.product_qty = 0
            for line in ids.order_line:
                ids.product_qty += line.product_qty

    # 查看批次
    @api.multi
    def split_lot(self):
        lot_obj = self.env['stock.picking.in.merge.lot']
        lot_id = lot_obj.search([('line_id', '=', self.id)])
        if not lot_id:
            lot_id = lot_obj.create({'line_id': self.id, 'product_id': self.product_id.id, 'qty_done': self.qty_done})
        view = self.env['ir.model.data'].xmlid_to_res_id('stock_picking_in_merge.form_stock_picking_in_merge_lot')
        return {
            'name': _('批次详细信息'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.picking.in.merge.lot',
            'views': [(view, 'form')],
            'view_id': view,
            'target': 'new',
            'res_id': lot_id.id,
        }

class stock_picking_in_merge_lot(models.TransientModel):
    """
        合并处理入库单的批次明细
    """
    _name = 'stock.picking.in.merge.lot'

    line_id = fields.Many2one('stock.picking.in.merge.line', u'入库明细')
    product_id = fields.Many2one('product.product', u'产品')
    order_line = fields.One2many('stock.picking.in.merge.lot.line', 'lot_id', u'明细')
    qty_done = fields.Float(u'完成')
    product_qty = fields.Float(u'完成', compute="_get_product_qty")

    def _get_product_qty(self):
        for ids in self:
            ids.product_qty = 0
            for line in ids.order_line:
                ids.product_qty += line.qty_done

    # 保存
    @api.multi
    def btn_save(self):
        view = self.env['ir.model.data'].xmlid_to_res_id('stock_picking_in_merge.form_stock_picking_in_merge')
        return {
            'name': _('合并入库'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.picking.in.merge',
            'views': [(view, 'form')],
            'view_id': view,
            'target': 'new',
            'res_id': self.env['stock.picking.in.merge.line'].browse(self._context.get('active_id')).merge_id.id,
        }

    # 取消
    @api.multi
    def btn_cancel(self):
        view = self.env['ir.model.data'].xmlid_to_res_id('stock_picking_in_merge.form_stock_picking_in_merge')
        return {
            'name': _('合并入库'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.picking.in.merge',
            'views': [(view, 'form')],
            'view_id': view,
            'target': 'new',
            'res_id': self.env['stock.picking.in.merge.line'].browse(self._context.get('active_id')).merge_id.id,
        }

class stock_picking_in_merge_lot_line(models.TransientModel):
    """
        合并处理入库单的批次
    """
    _name = 'stock.picking.in.merge.lot.line'

    lot_id = fields.Many2one('stock.picking.in.merge.lot', u'产品')
    picking_id = fields.Many2one('stock.picking', u'入库单')
    lot_name = fields.Char(u'批次名称')
    qty_done = fields.Float(u'完成')

class stock_picking_inherit(models.Model):
    """
        入库单增加采购单供应商参考字段
    """
    _inherit = 'stock.picking'

    partner_ref = fields.Char(u'业务伙伴参考')

    # 创建调拨单的时候，根据源文件获取对应的业务伙伴参考
    @api.model
    def create(self, vals):
        res = super(stock_picking_inherit, self).create(vals)
        if res.origin:
            partner_ref = ''
            sale_id = self.env['sale.order'].search([('name', '=', res.origin)])
            if sale_id:
                partner_ref = sale_id[0].client_order_ref
            purchase_id = self.env['purchase.order'].search([('name', '=', res.origin)])
            if purchase_id:
                partner_ref = purchase_id[0].partner_ref
            if partner_ref:
                res.write({'partner_ref': partner_ref})
        return res
