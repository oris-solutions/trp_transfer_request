# -*- coding: utf-8 -*-

from odoo import fields, models, _


class StockMove(models.Model):
    _inherit = 'stock.move'

    trp_transfer_request_line_id = fields.Many2one('trp.transfer.request.line', string="Chi tiết yêu cầu")

    def update_quantity_transfer_request_line(self):
        rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        # 1. Cập nhật số lượng đã xuất, đã nhập cho Phiếu yêu cầu
        #   Phiếu xuất hoàn thành
        warehouse_out_id = self.picking_id.trp_transfer_request_id.warehouse_out_id

        qty_delivered = round(sum(self.picking_id.trp_transfer_request_id.picking_ids.filtered(
            lambda x: x.state in ('done') and x.location_id.usage == 'internal' and x.location_id.get_warehouse() == warehouse_out_id).move_lines.filtered(
            lambda x: x.product_id == self.product_id).mapped('quantity_done')), rounding)

        qty_delivered = qty_delivered - round(sum(self.picking_id.trp_transfer_request_id.picking_ids.filtered(
            lambda x: x.state in ('done') and x.location_dest_id.usage == 'internal' and x.location_dest_id.get_warehouse() == warehouse_out_id).move_lines.filtered(
            lambda x: x.product_id == self.product_id).mapped(
            'quantity_done')), rounding)

        #   Phiếu nhập hoàn thành
        warehouse_in_id = self.picking_id.trp_transfer_request_id.warehouse_in_id

        qty_receipted = round(sum(self.picking_id.trp_transfer_request_id.picking_ids.filtered(
            lambda x: x.state in ('done') and x.location_dest_id.usage == 'internal' and x.location_dest_id.get_warehouse() == warehouse_in_id).move_lines.filtered(
            lambda x: x.product_id == self.product_id).mapped('quantity_done')), rounding)

        qty_receipted = qty_receipted - round(sum(self.picking_id.trp_transfer_request_id.picking_ids.filtered(
            lambda x: x.state in ('done') and x.location_id.usage == 'internal' and x.location_id.get_warehouse() == warehouse_in_id).move_lines.filtered(
            lambda x: x.product_id == self.product_id).mapped(
            # lambda x: x.product_id == self.product_id and x.origin_returned_move_id.id != False).mapped(
            'quantity_done')), rounding)

        # picking_done_inbounds = self.picking_id.trp_transfer_request_id.picking_ids.filtered(
        #     lambda x: x.state in ('done') and x.location_dest_id.usage == 'internal')
        # if picking_done_inbounds:
        #     self._cr.execute(
        #         'select sum(quantity_done) from stock_move where picking_id in %s and product_id = %s',
        #         [tuple(picking_done_inbounds.ids), self.product_id.id])
        #     results = self._cr.fetchall()
        #     if results:
        #         qty_receipted = results[0][0]

        #   Cập nhật Phiếu yêu cầu
        trp_transfer_request_line_ids = self.picking_id.trp_transfer_request_id.trp_transfer_request_line_ids.filtered(
            lambda x: x.product_id == self.product_id)
        for item in trp_transfer_request_line_ids:
            item["qty_delivered"] = qty_delivered
            item["qty_receipted"] = qty_receipted

    def update_quantity_inbound(self):
        rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        # 1. Cập nhật số lượng đã xuất, đã nhập cho Phiếu yêu cầu
        #   Phiếu xuất hoàn thành

        qty_delivered = round(sum(self.picking_id.trp_transfer_request_id.picking_ids.filtered(
            lambda x: x.state in ('done') and x.location_id.usage == 'internal').move_lines.filtered(
            lambda x: x.product_id == self.product_id).mapped('quantity_done')), rounding)

        qty_receipted = round(sum(self.picking_id.trp_transfer_request_id.picking_ids.filtered(
            lambda x: x.state in ('done') and x.location_dest_id.usage == 'internal').move_lines.filtered(
            lambda x: x.product_id == self.product_id).mapped('quantity_done')), rounding)

        # picking_done_inbounds = self.picking_id.trp_transfer_request_id.picking_ids.filtered(
        #     lambda x: x.state in ('done') and x.location_dest_id.usage == 'internal')
        # if picking_done_inbounds:
        #     self._cr.execute(
        #         'select sum(product_uom_qty) from stock_move where picking_id in %s and product_id = %s',
        #         [tuple(picking_done_inbounds.ids), self.product_id.id])
        #     results = self._cr.fetchall()
        #     if results:
        #         qty_receipted = results[0][0]

        # 2. Cập nhật cho phiếu Inbound
        #   Dự báo xuất
        qty_delivered_target = round(sum(self.picking_id.trp_transfer_request_id.picking_ids.filtered(
            lambda x: x.state in ('confirmed', 'assigned', 'done') and x.location_id.usage == 'internal').move_lines.filtered(
            lambda x: x.product_id == self.product_id).mapped('product_uom_qty')), rounding)

        #   Dự báo nhập
        qty_receipted_target = round(sum(self.picking_id.trp_transfer_request_id.picking_ids.filtered(
            lambda x: x.state in ('confirmed', 'assigned', 'done') and x.location_dest_id.usage == 'internal').move_lines.filtered(
            lambda x: x.product_id == self.product_id).mapped('product_uom_qty')), rounding)

        # picking_inbounds = self.picking_id.trp_transfer_request_id.picking_ids.filtered(
        #     lambda x: x.state in ('confirmed', 'assigned', 'done') and x.location_dest_id.usage == 'internal')
        # if picking_inbounds:
        #     self._cr.execute(
        #         'select sum(product_qty) from stock_move where picking_id in %s and product_id = %s',
        #         [tuple(picking_inbounds.ids), self.product_id.id])
        #     results = self._cr.fetchall()
        #     if results:
        #         qty_receipted_target = results[0][0]

        #   Kiểm tra nếu không tạo dở dang
        count_outbound_done = len(self.picking_id.trp_transfer_request_id.picking_ids.filtered(
            lambda x: x.state in ('done') and x.location_id.usage == 'internal'))
        count_outbound = len(self.picking_id.trp_transfer_request_id.picking_ids.filtered(
            lambda x: x.state in ('confirmed', 'assigned', 'done') and x.location_id.usage == 'internal'))

        if count_outbound_done == count_outbound:
            qty_delivered_target = qty_delivered

        #   Cập nhật phiếu inbound
        if count_outbound_done == count_outbound and qty_delivered_target != qty_receipted_target:
            # Cập nhật lại phiếu nhập kho
            stock_pickings = self.picking_id.trp_transfer_request_id.picking_ids.filtered(lambda x: x.state in ('assigned', 'confirmed') and x.location_dest_id.usage == 'internal')
            if stock_pickings:
                stock_moves = stock_pickings[0].move_lines.filtered(lambda x: x.product_id == self.product_id)
                for item_move in stock_moves:
                    item_move.write({
                        'product_uom_qty': qty_delivered_target - qty_receipted,
                    })
                    # if qty_delivered_target - qty_receipted == 0:
                    #     item_move.unlink()
                    # else:
                    item_move._do_unreserve()
                    item_move._action_assign()