# -*- coding: utf-8 -*-

# AutoTrace - An editing tool for QGIS that allows users to 'trace' new
# feature geometry based on existing features.
# Copyright (C) 2012 Peter Wells for Lutra Consulting
# Based on traceDigitize by Cédric Möri with lots of stuff from Stefan 
# Ziegler (CAD-Tools)

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

def classFactory(iface):
    from autoTrace import AutoTrace
    return AutoTrace(iface)
