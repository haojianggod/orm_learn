#!/usr/bin/env python
# -*- coding:utf8 -*-

#__author__ == 'godlikeme'
from decorators import with_connection
from mylogging.factory import logger1
from transwarp.db_module.db import Dict, _db_ctx
from transwarp.db_module.db_exceptions import MultiColumnsError


@with_connection
def _select(sql, first, *args):
    """

    执行SQL， 返回结果 或者多个结果组成的列表
    """
    global _db_ctx
    sql = sql.replace('?', "%s")
    logger1.info('SQL: %s, ARGS: %s' % (sql, args))
    try:
        cursor = _db_ctx.connection.cursor()
        cursor.execute(sql, args)
        if cursor.description:
            names = [x[0] for x in cursor.description]
        if first:
            values = cursor.fetchone()
            if not values:
                return None

            return Dict(names, values)

        return [Dict(names, x) for x in cursor.fetchall()]

    except:
        raise


def select_one(sql, *args):
    """
    执行SQL 仅返回一个结果
    如果没有结果 返回None
    如果有1个结果，返回一个结果
    如果有多个结果，返回第一个结果

    """
    _select(sql, True, *args)


def select_int(sql, *args):
    """
    执行一个sql 返回一个数值，
    注意仅一个数值，如果返回多个数值将触发异常

    """
    d = _select(sql, True, *args)
    if len(d) != 1:
        raise MultiColumnsError("Expect only one colume.")
    return d.values()[0]


def select(sql, *args):
    """
    执行sql 以列表形式返回结果
    """
    return _select(sql, False, *args)


@with_connection
def _update(sql, *args):
    """
    执行update 语句，返回update的行数

    """
    global _db_ctx
    sql = sql.replace('?', '%s')
    logger1.info('SQL: %s, ARGS: %s' % (sql, args))
    try:
        cursor = _db_ctx.connection.cursor()
        cursor.execute(sql, args)
        r = cursor.rowcount
        return r
    except:
        raise

def update(sql, *args):
    """
    执行update 语句，返回update的行数
    >>> u1 = dict(id=1000, name='Michael', email='michael@test.org', passwd='123456', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> u2 = select_one('select * from user where id=?', 1000)
    >>> u2.email
    u'michael@test.org'
    >>> u2.passwd
    u'123456'
    >>> update('update user set email=?, passwd=? where id=?', 'michael@example.org', '654321', 1000)
    1
    >>> u3 = select_one('select * from user where id=?', 1000)
    >>> u3.email
    u'michael@example.org'
    >>> u3.passwd
    u'654321'
    >>> update('update user set passwd=? where id=?', '***', '123')
    0
    """
    return _update(sql, *args)


def insert(table, **kwargs):
    """
    执行insert语句
    >>> u1 = dict(id=2000, name='Bob', email='bob@test.org', passwd='bobobob', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> u2 = select_one('select * from user where id=?', 2000)
    >>> u2.name
    u'Bob'
    >>> insert('user', **u2)
    Traceback (most recent call last):
     ...
    IntegrityError: 1062 (23000): Duplicate entry '2000' for key 'PRIMARY'
    """

    cols, args = zip(*kwargs.iteritems())
    sql = 'insert into `%s` (%s) values (%s)' % (table,
                                                 ','.join(['`%s`' % col for col in cols]),
                                                 ','.join(['?' for i in range(len(args))])
                                                 )

    return _update(sql, *args)



