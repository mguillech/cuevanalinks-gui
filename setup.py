#!/usr/bin/env python
# -*- coding: utf-8 -*-
try:
    from setuptools import setup
except ImportError:
    import distribute_setup
    distribute_setup.use_setuptools()
    from setuptools import setup

import os
import sys
try:
    import py2exe
    PY2EXE_ACTIVE = 1
except:
    #no windows platform
    PY2EXE_ACTIVE = 0

from cuevanalinks import __version__

if sys.version_info < (2, 6):
    print('ERROR: cuevanalinks requires at least Python 2.6 to run.')
    sys.exit(1)

def find_file_in_path(filename):
    """help function to include  data files"""
    for include_path in sys.path:
        file_path = os.path.join(include_path, filename)
        if os.path.exists(file_path):
            return file_path

long_description = open('README.rst').read()

dll_excludes = ['libgdk-win32-2.0-0.dll', 'libgobject-2.0-0.dll', 'tcl84.dll',
                'tk84.dll']
excludes = ['_gtkagg', '_tkagg', 'bsddb', 'curses', 'email', 'pywin.debugger',
            'pywin.debugger.dbgcon', 'pywin.dialogs', 'tcl',
            'Tkconstants', 'Tkinter']

if PY2EXE_ACTIVE:
    data_files = [('imageformats', [
                        find_file_in_path("PyQt4/plugins/imageformats/qjpeg4.dll"),
                        find_file_in_path("PyQt4/plugins/imageformats/qmng4.dll"),
                        find_file_in_path("PyQt4/plugins/imageformats/qgif4.dll"),]
                     )
                    ]
else:
    data_files = []

setup(
    name = 'CuevanaLinks-GUI',
    version = __version__,
    description = 'A program to retrieve movies and series (or its links)\
                    from cuevana.tv',
    long_description = long_description,
    author = u'Martín Chikilian'.encode("UTF-8"),
    author_email = 'slacklinucs@gmail.com',
    url='https://github.com/mguillech/cuevanalinks-gui',
    packages = ['cuevanalinks-gui',],
    license = 'GNU GENERAL PUBLIC LICENCE v3.0 (see LICENCE.txt)',
    scripts = ['bin/cuevanalinks-gui'],
    package_data = {'cuevanalinks-gui': ['resources/*.png']},
    data_files = data_files,
    install_requires = ['pyquery>=0.5'],
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
      ],
    options = {"py2exe": {"compressed": 2,
                          "optimize": 0, #2,
                          "includes": ['sip'],
                          "excludes": excludes,
                          "packages": ['cuevanalinks-gui','lxml', 'gzip'],
                          "dll_excludes": dll_excludes,
                          "bundle_files": 3,
                          "dist_dir": "dist",
                          "xref": False,
                          "skip_archive": False,
                          "ascii": False,
                          "custom_boot_script": '',
                         }
              },
    windows=[{"script" : "bin/cuevanalinks-gui"}]
)

