#!/usr/bin/env python
# -*- coding:utf8 -*-

#__author__ == 'godlikeme'
from transwarp.orm.base import *
from transwarp.db_module.db import transaction
import uuid


class A(object):
    pass


class B(A):
    def __new__(cls, name, bases, attrs):
        return A.__new__(name, bases, attrs)


class User(Model):
    name = StringField()
    age = IntegerField()
    sex = StringField()
    _id = StringField(primary_key=True)


if __name__ == '__main__':
    with transaction():
        for i in range(100):
           s = User()
           s.name = "jianghao"
           s.age = 18
           s.sex = "Man"
           s._id = str(uuid.uuid1())
           s.insert()

