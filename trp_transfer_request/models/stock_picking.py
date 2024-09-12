# -*- coding: utf-8 -*-

from odoo import fields, models, SUPERUSER_ID


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    trp_transfer_request_id = fields.Many2one('trp.transfer.request', string="Yêu cầu chuyển kho")

    def action_cancel(self):
        res = super(StockPicking, self).action_cancel()

        if self.trp_transfer_request_id:
            if len(self.trp_transfer_request_id.picking_ids.filtered(lambda x: x.state != 'cancel')) == 0:
                self.trp_transfer_request_id.action_cancel()
            # else:
            #     self.update_moves_quantity_inbound()

        return res

    def action_done(self):
        res = super(StockPicking, self).action_done()
        if self.trp_transfer_request_id:
            # Cập nhật trạng thái cho phiếu yêu cầu
            # if self.trp_transfer_request_id.state != "ongoing":
            #     self.trp_transfer_request_id.action_ongoing()

            # Cập nhật
            #       - Giá trị nhập/ xuất cho phiếu yêu cầu
            #       - Giá trị Demand của phiếu nhập dở dang
            # for line in self.move_lines:
            #     line.update_quantity_transfer_request_line()

            # if self.location_id.usage == 'internal':
            #     for line in self.move_lines:
            #         line.update_quantity_inbound()

            # Cập nhật trạng thái phiếu yêu cầu nếu tất cả các phiếu kho điều đã
            if len(self.with_user(SUPERUSER_ID).trp_transfer_request_id.picking_ids.filtered(lambda x: x.state not in ('done', 'cancel'))) == 0:
                self.trp_transfer_request_id.action_done()

        return res
