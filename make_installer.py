#!/usr/bin/env python
# -*- coding: utf-8 -*-

import subprocess
import cuevanalinks
import os.path

version = cuevanalinks.__version__
make_nsis = "C:\Archivos de programa\NSIS\makensis.exe"
version_param = '/DVERSION=%s' % version 
script = 'cuevanalinks.nsi'

subprocess.call(['python', 'setup.py', 'py2exe'])
subprocess.call([make_nsis, version_param, script])
print
print "Ok!..Installer done in cuevanalinks-%s-installer.exe" % version