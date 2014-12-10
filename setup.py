#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()

readme = open('README.rst').read()
history = open('HISTORY.rst').read().replace('.. :changelog:', '')

setup(
    name='postage',
    version='1.1.0',
    description='A Python library for AMQP-based network components',
    long_description=readme + '\n\n' + history,
    author='Leonardo Giordani',
    author_email='giordani.leonardo@gmail.com',
    url='https://github.com/lgiordani/postage',
    packages=[
        'postage',
    ],
    package_dir={'postage': 'postage'},
    include_package_data=True,
    install_requires=[
    ],
    license="GPL v2.0 or newer",
    zip_safe=False,
    keywords='postage',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'License :: OSI Approved :: Mozilla Public License 1.1 (MPL 1.1)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Networking ',
    ],
    test_suite='tests',
)
