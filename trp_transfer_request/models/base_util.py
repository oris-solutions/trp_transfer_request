# -*- coding: utf-8 -*-

from odoo import models, fields as F, api, _
from datetime import datetime
import pytz
import logging
_logger = logging.getLogger(__name__)
import odoo.tools as tools
from odoo import SUPERUSER_ID
from urllib.parse import urljoin
from urllib.parse import urlencode
from dateutil.relativedelta import relativedelta


class BaseUtil(models.Model):
    _name = 'base.util'
    _auto = False

    def create_record(self, vals=None, table_name=None, target_self=None, new_cr=None):

        tocreate = {
            parent_model: {'id': vals.pop(parent_field, None)}
            for parent_model, parent_field in self._inherits.items()
        }
        tocreate_m2m = {}


        updates = [
            ('id', "nextval('%s')" % target_self._sequence),
        ]

        protected_fields = []
        upd_todo = []
        unknown_fields = []
        for name, val in list(vals.items()):
            field = target_self._fields.get(name)
            if not field:
                unknown_fields.append(name)
                del vals[name]
            elif field.inherited:
                tocreate[field.related_field.model_name][name] = val
                del vals[name]
            elif not field.store:
                del vals[name]
            elif field.inverse:
                protected_fields.append(field)
            elif field.type == 'many2many':
                tocreate_m2m.update({name: {'val': val, 'table': field._column_rel, 'column1': field.column1,
                                            'column2': field.column2}})
                del vals[name]
        if unknown_fields:
            _logger.warning('No such field(s) in model %s: %s.', target_self._name, ', '.join(unknown_fields))

        # create or update parent records
        for parent_model, parent_vals in tocreate.items():
            parent_id = parent_vals.pop('id')
            if not parent_id:
                parent_id = self.env[parent_model].create(parent_vals).id
            else:
                self.env[parent_model].browse(parent_id).write(parent_vals)
            vals[self._inherits[parent_model]] = parent_id

        # set boolean fields to False by default (to make search more powerful)
        for name, field in self._fields.items():
            if field.type == 'boolean' and field.store and name not in vals:
                vals[name] = False

        # determine SQL values
        self = self.browse()
        for name, val in vals.items():
            field = target_self._fields[name]
            if field.store and field.type:
                column_val = field.convert_to_column(val, target_self, vals)
                updates.append((name, '%s', column_val))
            else:
                upd_todo.append(name)

            if hasattr(field, 'selection') and val:
                target_self._check_selection_field_value(name, val)

        if self._log_access:
            updates.append(('create_uid', '%s', self._uid))
            updates.append(('write_uid', '%s', self._uid))
            updates.append(('create_date', "(now() at time zone 'UTC')"))
            updates.append(('write_date', "(now() at time zone 'UTC')"))

        # insert a row for this record
        cr = self._cr if not new_cr else new_cr
        query = """INSERT INTO "%s" (%s) VALUES(%s) RETURNING id""" % (
            table_name,
            ', '.join('"%s"' % u[0] for u in updates),
            ', '.join(u[1] for u in updates),
        )
        cr.execute(query, tuple(u[2] for u in updates if len(u) > 2))

        # from now on, self is the new record
        id_new, = cr.fetchone()
        # Insert many2many field
        for key in tocreate_m2m.keys():

            if len(tocreate_m2m[key].get('val')) > 0:
                if tocreate_m2m[key].get('val')[0][0] == 6 and len(tocreate_m2m[key].get('val')[0][2]) > 0:
                    values = ''
                    for value in tocreate_m2m[key].get('val')[0][2]:
                        values += '(%s, %s),' % (id_new, value)
                    values = values.strip(',')
                    sql = """INSERT INTO "%s" (%s,%s) VALUES %s""" % (tocreate_m2m[key].get('table'),
                                                                       tocreate_m2m[key].get('column1'),
                                                                       tocreate_m2m[key].get('column2'),
                                                                       values)
                    self.env.cr.execute(sql)
                elif tocreate_m2m[key].get('val')[0][0] == 4:
                    values = ''
                    for value in tocreate_m2m[key].get('val'):
                        values += '(%s, %s),' % (id_new, value[1])
                    values = values.strip(',')
                    sql = """INSERT INTO "%s" (%s,%s) VALUES %s""" % (tocreate_m2m[key].get('table'),
                                                                       tocreate_m2m[key].get('column1'),
                                                                       tocreate_m2m[key].get('column2'),
                                                                       values)
                    if not new_cr:
                        self.env.cr.execute(sql)
                    else:
                        new_cr.execute(sql)
        return id_new

    def convert_datetime_tz(self, dt, str=True):
        """
            Returns the datetime as seen in the client's timezone.
           ex:  datetime = '2017-02-09 06:00:00'
                datetime_tz = '2017-02-09 13:00:00'
        """
        if not dt:
            return dt
        if type(dt) != type('') and type(dt) != type(u""):
            dt = dt
        else:
            dt = F.Datetime.from_string(dt)
        if self.env.context and self.env.context.get('tz'):
            tz_name = self.env.context['tz']
        else:
            tz_name = self.pool.get('res.users').read(self.env.cr, self.env.uid, SUPERUSER_ID, ['tz'])['tz']
        if not tz_name:
            tz_name = 'Asia/Ho_Chi_Minh'
        if tz_name:
            try:
                utc = pytz.timezone('UTC')
                context_tz = pytz.timezone(tz_name)
                utc_datetime = utc.localize(dt, is_dst=False)  # UTC = no DST
                datetime_tz = utc_datetime.astimezone(context_tz)
            except Exception:
                _logger.debug("Failed to compute context/client-specific today date, "
                              "using the UTC value for `today`",
                              exc_info=True)
        if str:
            return F.Datetime.to_string(datetime_tz)
        else:
            return datetime_tz

    def date_to_datetime_utc(self, date, str=True):
        """
            Convert date to datetime UTC:
             ex: date = '2017-02-09'
             datetime = '2017-02-09 00:00:00'
             datetime_utc = '2017-02-09 05:00:00'
        """

        if type(date) == type('') or type(date) == type(u""):
            date = datetime.strptime(date, tools.DEFAULT_SERVER_DATE_FORMAT)
            # date = F.Date.from_string(date)
        if self.env.context and self.env.context.get('tz'):
            tz_name = self.env.context['tz']
        else:
            tz_name = self.env['res.users'].read(self.env.uid, ['tz'])['tz']
        if tz_name:
            utc = pytz.timezone('UTC')
            context_tz = pytz.timezone(tz_name)
            user_datetime = date
            local_timestamp = context_tz.localize(user_datetime, is_dst=False)
            user_datetime = local_timestamp.astimezone(utc)
        if str:
            return F.Datetime.to_string(user_datetime)
        else:
            return user_datetime

    def datetime_to_datetime_utc(self, str_datetime, str=True):
        """
            Convert date to datetime UTC:
             ex: date = '2017-02-09'
             datetime = '2017-02-09 00:00:00'
             datetime_utc = '2017-02-09 05:00:00'
        """

        if type(str_datetime) == type('') or type(str_datetime) == type(u""):
            str_datetime = datetime.strptime(str_datetime, tools.DEFAULT_SERVER_DATETIME_FORMAT)

        if self.env.context and self.env.context.get('tz'):
            tz_name = self.env.context['tz']
        else:
            tz_name = self.env['res.users'].read(self.env.uid, ['tz'])['tz']
        if tz_name:
            utc = pytz.timezone('UTC')
            context_tz = pytz.timezone(tz_name)
            user_datetime = str_datetime
            local_timestamp = context_tz.localize(user_datetime, is_dst=False)
            user_datetime = local_timestamp.astimezone(utc)
        if str:
            return F.Datetime.to_string(user_datetime)
        else:
            return user_datetime

    def get_access_link(self, for_view_action, context=None):
        """
        paramaters:
            1. for_view_action :  self.get_formview_action(cr, uid, id, context)
        Output:
        Link with structure:
        hostname/web?db=database#id= &model= &view_type=
        """
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        query = {'db': self.env.cr.dbname}
        fragment = {}
        fragment.update(id=for_view_action.get('res_id'), view_type=for_view_action.get('view_type'),
                        model=for_view_action.get('res_model'))
        ctx = for_view_action.get('context',False)
        with_context = self.env.context.copy()
        if ctx and with_context.get('no_params', False) == False:
            params = ctx.get('params', False)
            if params and params.get('action', False):
                fragment.update(action=params.get('action', False))
        url = urljoin(base_url, "/web?%s#%s" % (urlencode(query), urlencode(fragment)))
        return url

    def get_product_available(self, product_id, location_id, lot_id=False):
        qr = """
            SELECT SUM(quantity) FROM stock_quant WHERE location_id = %(location_id)s
               AND product_id = %(product_id)s
        """ % {'location_id': location_id, 'product_id': product_id if product_id else 0}
        # if lot_id:
        #     if not isinstance(lot_id, list):
        #         qr += ' AND lot_id = %s' % lot_id
        #     else:
        #         if len(lot_id) > 0:
        #             qr += ' AND lot_id in (%s)' % str(lot_id).strip('[]')
        self.env.cr.execute(qr)
        data = self.env.cr.fetchone()
        if data and len(data) >0 and data[0]:
            return data[0]
        return 0

    def date_now_timezone(self, str=True):
        """
            default odoo get date now utc, we must convert to date timezone
        """
        if str:
            return F.Date.context_today(self)
        else:
            return self.str_to_date(F.Date.context_today(self))

    def str_to_date(self, date):
        """
            convert string to date
        :param str_date:
        :return:
        """
        try:
            return F.Date.from_string(date)
        except:
            return date

    def date_to_str(self, date):
        """
            convert date to str
        :param date_val:
        :return:
        """
        try:
            return F.Date.to_string(date)
        except:
            return date

    def date_after_next_month(self, date, month=1):
        """
        Return date after next month
        Eg: date after 2 month from 15/01/2013 is: 15/03/2013
        """
        return self.str_to_date(date) + relativedelta(months=+month)

    def last_date_of_month(self, date, str=False):
        """Return the last date of month.
        Args:
            date (string or datetime.date): date contains month we want to get last date

        Returns:
            datetime.date: last date of the month

        Examples:
            >>> last_date_of_month('2015-03-25')
            >>> datetime.date(2015, 3, 31)
        """
        last_date = self.str_to_date(date) + relativedelta(day=1, months=+1, days=-1)
        if str:
            return self.date_to_str(last_date)
        return last_date

    def convert_datetime_tz_v1(self, dt, user_rcs, str=True):
        """
            Returns the datetime as seen in the client's timezone.
           ex:  datetime = '2017-02-09 06:00:00'
                datetime_tz = '2017-02-09 13:00:00'
        """
        if not dt:
            return dt
        if type(dt) != type('') and type(dt) != type(u""):
            dt = dt
        else:
            dt = F.Datetime.from_string(dt)
        if self.env.context and self.env.context.get('tz'):
            tz_name = self.env.context['tz']
        else:
            tz_name = user_rcs.tz
        if not tz_name:
            tz_name = 'Asia/Ho_Chi_Minh'
        if tz_name:
            try:
                utc = pytz.timezone('UTC')
                context_tz = pytz.timezone(tz_name)
                utc = dt.replace(tzinfo=utc)
                datetime_tz = utc.astimezone(context_tz)
            except Exception:
                _logger.debug("Failed to compute context/client-specific today date, "
                              "using the UTC value for `today`",
                              exc_info=True)
        if str:
            return F.Datetime.to_string(datetime_tz)
        else:
            return datetime_tz

    def date_to_datetime_utc_v1(self, date, user_rcs, str=True):
        """
            Convert date to datetime UTC:
             ex: date = '2017-02-09'
             datetime = '2017-02-09 00:00:00'
             datetime_utc = '2017-02-08 17:00:00'
        """

        if type(date) == type('') or type(date) == type(u""):
            date = datetime.strptime(date, tools.DEFAULT_SERVER_DATE_FORMAT)
            # date = F.Date.from_string(date)
        if self.env.context and self.env.context.get('tz'):
            tz_name = self.env.context['tz']
        else:
            tz_name = user_rcs.tz
        if not tz_name:
            tz_name = 'Asia/Ho_Chi_Minh'
        if tz_name:
            utc = pytz.timezone('UTC')
            context_tz = pytz.timezone(tz_name)
            user_datetime = date
            local_timestamp = context_tz.localize(user_datetime, is_dst=False)
            user_datetime = local_timestamp.astimezone(utc)
        if str:
            return F.Datetime.to_string(user_datetime)
        else:
            return user_datetime

    def datetime_to_datetime_utc_v1(self, str_datetime, user_rcs, str=True):
        """
            Convert date to datetime UTC:
             ex: date = '2017-02-09'
             datetime = '2017-02-09 00:00:00'
             datetime_utc = '2017-02-08 17:00:00'
        """

        if type(str_datetime) == type('') or type(str_datetime) == type(u""):
            str_datetime = datetime.strptime(str_datetime, tools.DEFAULT_SERVER_DATETIME_FORMAT)
            # date = F.Date.from_string(date)
        if self.env.context and self.env.context.get('tz'):
            tz_name = self.env.context['tz']
        else:
            tz_name = user_rcs.tz
        if not tz_name:
            tz_name = 'Asia/Ho_Chi_Minh'
        if tz_name:
            utc = pytz.timezone('UTC')
            context_tz = pytz.timezone(tz_name)
            user_datetime = str_datetime
            local_timestamp = context_tz.localize(user_datetime, is_dst=False)
            user_datetime = local_timestamp.astimezone(utc)
        if str:
            return F.Datetime.to_string(user_datetime)
        else:
            return user_datetime
