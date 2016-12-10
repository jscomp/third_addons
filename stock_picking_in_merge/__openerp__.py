# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': '入库单合并入库',
    'version': '1.1',
    'summary': 'stock_picking_in_merge',
    'description': """
        1：在入库单订单列表更多中增加按钮“合并入库”
        2：选择需要合并入库的入库单，点击合并入库按钮
        3：选择入库的产品数量，根据时间先后的顺序处理选中的订单
        4：销售订单生成出库单和采购订单生成入库单增加对应业务伙伴的业务伙伴参考信息
    """,
    'author': "linyinhuan@139.com",
    'website': "http://www.jscomp.cn",
    'depends': ['base','stock','purchase','sale'],
    'category': 'stock',
    'sequence': 13,
    'demo': [
    ],
    'data': [
        'wizard/stock_picking_in_merge.xml',
    ],
    'test': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
