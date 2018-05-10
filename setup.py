#!/usr/bin/env python
# encoding=utf-8
from __future__ import print_function
import os
import sys

try:
    from setuptools import setup
except ImportError:
    print("This package requires 'setuptools' to be installed.")
    sys.exit(1)

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()

setup(name='slipsomat',
      version='0.2.1',  # Use bumpversion to update
      description='Sync Alma slips & letters',
      long_description=README,
      classifiers=[
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
      ],
      keywords='alma browser-automation',
      author='Dan Michael O. Heggø',
      author_email='d.m.heggo@ub.uio.no',
      url='https://github.com/scriptotek/alma-slipsomat',
      license='MIT',
      install_requires=[
          'selenium',
          'colorama',
          'python-dateutil'
      ],
      extras_require={
          'inquirer': ['inquirer'],
      },
      entry_points={
          'console_scripts': ['slipsomat=slipsomat.shell:main']
      },
      packages=['slipsomat']
      )
