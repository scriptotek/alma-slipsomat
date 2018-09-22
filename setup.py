#!/usr/bin/env python
# encoding=utf-8
from __future__ import print_function
from os import path
import sys

try:
    from setuptools import setup
except ImportError:
    print("This package requires 'setuptools' to be installed.")
    sys.exit(1)

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md')) as fp:
    long_description = fp.read()

setup(name='slipsomat',
      version='0.2.6',  # Use bumpversion to update
      description='Sync Alma slips & letters',
      long_description=long_description,
      long_description_content_type='text/markdown',
      classifiers=[
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.7',
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
          'python-dateutil',
          'PyInquirer',
      ],
      entry_points={
          'console_scripts': ['slipsomat=slipsomat.shell:main']
      },
      packages=['slipsomat']
      )
