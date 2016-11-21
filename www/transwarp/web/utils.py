#!/usr/bin/env python
# -*- coding:utf8 -*-

#__author__ == 'godlikeme'
import datetime
from const import _RE_TZ, _TIMEDELTA_ZERO


def load_module(module_name):
    """

    >>> m=load_module('xml')
    >>> m.__name__
    'xml'
    >>> m=load_module('transwarp.web.application')
    >>> m.__name__
    'application'

    """

    last_dot = module_name.rfind(".")
    if last_dot == -1:
        return __import__(module_name, globals(), locals())

    from_module = module_name[:last_dot]
    import_module = module_name[last_dot+1:]
    m = __import__(import_module, globals(), locals(), [from_module])
    return m


def to_unicode(value):
    if isinstance(value, list):
        return [item.decode("utf-8") for item in value]
    if isinstance(value, basestring):
        return value.decode("utf-8")

    raise Exception("type : %s cannot change to unicode" % type(value))


def unquote(v):
    # TODO
    return v


def to_str(v):
    if isinstance(v, unicode):
        return v.encode("utf-8")

    return v

def quote(v):
    #TODO
    return v


class UTC(datetime.tzinfo):
    def __init__(self, utc):
        utc = str(utc.strip().upper())
        mt = _RE_TZ.match(utc)
        if mt:
            minus = mt.group(1) == '-'
            h = int(mt.group(2))
            m = int(mt.group(3))
            if minus:
                h, m = (-h), (-m)
            self._utcoffset = datetime.timedelta(hours=h, minutes=m)
            self._tzname = 'UTC%s' % utc
        else:
            raise ValueError('bad utc time zone')

    def utcoffset(self, dt):
        """
        表示与标准时区的 偏移量
        """
        return self._utcoffset

    def dst(self, dt):
        """
        Daylight Saving Time 夏令时
        """
        return _TIMEDELTA_ZERO

    def tzname(self, dt):
        """
        所在时区的名字
        """
        return self._tzname

    def __str__(self):
        return 'UTC timezone info object (%s)' % self._tzname

    __repr__ = __str__


if __name__ == '__main__':
    s = load_module("transwarp.web.application")
    print s.__name__