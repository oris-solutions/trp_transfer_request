# -*- coding: utf-8 -*-


from odoo import fields, models, api, SUPERUSER_ID
from datetime import datetime, timedelta, date
from odoo.exceptions import Warning


class TrpTransferRequest(models.Model):
    _name = 'trp.transfer.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Yêu cầu chuyển kho"
    _order = "id desc"

    name = fields.Char(string="Yêu cầu chuyển kho")
    trp_transfer_request_line_ids = fields.One2many('trp.transfer.request.line', 'trp_transfer_request_id', string="Chi tiết yêu cầu", copy=True)
    date_done = fields.Datetime(string="Ngày hoàn thành", copy=False)
    route_id = fields.Many2one('stock.location.route', string="Tuyến đường")
    warehouse_in_id = fields.Many2one('stock.warehouse', string="Kho nhập")
    address_in_id = fields.Many2one('res.partner', string="Địa chỉ nhập", related='warehouse_in_id.partner_id')
    address_in = fields.Char(string="Địa chỉ nhập đầy đủ")
    warehouse_out_id = fields.Many2one('stock.warehouse', string="Kho xuất", related='route_id.supplier_wh_id', store=True)
    address_out_id = fields.Many2one('res.partner', string="Địa chỉ xuất", related='warehouse_out_id.partner_id')
    address_out = fields.Char(string="Địa chỉ xuất đầy đủ")
    description = fields.Text(string="Diễn giải", help="Diễn giải")
    date_schedule_out = fields.Datetime(string="Ngày dự kiến xuất", copy=False)
    owner_id = fields.Many2one('res.partner', 'Người chịu trách nhiệm', required=True, default=lambda self: self.env.user.partner_id.id, states={'done': [('readonly', True)]}, check_company=True)
    state = fields.Selection([('draft', 'Nháp'), ('request', 'Xác nhận'), ('ongoing', 'Đang điều chuyển'), ('trouble', 'Sự cố'), ('done', 'Hoàn thành'), ('cancel', 'Hủy')], string="Trạng thái", default='draft')
    picking_ids = fields.One2many('stock.picking', 'trp_transfer_request_id', string="Phiếu kho", copy=False)
    picking_count = fields.Integer(copy=False, compute='_compute_picking_count')
    procurement_group_id = fields.Many2one('procurement.group', 'Nhóm Cung ứng', copy=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id)
    move_type = fields.Selection([('direct', 'Càng sơm càng tốt'), ('one', 'Khi tất cả đã sẵn sàng')],
                                 string='Chính sách giao hàng', default="direct")

    # carrier_id = fields.Many2one('delivery.carrier', string="Đơn vị vận chuyển")
    # carrier_tracking_ref = fields.Char(string="Mã vận đơn")
    # transporter_id = fields.Many2one('res.partner', string="Người vận chuyển")

    @api.model
    def create(self, vals):
        seq_date = None
        vals['name'] = self.env['ir.sequence'].next_by_code('trp.transfer.request', sequence_date=seq_date) or 'New'
        return super(TrpTransferRequest, self).create(vals)

    def get_default_date_in(self):
        return date.today() + timedelta(days=1)

    def get_default_date(self):
        return datetime.now()

    date_schedule_in = fields.Date(string="Ngày giao hàng", required=True, default=get_default_date_in)
    date = fields.Datetime(string="Ngày yêu cầu", default=get_default_date, copy=False)

    def get_day(self):
        return datetime.now().day

    def get_month(self):
        return datetime.now().month

    def get_year(selfs):
        return datetime.now().year

    @api.onchange('warehouse_in_id')
    def onchange_route_id(self):
        if self.warehouse_in_id.resupply_route_ids:
            self.route_id = self.warehouse_in_id.resupply_route_ids[0].id
        else:
            self.route_id = False

    def recompute_request_lines(self):
        self.ensure_one()
        inventory_location_id = self.route_id.rule_ids[0].location_src_id
        for line in self.trp_transfer_request_line_ids:
            line.write({
                'qty_in_warehouse': self.env['base.util'].get_product_available(line.product_id.id,inventory_location_id.id,lot_id=line.lot_id.id if line.lot_id else False)
            })
            if line.product_qty <= line.qty_in_warehouse or self.state != "draft":
                line.write({
                    'flag_product_available': 1,
                    'qty_in_warehouse': line.product_qty
                })
            else:
                line.write({
                    'flag_product_available': 2
                })

    def action_confirm(self):
        self.trp_transfer_request_line_ids._action_launch_stock_rule()
        # transger is created
        self.state = 'request'
        stock_picking_ids = self.env['stock.picking'].search([('origin', '=', self.name)])
        stock_picking_ids.write({
            'trp_transfer_request_id': self.id,
            'move_type': self.move_type
        })
        self.picking_count = len(stock_picking_ids)
        phieu_xuat = stock_picking_ids.filtered(lambda sp: sp.state == 'confirmed')
        lot_id_in = self.trp_transfer_request_line_ids.filtered(lambda sp: sp.lot_id)
        # gan lot vao phieu xuat
        if lot_id_in:
            for line in self.trp_transfer_request_line_ids:
                vals = ({
                    'product_id': line.product_id.id,
                    'location_id': self.route_id.rule_ids[0].location_src_id.id,
                    'location_dest_id': self.route_id.rule_ids[0].location_id.id,
                    'lot_id': line.lot_id.id or False,
                    'product_uom_id': line.product_uom.id,
                    'qty_done': line.product_qty,
                    'picking_id': phieu_xuat.id
                })

                self.env['stock.move.line'].create(vals)
        phieu_xuat.action_assign()

    def _compute_picking_count(self):
        for record in self:
            record.write({
                'picking_count': len(record.picking_ids or [])
            })

    def action_stock_picking(self):
        return {
            'name': "Yêu cầu chuyển kho",
            'view_mode': 'tree,form',
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
            'domain': ['|', ('id', 'in', tuple(self.picking_ids.ids)), ('origin', '=', self.name)],
            'context': {'create': 0}
        }

    def check_available(self):
        if not self.trp_transfer_request_line_ids:
            raise Warning("Không có sản phẩm nào ở tab thông tin chi tiết.")
        self.recompute_request_lines()

    def action_done(self):
        is_check_trouble = True
        rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self.trp_transfer_request_line_ids:
            if round(line.qty_delivered, rounding) != round(line.qty_receipted, rounding):
                is_check_trouble = False
                break

        if len(self.picking_ids) == len(self.picking_ids.filtered(lambda sp: sp.state in ('done', 'cancel'))):
            if is_check_trouble:
                self.write({
                    'state': 'done',
                    'date_done': self.picking_ids[0].date_done
                })
            else:
                self.action_trouble()
        else:
            raise Warning("Phải hoàn thành hoặc hủy các phiếu kho liên quan.")

    def action_cancel(self):
        # total_qty_delivered = sum(self.trp_transfer_request_line_ids.mapped('qty_delivered'))
        # total_qty_receipted = sum(self.trp_transfer_request_line_ids.mapped('qty_receipted'))
        picking_ids = self.with_user(SUPERUSER_ID).picking_ids
        if len(picking_ids.filtered(lambda sp: sp.state == 'done')) == 0:
            picking_ids = picking_ids.filtered(lambda sp: sp.state not in ('done', 'cancel'))
            picking_ids.write({'state': 'cancel'})
            self.write({'state': 'cancel'})
        else:
            raise Warning("Bạn không thể húy Yêu cầu chuyển kho. Vì đã có nhập/xuất liên quan.")

    def action_ongoing(self):
        self.write({'state': 'ongoing'})

    def action_trouble(self):
        self.write({'state': 'trouble'})

    def action_update_quantity_demand_inbound(self):
        for picking in self.picking_ids:
            # Cập nhật
            #       - Giá trị nhập/ xuất cho phiếu yêu cầu
            #       - Giá trị Demand của phiếu nhập dở dang
            for line in picking.move_lines:
                line.update_quantity_transfer_request_line()

            if picking.location_id.usage == 'internal':
                for line in picking.move_lines:
                    line.update_quantity_inbound()

            # # Cập nhật trạng thái phiếu yêu cầu nếu tất cả các phiếu kho điều đã
            # if len(self.trp_transfer_request_id.picking_ids.filtered(
            #         lambda x: x.state not in ('done', 'cancel'))) == 0:
            #     self.trp_transfer_request_id.action_done()

        is_check_trouble = True
        rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self.trp_transfer_request_line_ids:
            if round(line.qty_delivered, rounding) != round(line.qty_receipted, rounding):
                is_check_trouble = False
                break

        if len(self.picking_ids) == len(self.picking_ids.filtered(lambda sp: sp.state in ('done', 'cancel'))):
            if is_check_trouble:
                self.write({
                    'state': 'done',
                    'date_done': self.picking_ids[0].date_done
                })
            else:
                self.action_trouble()

    def action_update_quantity_in_out(self):
        res = self.env["trp.transfer.request"].search([('state', 'in', ('request', 'ongoing', 'done'))])
        for transfer in res:
            for item in transfer.picking_ids:
                item["move_type"] = "direct"

            transfer.action_update_quantity_demand_inbound()

    def action_update_states(self):
        res = self.env["trp.transfer.request"].search([('state', 'in', ('request', 'ongoing'))])

        for item in res:
            if len(item.picking_ids.filtered(lambda x: x.state != 'done')) != 0 and len(item.picking_ids.filtered(lambda x: x.state != 'done')) < len(item.picking_ids):
                item.write({'state': 'ongoing'})
            elif len(item.picking_ids.filtered(lambda x: x.state == 'done')) == len(item.picking_ids):
                item.write({'state': 'done'})
            elif len(item.picking_ids.filtered(lambda x: x.state == 'cancel')) == len(item.picking_ids):
                item.write({'state': 'cancel'})
            else:
                item.write({'state': 'request'})

    def unlink(self):
        if self.state != 'draft':
            raise Warning("Không thể xóa phiếu yêu cầu chuyển kho này khi nó khác dự thảo")
        return super(TrpTransferRequest, self).unlink()
