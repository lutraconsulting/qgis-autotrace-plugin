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

"""
    Behavior of the auto method of tracing:
    
    *cursor is within snapable distance of a vertice with the shift key goes down
    
    onMouseMove:
        Remove any uncommitted vertices from the rubber band
        If shift is down:
            call proposeRBUpdate()
        
    onShiftKeyGoingDown:
        call proposeRBUpdate()
      
    onShistKeyComingUp:
        Remove any uncommitted vertices from the rubber band
    
    Function proposeRBUpdate():
        If the last point in the RB is snapped to a feature:
            If we're currently snapping to the same feature:
                Determine the vertices that make the shortest path between v1 and v2
                Add them as uncommitted vertices to the rb
        
    If the left button is clicked and the shift key is down:
        Unmark any vertices marked as preliminary
        
    
    High level
    ==========
    
    When the user presses shift and hovers over a vertice, the rubber-band
    should update to show the auto-traced path around the 
  
"""

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *

# Vertex Finder Tool class
class VertexTracerTool(QgsMapTool):
    
    def __init__(self, canvas):

        QgsMapTool.__init__(self,canvas)
        self.canvas=canvas
        self.started = False
        self.snapper = QgsMapCanvasSnapper(self.canvas)
        self.snapIndicator = None
        self.mCtrl = False
        self.mShift = False
        self.lastPoint = None
        self.pointsProposed = False
        self.propVertCnt = 0
        self.snappedLayer = None
        self.snappedGeometry = None
        self.snappedVertexNr = None
        self.snappedPartNr = None
        self.snappedRingNr = None
        self.snappedRingVertexOffset = None
        self.snappedToPolygon = False

        self.rb = QgsRubberBand(self.canvas, QGis.Line)
        self.rb.setColor(QColor(255, 0, 0))

        self.autoCursor = QCursor(QPixmap(["16 16 3 1",
                                          "      c None",
                                          ".     c #FF00FF",
                                          "+     c #FFFFFF",
                                          "                ",
                                          "       +.+      ",
                                          "      ++.++     ",
                                          "     +.....+    ",
                                          "    +.     .+   ",
                                          "   +.   .   .+  ",
                                          "  +.    .    .+ ",
                                          " ++.    .    .++",
                                          " ... ...+... ...",
                                          " ++.    .    .++",
                                          "  +.    .    .+ ",
                                          "   +.   .   .+  ",
                                          "   ++.     .+   ",
                                          "    ++.....+    ",
                                          "      ++.++     ",
                                          "       +.+      "]))
                                    
    def proposeRBUpdate(self, event=None):
        """
          Pop the last vert off the rb (the current mouse position)
          Push our proposed ones on
          Make not of how many proposed verts were added (propVertCnt)
          Push back the last vert
        """
        if self.started:
          
            # We have to do our capturing of mouse coords here else we just end up popping the same point off and on again if moving
            # i.e. the cursor doesn't follow the mouse
            
            if self.snappedLayer is None:
                return
            
            newMouseP = None
            retval = 0
            snapResults = []
            if event is not None:
                x = event.pos().x()
                y = event.pos().y()
                newMouseP =  QgsMapToPixel.toMapCoordinates(self.canvas.getCoordinateTransform (), x, y)
                eventPoint = QPoint(x,y)
                (retval,snapResults) = self.snapper.snapToBackgroundLayers(eventPoint)
            else:
                x = self.canvas.mouseLastXY().x()
                y = self.canvas.mouseLastXY().y()
                vertCount = self.rb.numberOfVertices()
                #newMouseP = QgsPoint( self.rb.getPoint( 0, vertCount - 1 ) )
                
                (retval,snapResults) = self.snapper.snapToBackgroundLayers( QPoint(x,y) )
              
            if len(snapResults) < 1:
                # There was nothing to snap to here, just update the end of the rb
                self.clearSnapIndicator()
                point = QgsMapToPixel.toMapCoordinates(self.canvas.getCoordinateTransform (), x, y)
                self.rb.movePoint(point)
                return
            else:
                self.updateSnapIndicator(snapResults[0].snappedVertex)
                part, ring = self.getPartAndRing(snapResults[0].layer, snapResults[0].snappedAtGeometry, snapResults[0].snappedVertexNr)
                if snapResults[0].layer <> self.snappedLayer or \
                    snapResults[0].snappedAtGeometry <> self.snappedGeometry or \
                    self.snappedPartNr != part or \
                    self.snappedRingNr != ring:
                    # We snapped to something but we can't do anything fancy with it
                    self.rb.movePoint(snapResults[0].snappedVertex)
                    return
                
            # By this point, we should be snapping to the same layer and geomtry as last time (so we can now 
            # calculate paths between the two points
            
            self.rb.removeLastPoint()
            
            # Now determine the points that we need to add
            newVerts = self.getAdditionalVerts( snapResults[0].snappedVertexNr )
            
            for newVert in newVerts:
                f = QgsFeature()
                self.snappedLayer.getFeatures(QgsFeatureRequest(self.snappedGeometry)).nextFeature(f)
                if self.snappedToPolygon:
                    v = f.geometry().vertexAt(newVert)
                else:
                    v = f.geometry().vertexAt(newVert)
                if self.snappedLayer != None and self.snappedLayer.crs() != self.canvas.currentLayer().crs():
                    v = self.reprojectPoint(v)
                v = self.canvas.mapRenderer().layerToMapCoordinates(self.snappedLayer, v)
                self.rb.addPoint(v,False)
                self.propVertCnt += 1
                self.pointsProposed = True
            self.rb.update()
            
            self.rb.addPoint(snapResults[0].snappedVertex)
      
    def getAdditionalVerts( self, secondVertexNr ):
        """
            For a given geometry (even multi-part polygons) determien the 
            shortest (or longest) route between:
              
                self.snappedVertexNr
                and
                secondVertexNr
                on
                self.snappedGeometry
                
                Are they both the same vertice?
                    Are they really the same vertice (0 and 4 in a square)
        """
        
        firstVertexNr = self.snappedVertexNr
        
        firstVertexNr -= self.snappedRingVertexOffset
        secondVertexNr -= self.snappedRingVertexOffset
        
        if firstVertexNr == secondVertexNr:
            return []
        
        largerNr = max(firstVertexNr,secondVertexNr)
        smallerNr = min(firstVertexNr,secondVertexNr)
        
        f = QgsFeature()
        self.snappedLayer.getFeatures(QgsFeatureRequest(self.snappedGeometry)).nextFeature(f)
        
        if not f.geometry().isMultipart():
            if f.geometry().type() == QGis.Line:
                vertCount = len( f.geometry().asPolyline() )
            else:
                vertCount = len( f.geometry().asPolygon()[self.snappedRingNr] )
        else:
            if f.geometry().type() == QGis.Line:
                vertCount = len( f.geometry().asMultiPolyline()[self.snappedPartNr] )
            else:
                vertCount = len( f.geometry().asMultiPolygon()[self.snappedPartNr][self.snappedRingNr] )
        
        if self.snappedToPolygon:
            if ((firstVertexNr == vertCount-1) and (secondVertexNr == 0)) or ((secondVertexNr == vertCount-1) and (firstVertexNr == 0)):
                return []
        
        if self.snappedToPolygon:
            # Determine which route is shorter
            joinFaster = False
            normalDistance = largerNr - smallerNr
            joinDistance = (vertCount - largerNr - 1) + smallerNr
            if joinDistance < normalDistance:
                joinFaster = True
            if self.mCtrl:
                joinFaster = not(joinFaster)
            
            if joinFaster:
                if secondVertexNr > firstVertexNr:
                    a = range(firstVertexNr-1,-1,-1)
                    b = range(vertCount-2,secondVertexNr,-1)
                    a.extend(b)
                    return [x+self.snappedRingVertexOffset for x in a]
                else:
                    a = range(firstVertexNr+1,vertCount,1)
                    b = range(1,secondVertexNr,1)
                    a.extend(b)
                    return [x+self.snappedRingVertexOffset for x in a]
            
        # else if jointFaster is not true
        if secondVertexNr > firstVertexNr:
            newverts = range(firstVertexNr+1,secondVertexNr,1)
            return [x+self.snappedRingVertexOffset for x in newverts]
        else:
            newverts = range(firstVertexNr-1,secondVertexNr,-1)
            return [x+self.snappedRingVertexOffset for x in newverts]
    
    
    def reprojectPoint(self, srcPt):
        """ In the event we are tracing from a layer with different 
        projection we will need to reproject traced vertices to the 
        projection of the layer we are editing """
        
        src = self.snappedLayer.crs()
        dst = self.canvas.currentLayer().crs()
        trans = QgsCoordinateTransform(src, dst)
        return trans.transform(srcPt)
        
    
    def acceptProposedRBUpdate(self):
        self.propVertCnt = 0
        self.pointsProposed = False
    
      
    def revertProposedRBUpdate(self):
        """
            Pop the last vert off the rb
            Pop off and discard propVertCnt vertices
            Push the last vert back on again
        """
        if self.pointsProposed:
            mouseP = QgsPoint( self.rb.getPoint( 0, self.rb.numberOfVertices()-1 ) )
            self.rb.removeLastPoint()
            for i in range(self.propVertCnt):
                self.rb.removeLastPoint()
            self.rb.addPoint(mouseP)
            self.propVertCnt = 0
            self.pointsProposed = False
    
    def keyPressEvent(self,  event):
        if event.key() == Qt.Key_Control:
            self.mCtrl = True
            if self.mShift:
                self.revertProposedRBUpdate()
                self.proposeRBUpdate()
        if event.key() == Qt.Key_Shift:
            self.mShift = True
            self.proposeRBUpdate()

    def keyReleaseEvent(self,  event):
        if event.key() == Qt.Key_Control:
            self.mCtrl = False
            if self.mShift:
                self.revertProposedRBUpdate()
                self.proposeRBUpdate()
        if event.key() == Qt.Key_Shift:
            self.mShift = False
            self.revertProposedRBUpdate()
        #remove the last added point when the delete key is pressed
        if event.key() == Qt.Key_Backspace:
            self.removeLastPoint()

    def removeLastPoint(self):
        if self.rb.numberOfVertices() > 0:
            self.rb.removeLastPoint()
        rbVertCount = self.rb.numberOfVertices()
        if rbVertCount >= 2:
            lastPoint = self.rb.getPoint(0, rbVertCount-2)
            lastPointOnScreen = self.canvas.getCoordinateTransform().transform(lastPoint)
            retval, snapResults = self.snapper.snapToBackgroundLayers(QPoint( lastPointOnScreen.x(), lastPointOnScreen.y()))
            if len(snapResults) > 0:
                self.updateDetailsOfLastSnap(snapResults[0])
            else:
                self.updateDetailsOfLastSnap()
        else:
            self.updateDetailsOfLastSnap()

    def canvasPressEvent(self,event):
        #on left click, we add a point
        if event.button() == Qt.LeftButton:
            layer = self.canvas.currentLayer()
            if not layer:
              return

            #if it the start of a new trace, set the rubberband up
            if self.started == False:
                self.rb.reset(layer.geometryType())
                self.lastPoint = None
            
            self.started = True
            self.acceptProposedRBUpdate()
            
            if layer <> None:
                #if self.mCtrl == False:
                x = event.pos().x()
                y = event.pos().y()
                selPoint = QPoint(x,y)
                (retval,result) = self.snapper.snapToBackgroundLayers(selPoint)
                
                #the point is either from snapping result
                if result  <> []:
                    point = result[0].snappedVertex
                    self.updateDetailsOfLastSnap(result[0])
                    
                #or just a plain point
                else:
                    point =  QgsMapToPixel.toMapCoordinates(self.canvas.getCoordinateTransform (), x, y)
                    self.updateDetailsOfLastSnap()
                  
                self.appendPoint(QgsPoint(point))
            
    
    def getPartAndRing(self, layer, featureId, snappedVertNr):
      """ Return the index of the part and ring that snappedVertNr exists 
      in.  Lines will always have ring=0. """
      
      f = QgsFeature()
      layer.getFeatures(QgsFeatureRequest(featureId)).nextFeature(f)
      geom = f.geometry()
      snapGeom = QgsGeometry().fromPoint( geom.vertexAt(snappedVertNr) )
      
      if not geom.isMultipart():
          if geom.type() == QGis.Line:
              # If it was not snapped to this line, we wouldn't even be here
              self.snappedRingVertexOffset = 0
              return 0, 0
          elif geom.type() == QGis.Polygon:
              ringId = 0
              vertOffset = 0
              for ring in geom.asPolygon():
                  if ringId > 0:
                      vertOffset += lastRingLen
                  ringGeom = QgsGeometry().fromPolyline( ring )
                  if snapGeom.intersects(ringGeom):
                      self.snappedRingVertexOffset = vertOffset
                      return 0, ringId
                  ringId += 1
                  lastRingLen = len(ring)
              self.snappedRingVertexOffset = 0
              return 0, 0 # We should not get here
          else:
              self.snappedRingVertexOffset = 0
              return 0, 0
      
      else:
          # Multipart
          if geom.type() == QGis.Line:
              partId = 0
              vertOffset = 0
              for part in geom.asMultiPolyline():
                  if partId > 0:
                      vertOffset += lastLineLength
                  lineGeom = QgsGeometry().fromPolyline( part )
                  if lineGeom.intersects(snapGeom):
                      self.snappedRingVertexOffset = vertOffset
                      return partId, 0
                  partId += 1
                  lastLineLength = len(part)
              return 0, 0 # We should not get here
          elif geom.type() == QGis.Polygon:
              partId = 0
              vertOffset = 0
              for part in geom.asMultiPolygon():
                  ringId = 0
                  for ring in part:
                      if partId > 0 or ringId > 0:
                          vertOffset += lastRingLen
                      ringGeom = QgsGeometry().fromPolyline( ring )
                      if snapGeom.intersects(ringGeom):
                          self.snappedRingVertexOffset = vertOffset
                          return partId, ringId
                      ringId += 1
                      lastRingLen = len(ring)
                  partId += 1
              self.snappedRingVertexOffset = 0
              return 0, 0 # We should not get here
          else:
              self.snappedRingVertexOffset = 0
              return 0, 0

    def updateDetailsOfLastSnap(self, snappingResult=None):
        if snappingResult is not None:
            self.snappedLayer = snappingResult.layer
            self.snappedGeometry = snappingResult.snappedAtGeometry
            self.snappedVertexNr = snappingResult.snappedVertexNr
            part, ring = self.getPartAndRing(self.snappedLayer, self.snappedGeometry, self.snappedVertexNr)
            self.snappedPartNr = part
            self.snappedRingNr = ring
            if self.snappedLayer.geometryType() == 2:
                self.snappedToPolygon = True
            else:
                self.snappedToPolygon = False
        else:
            self.snappedLayer = None
            self.snappedGeometry = None
            self.snappedVertexNr = None
            self.snappedPartNr = None
            self.snappedRingNr = None
            self.snappedRingVertexOffset = None
            self.snappedToPolygon = False
         
    def initialiseSnapIndicator(self, position):
        self.snapIndicator = QgsVertexMarker(self.canvas)
        self.snapIndicator.setIconType(QgsVertexMarker.ICON_CROSS)
        self.snapIndicator.setIconSize(20)
        self.snapIndicator.setColor( QColor(85,85,85) )
        self.snapIndicator.setPenWidth(1)
    
    def updateSnapIndicator(self, newPosition):
        if self.snapIndicator == None:
            self.initialiseSnapIndicator(newPosition)
        else:
            self.snapIndicator.setCenter(newPosition)
      
    def clearSnapIndicator(self):
        if self.snapIndicator != None:
            self.canvas.scene().removeItem(self.snapIndicator)
            self.snapIndicator = None
       
    def canvasMoveEvent(self,event):
        
        x = event.pos().x()
        y = event.pos().y()
        eventPoint = QPoint(x,y)
        
        if self.started:
            if self.mShift and self.snappedLayer is not None:
                self.revertProposedRBUpdate()
                self.proposeRBUpdate(event)
            else:
                # If there is a snapable point nearby, move the end of the rb to it
                (retval,result) = self.snapper.snapToBackgroundLayers(eventPoint)
                if result <> []:
                    self.rb.movePoint(result[0].snappedVertex)
                    self.updateSnapIndicator(result[0].snappedVertex)
                else:
                    point = QgsMapToPixel.toMapCoordinates(self.canvas.getCoordinateTransform (), x, y)
                    self.rb.movePoint(point)
                    self.clearSnapIndicator()
        # Display the snap indicator even if we have not yet started
        else:
            (retval,result) = self.snapper.snapToBackgroundLayers(eventPoint)
            if len(result) > 0:
                self.updateSnapIndicator(result[0].snappedVertex)
            else:
                self.clearSnapIndicator()

    def canvasReleaseEvent(self, event):
        #with right click the digitizing is finished
        if self.mShift:
            # User can only finish digitising when they are not holding down shift
            return
        if event.button() == Qt.RightButton:
            if self.canvas.currentLayer() and self.started == True:
                self.sendGeometry()
            #remember that this trace is finished, the next left click starts a new one
            self.started = False
            self.clearSnapIndicator()

    def appendPoint(self, point):
        #don't add the point if it is identical to the last point we added
        if (self.lastPoint <> point) :
            self.rb.addPoint(point)
            self.lastPoint = point
      
    def sendGeometry(self):
        layer = self.canvas.currentLayer() 

        coords = []
        #backward compatiblity for a bug in qgsRubberband, that was fixed in 1.7
        if QGis.QGIS_VERSION_INT >= 10700:
            #[coords.append(self.rb.getPoint(0, i)) for i in range(self.rb.numberOfVertices())]
            [ coords.append(self.rb.getPoint(0, i)) for i in range(self.rb.numberOfVertices()-1) ] # PW Fix for duplicate final vertice when adding lines
        else:
            [coords.append(self.rb.getPoint(0,i)) for i in range(1,self.rb.numberOfVertices())]

        ## On the Fly reprojection.
        layerEPSG = layer.crs().authid()
        projectEPSG = self.canvas.mapRenderer().destinationCrs().authid()
        
        if layerEPSG != projectEPSG:
            coords_tmp = coords[:]
            coords = []
            for point in coords_tmp:
                transformedPoint = self.canvas.mapRenderer().mapToLayerCoordinates( layer, point );
                coords.append(transformedPoint)
           
            coords_tmp = coords[:]
            coords = []
            lastPt = None
            for pt in coords_tmp:
                if (lastPt <> pt) :
                    coords.append(pt)
                    lastPt = pt
           
        ## Add geometry to feature.
        if layer.geometryType() == QGis.Polygon:
            g = QgsGeometry().fromPolygon([coords])
        else:
            g = QgsGeometry().fromPolyline(coords)
        
        self.emit(SIGNAL("traceFound(PyQt_PyObject)"),g) 
        
        #self.emit(SIGNAL("traceFound(PyQt_PyObject)"),self.rb.asGeometry()) 
        self.rb.reset(layer.geometryType())

    def activate(self):
        self.canvas.setCursor(self.autoCursor)
        
    def deactivate(self):
        try:
            self.rb.reset()
        except AttributeError:
            pass

    def isZoomTool(self):
        return False
    
    def isTransient(self):
        return False
      
    def isEditTool(self):
        return True
