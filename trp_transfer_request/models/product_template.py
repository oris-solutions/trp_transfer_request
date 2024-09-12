# -*- coding: utf-8 -*-

from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    transfer_ok = fields.Boolean(string="Có thể điều chuyển", default=True)

