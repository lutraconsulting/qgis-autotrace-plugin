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

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *

# initialize Qt resources from file resources.py
import resources

#Import own tools
from vertexTracerTool import VertexTracerTool

# Our main class for the plugin
class AutoTrace:
  
    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
    
    def initGui(self):
        mc = self.canvas
        layer = mc.currentLayer()
        
        self.rubberBand = 0
        
        # Create an action for getting help
        self.helpAction = QAction(QIcon(":/plugins/autoTrace/iconAutoTrace.png"), "Help", self.iface.mainWindow())
        QObject.connect(self.helpAction, SIGNAL("triggered()"), self.openHelp)
        self.menu = self.iface.pluginMenu().addMenu(QIcon(":/plugins/autoTrace/iconAutoTrace.png"), "AutoTrace")
        self.menu.addAction(self.helpAction)
          
        # Create action that will start plugin configuration
        self.action = QAction(QIcon(":/plugins/autoTrace/iconAutoTrace.png"), "Auto-trace", self.iface.mainWindow())
        self.action.setEnabled(False)
        self.action.setCheckable(True)
        self.action.setChecked(False)
        
        #Connect to signals for button behaviour
        QObject.connect(self.action, SIGNAL("triggered()"), self.run)
        QObject.connect(self.iface, SIGNAL("currentLayerChanged(QgsMapLayer*)"), self.toggle)
        QObject.connect(mc, SIGNAL("mapToolSet(QgsMapTool*)"), self.deactivate)
        
        # Add toolbar button 
        self.iface.digitizeToolBar().addAction(self.action)

        #Get the Tool
        self.tool = VertexTracerTool(self.canvas)
    
    def unload(self):
        self.iface.digitizeToolBar().removeAction(self.action)
        self.menu.removeAction(self.helpAction)
        self.iface.pluginMenu().removeAction(self.menu.menuAction())
    
    def openHelp(self):
        # Open the help page
        QDesktopServices.openUrl(QUrl('http://www.lutraconsulting.co.uk/resources/autotrace'))
    
    def toggle(self):
        mc = self.canvas
        layer = mc.currentLayer()
        
        #Decide whether the plugin button/menu is enabled or disabled
        if layer <> None:
            if layer.isEditable() and (layer.geometryType() == 1 or layer.geometryType() == 2):
                self.action.setEnabled(True)
                QObject.connect(layer,SIGNAL("editingStopped()"),self.toggle)
                QObject.disconnect(layer,SIGNAL("editingStarted()"),self.toggle)
          
            else:
                self.action.setEnabled(False)
                QObject.connect(layer,SIGNAL("editingStarted()"),self.toggle)
                QObject.disconnect(layer,SIGNAL("editingStopped()"),self.toggle)        
                
    def deactivate(self):
        #uncheck the button/menu and get rid off the VTTool signal
        self.action.setChecked(False)
        QObject.disconnect(self.tool, SIGNAL("traceFound(PyQt_PyObject)"), self.createFeature)
    
    def run(self):
        #Here we go...
        mc = self.canvas
        layer = mc.currentLayer()
      
        #bring our tool into action
        mc.setMapTool(self.tool)
        self.action.setChecked(True)
     
        #Connect to the VTtool
        QObject.connect(self.tool, SIGNAL("traceFound(PyQt_PyObject)"), self.createFeature)
        
        # Warn if there are no snapable layers
        if self.snappableLayerCount() < 1:
            self.iface.messageBar().pushMessage("AutoTrace", \
            "None of the enabled layers have snapping enabled - AutoTrace needs snappable layers in order to trace.", level=QgsMessageBar.WARNING)
            
    def snappableLayerCount(self):
        count = 0
        proj = QgsProject.instance()
        for layer in self.iface.mapCanvas().layers(): # Visible layers
            if proj.snapSettingsForLayer( layer.id() )[1]:
                count += 1
        return count
 
    def createFeature(self, geom):

        if not geom:
          return False  # invalid geometry (e.g. just one point for a polyline)

        layer = self.canvas.currentLayer() 
        provider = layer.dataProvider()
        fields = provider.fields()
        f = QgsFeature(fields)
        
        errors = geom.validateGeometry()
        if len(errors) == 0:
            f.setGeometry(geom)
        else:
            # Concatenate errors into a string
            errorsString = ""
            for error in errors:
                locationString = "[" + str(error.where().x()) + "," + str(error.where().y()) + "]"
                errorsString += error.what()
                errorsString += "\n  "
                errorsString += locationString
                errorsString += "\n"
            reply = QMessageBox.question(self.iface.mainWindow(), 'Feature not valid',
            "The geometry of the feature you just added isn't valid. Do you want to use it anyway?\n\n" + 
            "Errors were:\n\n" +
            errorsString,
            QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                f.setGeometry(geom)
            else:
                return False
      
        layer.beginEditCommand("Feature added")
        layer.addFeature(f)
        layer.endEditCommand()
        
        self.canvas.refresh()


