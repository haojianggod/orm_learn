#!/usr/bin/env python
# -*- coding:utf8 -*-

#__author__ == 'godlikeme'

class BaseORMException(Exception):
    pass

class GenSqlException(BaseORMException):
    pass

class PrimaryKeyException(BaseORMException):
    pass

