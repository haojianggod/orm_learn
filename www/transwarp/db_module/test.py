#!/usr/bin/env python
# -*- coding:utf8 -*-

#__author__ == 'godlikeme'

from functools import wraps

def wrap3(func):
    @wraps(func)
    def call_it(*args, **kwargs):
        """wrap func: call_it2"""
        print 'before call'
        return func(*args, **kwargs)
    return call_it

@wrap3
def hello3():
    """test hello 3"""
    print 'hello world3'


def test_create_engine():
    from transwarp.db_module.db import create_engine,engine
    create_engine('root', '123456','test','127.0.0.1',3306)
    print engine



if __name__ == '__main__':
    test_create_engine()