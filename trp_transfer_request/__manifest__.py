# -*- coding: utf-8 -*-
{
    'name': 'Transfer Request',
    'summary': "Yêu cầu chuyển kho",
    'description': """"
        27/05- bổ sung in
    """,
    'author': 'HaiTran',
    'website': 'http://adiva.com.vn',

    'category': 'Customize/stock',
    'version': '1.0',

    'author': 'HaiTran',
    'depends': [
        'stock',
        'stock_account',
        'odoosmes_report',
    ],
    'sequence': 1,
    'data': [
        'security/ir.model.access.csv',
        'views/trp_transfer_request_view.xml',
        'data/ir_sequence_data.xml',
        'data/template_yeu_cau_chuyen_kho.xml',
        'views/product_template_view.xml'
    ],
}