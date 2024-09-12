# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Excel, Word, Pdf Report Template",
    'category': 'Extra Tools',
    "summary": """Convert ods, odt report
    to xlsx, pdf, xls, docx, doc ... with Libreoffice""",
    "version": "1.0",
    "author": "Cybers Thang",
    "support": "ducthangict.dhtn@gmail.com",
    "license": "AGPL-3",
    "website": "https://odoosmes.com",
    "depends": [
        'base',
        'web'
    ],
    'data': [
        'views/report_view111.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'odoosmes_report/static/src/js/odoosmes_report.js',
        ],
    },

    'images': ['static/description/bg.png'],
    "installable": True,
    "application": True,
}
