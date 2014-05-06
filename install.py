#!/usr/bin/env python
# -*- coding: utf-8 -*-

# peter dot wells at lutraconsulting dot co dot uk
# Lutra Consulting
# 23 Chestnut Close
# Burgess Hill
# West Sussex
# RH15 8HN

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import sys
import os
import shutil
import platform
import glob

pkg = False

if len(sys.argv) > 1:
  for arg in sys.argv[1:]:
    if arg == '-pkg':
      pkg = True
    else:
      print "install.py [-pkg]"
      print ""
      print "  Install AutoTrace Python plugin"
      print ""
      print "  Arguments:"
      print "  -pkg      Create a package for upload instead of installing"
      sys.exit(0)

install_files = ['metadata.txt'] + glob.glob("*.py") + glob.glob("*.png")
install_files.remove("install.py")  # exclude this file!

if pkg:
  import zipfile
  pkgname = "autoTrace.zip"
  with zipfile.ZipFile(pkgname, "w", zipfile.ZIP_DEFLATED) as z:
    for filename in install_files:
      z.write(filename, "autoTrace/"+filename)
  print "-- package written: " + pkgname

else:
  plugin_dir = os.path.expanduser(os.path.join("~", ".qgis2", "python", "plugins", "autoTrace"))
  if not os.path.exists(plugin_dir):
    os.makedirs(plugin_dir)
    
  for filename in install_files:
    print "-- "+filename
    shutil.copy(filename, plugin_dir)
