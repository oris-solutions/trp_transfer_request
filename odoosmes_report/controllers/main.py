# -*- encoding: utf-8 -*-
from odoo import http
import odoo
from odoo.http import request
from odoo.addons.web.controllers.main import serialize_exception, content_disposition
import werkzeug.utils

from base64 import b64decode, b64encode
import tempfile

from io import BytesIO 
import zipfile
from jinja2  import Template

from subprocess import Popen, PIPE
from odoo.tools.misc import find_in_path

import subprocess
import pkg_resources
import logging
import json
from odoo.addons.web.controllers import main
_logger = logging.getLogger(__name__)

import sys


MIME_DICT = {
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "pdf": "application/pdf",
    "doc": "application/msword",
    "rtf": "application/rtf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx" : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls" : "application/excel",
    "zip": "application/zip",
    "xml" : "text/xml",
}

def compile_file(cmd):
    try:
        compiler = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    except Exception:
        msg = "Could not execute command %r" % cmd[0]
        _logger.error(msg)
        return ''
    result = compiler.communicate()
    if compiler.returncode:
        error = result
        _logger.warning(error)
        return ''
    return result[0]

def get_command(format_out, file_convert):
    try:
        unoconv = find_in_path('unoconv')
    except IOError:
        unoconv = 'unoconv'
    return [unoconv,  "--stdout", "-f", "%s" % format_out, "%s" % file_convert]

def make_response(mimetype, content, file_name, out_format_file):
    headers = [
        ('Content-Type', mimetype),
        ('Content-Length', len(content)),
        ('Content-Disposition', content_disposition("%s.%s" % (file_name,out_format_file)))
    ]
    return request.make_response(content, headers=headers)

class ReportController(main.ReportController):

    @http.route(['/report/download'], type='http', auth="user")
    def report_download(self, data, token):
        print ("A" * 100)
        res = super(ReportController, self).report_download(data, token)

        requestcontent = json.loads(data)
        print(requestcontent)
        url, type = requestcontent[0], requestcontent[1]
        print(self, self)
        if type == 'controller':
            from werkzeug.test import Client
            from werkzeug.datastructures import Headers
            from werkzeug.wrappers import BaseResponse
            reqheaders = Headers(request.httprequest.headers)
            response = Client(request.httprequest.app, BaseResponse).get(url, headers=reqheaders, follow_redirects=True)
            response.set_cookie('fileToken', token)
            return response
        else:
            return res

    @http.route('/report/odoosmes.com/<reportname>/<docids>', type='http', auth="user")
    @serialize_exception
    def download_document(self, **kw):
        context = request.context
        docids = [int(i) for i in kw.get("docids").split(',')]
        t_report_name = kw.get("reportname")

        report = request.env['ir.actions.report'];
        conditions = [
            ('report_type', 'in', ['controller']),
            ('print_report_name', '=', t_report_name)]

        report_ids = report.search(conditions, limit=1)
        
        assert report_ids, 'Not found report name ' + t_report_name
        
        report_obj = request.env[report_ids.model]
        output_file = report_ids.output_file
        report_name = report_ids.name

        docs = report_obj.search([('id','in',docids)])
        if report_ids.template_id:
            in_stream = BytesIO(b64decode(report_ids.template_id.datas))
        else:
            in_stream = pkg_resources.resource_filename(
                'odoo.addons.%s'% report_ids.modules_name,report_ids.rp_path
            )
        temp = tempfile.NamedTemporaryFile()

        if len(docids) == 1:
            data = dict(o=docs, company=request.env.company)
            if hasattr(report_obj, 'custom_report'):
                data.update({"data": docs.custom_report()})
            t = Template(in_stream, temp, ignore_undefined_variables=True,
                escape_false=True)
            t.render(data)
            temp.seek(0)
            default_out_odt = temp.read()
            if not output_file:
                temp.close()
                return make_response(MIME_DICT["odt"], default_out_odt, report_name, "odt")
            out = compile_file(get_command(output_file, temp.name))
            temp.close()
            if not out:
                return make_response(MIME_DICT["odt"], default_out_odt, report_name, "odt")
            return make_response(MIME_DICT[output_file], out, report_name, output_file)
        # if more than one zip returns
        else:
            buff = StringIO()
            zip_archive = zipfile.ZipFile(buff, mode='w')

            for doc in docs:
                data = dict(o=doc)
                if hasattr(report_obj, 'custom_report'):
                    data.update({"data": doc.custom_report()})

                t = Template(in_stream, temp, escape_false=True)
                t.render(data)
                temp.seek(0)
                default_out_odt = temp.read()
                if not output_file:
                    zip_archive.writestr("%s_%s.odt" % (report_name, doc.id), default_out_odt)
                else:
                    out = compile_file(get_command(output_file, temp.name))
                    if not out:
                        zip_archive.writestr("%s_%s.odt" % (report_name, doc.id), default_out_odt)
                    else:
                        zip_archive.writestr("%s_%s.%s" % (report_name, doc.id, output_file), out)
            temp.close()
            zip_archive.close()
            return make_response(MIME_DICT["zip"], buff.getvalue(), report_name, "zip")


