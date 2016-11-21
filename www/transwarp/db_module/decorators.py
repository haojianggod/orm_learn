#!/usr/bin/env python
# -*- coding:utf8 -*-

#__author__ == 'godlikeme'

from functools import wraps
from transwarp.db_module.db import connection, transaction, create_engine

create_engine('root', '123456','test','127.0.0.1',3306)


def with_connection(func):
    @wraps(func)
    def _wrapper(*args, **kwargs):
        with connection():
            return func(*args, **kwargs)

    return _wrapper


def with_transaction(func):
    @wraps(func)
    def _wrapper(*args, **kwargs):
        with transaction():
            return func(*args, **kwargs)

    return _wrapper


@with_connection
def hello():
    print "hello"

if __name__ == '__main__':

    hello()

