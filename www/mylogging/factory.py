#!/usr/bin/env python
# -*- coding:utf8 -*-

#__author__ == 'godlikeme'
import logging
import logging.config
import os


dir = os.path.dirname(__file__)
conf_path = os.path.join(dir, "logger.conf")
logging.config.fileConfig(conf_path)

logger1 = logging.getLogger("example01")
logger2 = logging.getLogger("example02")