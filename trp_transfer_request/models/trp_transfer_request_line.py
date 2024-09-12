# -*- coding: utf-8 -*-

from odoo import fields, models, api
from odoo.exceptions import Warning


class TrpTransferRequestLine(models.Model):
    _name = 'trp.transfer.request.line'

    trp_transfer_request_id = fields.Many2one('trp.transfer.request', string="Yêu cầu chuyển kho", copy=False)
    product_id = fields.Many2one('product.product', string="Sản phẩm")
    product_name = fields.Char(string="Mô tả")
    product_qty = fields.Float(string="Số lượng")
    product_uom = fields.Many2one('uom.uom', string="Đơn vị tính", related='product_id.uom_id')
    qty_delivered = fields.Float(string="Số lượng đã giao", copy=False)
    qty_receipted = fields.Float(string="Số lượng đã nhận", copy=False)
    qty_diff = fields.Float(string="Số lượng chênh lệch", compute="_compute_qty_diff", copy=False)
    lot_id = fields.Many2one('stock.production.lot', string="Số lô/sê-ri")
    move_ids = fields.One2many('stock.move', 'trp_transfer_request_line_id', string="Hoạt động kho")
    qty_in_warehouse = fields.Integer(copy=False)
    flag_product_available = fields.Integer(copy=False)
    icon_i = fields.Char()

    def _compute_qty_diff(self):
        for line in self:
            line.qty_diff = line.qty_delivered - line.qty_receipted

    def _get_procurement_group(self):
        return self.trp_transfer_request_id.procurement_group_id

    def _prepare_procurement_group_vals(self):
        return {
            'name': self.trp_transfer_request_id.name,
            'move_type': self.trp_transfer_request_id.move_type,
            'partner_id': self.trp_transfer_request_id.address_in_id.id,
        }

    def _prepare_procurement_values(self, group_id=False):
        values = {}
        self.ensure_one()
        date_planned = self.trp_transfer_request_id.date
        routes = self.trp_transfer_request_id.route_id
        values.update({
            'group_id': group_id,
            'date_planned': date_planned,
            'route_ids': routes,
            'lot_id': self.lot_id or False,
            'warehouse_id':   self.trp_transfer_request_id.warehouse_in_id,
            'location_id': self.trp_transfer_request_id.route_id.rule_ids[0].location_id.id,
            'partner_id': self.trp_transfer_request_id.address_in_id.id,
            'company_id': self.env.company.id,
        })
        return values

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """
        Launch procurement group run method with required/custom fields genrated by a
        sale order line. procurement group will launch '_run_pull', '_run_buy' or '_run_manufacture'
        depending on the sale order line product rule.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        procurements = []
        for line in self:
            group_id = line._get_procurement_group()
            if not group_id:
                group_id = self.env['procurement.group'].create(line._prepare_procurement_group_vals())
                line.trp_transfer_request_id.procurement_group_id = group_id
            else:
                # In case the procurement group is already created and the order was
                # cancelled, we need to update certain values of the group.
                updated_vals = {}
                if group_id.partner_id != line.trp_transfer_request_id.address_in_id:
                    updated_vals.update({'partner_id': line.trp_transfer_request_id.address_in_id.id})
                updated_vals.update({'move_type': self.trp_transfer_request_id.move_type})
                if updated_vals:
                    group_id.write(updated_vals)

            values = line._prepare_procurement_values(group_id=group_id)
            product_qty = line.product_qty

            line_uom = line.product_uom
            quant_uom = line.product_id.uom_id
            product_qty, procurement_uom = line_uom._adjust_uom_quantities(product_qty, quant_uom)
            procurements.append(self.env['procurement.group'].Procurement(
                line.product_id, product_qty, procurement_uom,
                line.trp_transfer_request_id.route_id.rule_ids[-1].location_id,
                'line.name', self.trp_transfer_request_id.name, self.env.company, values))
        if procurements:
            self.env['procurement.group'].run(procurements)
        return True

    def split_quantities(self):
        vals = {
            'product_id': self.product_id.id or False,
            'product_name': self.product_name or False,
            'product_qty': 1,
            'product_uom': self.product_uom.id or False,
            'trp_transfer_request_id': self.trp_transfer_request_id.id or False,
        }
        self.create(vals)

    @api.onchange('product_id')
    def onchange_product_name(self):
        self.write({
            'product_name': self.product_id.name,
        })

    # check duplicate line
    @api.onchange('lot_id')
    def onchange_product_id_lot_id(self):
        if self.lot_id:
            duplicate = self.trp_transfer_request_id.trp_transfer_request_line_ids.filtered(lambda line: line.product_id == self.product_id and line.lot_id == self.lot_id)
            if len(duplicate) > 2:
                raise Warning("Dòng line bị dupl_action_launch_stock_ruleicate")
