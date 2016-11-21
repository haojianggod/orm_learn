#!/usr/bin/env python
# -*- coding:utf8 -*-

#__author__ == 'godlikeme'
import threading

from mylogging.factory import logger1 as logging
from transwarp.db_module.db_exceptions import DBError


class _Engine(object):
    def __init__(self, connect):
        self._connect = connect

    def connect(self):
        return self._connect()

engine = None


class Dict(dict):
    """
    字典对象
    实现一个简单的可以通过属性访问的字典，比如 x.key = value
    """
    def __init__(self, names=(), values=(), **kwargs):
        super(Dict, self).__init__(**kwargs)
        for k, v in zip(names, values):
            self[k] = v

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(r" <%s> object has no attribute '%s'" % (self.__class__.__name__, item))

    def __setattr__(self, key, value):
        self[key] = value


def create_engine(user, password, database, host='127.0.0.1', port=3306, autocommit=False, **kw):
    """

    db模块核心，用于数据库链接，生成全局对象engine
    engine 持有数据库链接
    """
    import MySQLdb

    global engine
    if engine is not None:
        raise DBError("Engine is already initialized")
    params = dict(user=user, passwd=password, db=database, host=host, port=port)
    defaults = dict(use_unicode=True, charset='utf8', autocommit=autocommit)
    for k, v in defaults.iteritems():
        params[k] = kw.pop(k,v)

    params.update(kw)
    # params['buffered'] = True
    engine = _Engine(lambda: MySQLdb.connect(**params))
    print engine

    logging.info("[ + ] init engine <%s> ok." % hex(id(engine)))


class _DbCtx(threading.local):
    def __init__(self):
        self.connection = None
        self.transactions = 0

    def is_init(self):
        return not self.connection is None

    def init(self):
        self.connection = _LasyConnection()
        self.transactions = 0

    def cleanup(self):
        self.connection.cleanup()
        self.connection = None

    def cursor(self):
        return self.connection.cursor()

_db_ctx = _DbCtx()


class _LasyConnection(object):
    """
        惰性连接对象
        仅当需要cursor对象时，才连接数据库，获取连接
    """
    def __init__(self):
        self.connection = None

    def cursor(self):
        if self.connection is None:
            self.connection = engine.connect()
            logging.info('[CONNECTION] [OPEN] connection <%s>...' % hex(id(self.connection)))

        return self.connection.cursor()

    def commit(self):
        if self.connection:
            self.connection.commit()

    def rollback(self):
        if self.connection:
            self.connection.rollback()

    def cleanup(self):
        if self.connection:
            _connection = self.connection
            self.connection = None
            logging.info('[CONNECTION] [CLOSE] connection <%s>...' % hex(id(_connection)))
            _connection.close()


class _ConnectionCtx(object):
    """
        因为_DbCtx实现了连接的 获取和释放，但是并没有实现连接
        的自动获取和释放，_ConnectCtx在 _DbCtx基础上实现了该功能，
        因此可以对 _ConnectCtx 使用with 语法，比如：
        with connection():
            pass
            with connection():
                pass
    """
    def __enter__(self):
        global _db_ctx
        self.should_cleanup = False
        if not _db_ctx.is_init():
            _db_ctx.init()
            self.should_cleanup = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _db_ctx

        if self.should_cleanup:
            _db_ctx.cleanup()
            self.should_cleanup = False


class _TransactionCtx(object):
    """
    事务嵌套，每加一层嵌套就计数 +1, 离开一层就计数 -1, 最后为0才提交
    """
    def __enter__(self):
        global _db_ctx
        self.should_close_conn = False
        if not _db_ctx.is_init():
            _db_ctx.init()
            self.should_close_conn = True

        _db_ctx.transactions += 1
        logging.info("[Transaction] begin transaction.." if _db_ctx.transactions == 1 else 'join current transaction...')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _db_ctx
        _db_ctx.transactions -= 1
        try:
            if _db_ctx.transactions == 0:
                if exc_type is None:
                    self.commit()
                else:
                    self.rollback()
        finally:
            if self.should_close_conn:
                _db_ctx.cleanup()
                self.should_close_conn = False

    def commit(self):
        global _db_ctx
        logging.info("[ + ] commit transaction...")
        try:
            _db_ctx.connection.commit()
            logging.info("[ + ] transaction ok")
        except:
            logging.warn("[ - ] commit failed, try rollback...")
            _db_ctx.connection.rollback()
            raise

    def rollback(self):
        global _db_ctx
        logging.warn('[ + ] rollback transaction...')
        _db_ctx.connection.rollback()
        logging.info('[ + ] rollback ok.')


def connection():
    return _ConnectionCtx()

def transaction():
    return _TransactionCtx()
