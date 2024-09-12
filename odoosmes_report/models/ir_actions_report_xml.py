# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _

class ir_actions_report(models.Model):
    _inherit = 'ir.actions.report'

    report_type = fields.Selection([
        ('qweb-html', 'HTML'),
        ('qweb-pdf', 'PDF'),
        ('qweb-text', 'Text'), ('controller', 'Controller')
    ], required=True, default='qweb-pdf',
        help='The type of the report that will be rendered, each one having its own'
             ' rendering method. HTML means the report will be opened directly in your'
             ' browser PDF means the report will be rendered using Wkhtmltopdf and'
             ' downloaded by the user.')

    template_id = fields.Many2one("ir.attachment", "Template *.odt, *.ods")
    output_file = fields.Selection(
        selection=[
        ('xlsx','xlsx'),
        ('xls','xls'),
        ('docx','docx'),
        ('doc','doc'),
        ('pdf','pdf'),
        ('odt','odt'),
        ('ods','ods')
        ],
        string="Output Format")
    module = fields.Char(
        "Module",
        help="The implementer module that provides this report")
    odoosmes_template_fallback = fields.Char(
        "Fallback",
        size=128,
        help=(
            "If the user does not provide a template this will be used "
            "it should be a relative path to root of YOUR module "
            "or an absolute path on your server."
        ))
    modules_name = fields.Char(
        string='Tên Module',
    )
    rp_path = fields.Char(
        string='Tên Files Report',
    )
    ma = fields.Char(string="Mã")
    @api.onchange('print_report_name')
    def onchange_report_name(self):
        if self.report_name:
            self.ma = "/report/odoosmes.com/" + self.print_report_name
