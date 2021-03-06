'''
Created on 11.12.2010
Based on Kwasi Mensah's (kmensah@andrew.cmu.edu)
"The Fractal Plants Sample Program" from 8/05/2005
@author: Praios (Jan Brohl)
@license: BSD-license
Quat-patch and improved drawBody by Craig Macomber

Copyright (c) 2012, Jan Brohl
All rights reserved.

Redistribution and use in source and binary forms,
with or without modification,
are permitted provided that the following conditions are met:

    Redistributions of source code must retain the above copyright notice,
    this list of conditions and the following disclaimer.

    Redistributions in binary form must reproduce the above copyright notice,
    this list of conditions and the following disclaimer in the documentation
    and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE
GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''
#pandac.PandaModules on older panda3d versions
from panda3d.core import (NodePath, Geom, GeomNode,
TransformState, GeomVertexWriter, GeomTristrips,
GeomVertexRewriter, GeomVertexData, GeomVertexFormat,
Mat4, Vec3, CollisionNode, CollisionTube, Point3, Quat)
import math
import random


def clamp(value, minval, maxval):
    """
    clamp a value to at least minval and maxval at most
    """
    if value > maxval:
        return maxval
    elif value < minval:
        return minval
    else:
        return value


#this is for making the tree not too straight
def _randomBend(quat, maxBend=30):
    #angle=clamp(random.gauss(0,45),-90,90)
    #not sure which is better
    angle = random.randint(-90, 90)
    return _angleRandomAxis(quat, angle, maxBend)


def _angleRandomAxis(quat, angle, maxBend=30):
    q = Quat()
    #power of 2 here makes distribution even withint a circle
    # (makes larger bends are more likley as they are further spread)
    bendAngle = (random.random() ** 2) * maxBend
    #gauss might be more realistic but actually is far from perfect
    #bendAngle=clamp(random.gauss(0,maxBend*0.5),0,maxBend)
    q.setHpr((angle, bendAngle, 0))
    return q * quat


class FractalTree(NodePath):
    """
    Base class for fractal trees
    """
    def __init__(self, barkTexture, leafModel,
                 lengthList, numCopiesList, radiusList):
        """
        make tree from params
        """
        NodePath.__init__(self, "Tree Holder")
        self.numPrimitives = 0
        self.leafModel = leafModel
        self.barkTexture = barkTexture
        self.bodies = NodePath("Bodies")
        self.leaves = NodePath("Leaves")
        self.coll = self.attachNewNode(CollisionNode("Collision"))
        self.bodydata = GeomVertexData("body vertices",
                                       GeomVertexFormat.getV3n3t2(),
                                       Geom.UHStatic)
        self.drawFlags = set()
        self.numCopiesList = list(numCopiesList)
        self.radiusList = list(radiusList)
        self.lengthList = list(lengthList)
        self.iterations = 1

        self.makeEnds()
        self.makeFromStack(True)
        #self.coll.show()
        self.bodies.setTexture(barkTexture)
        self.coll.reparentTo(self)
        self.bodies.reparentTo(self)
        self.leaves.reparentTo(self)

    def getStatic(self):
        """
        this makes a flattened version of the tree for faster rendering...
        """
        np = NodePath(self.node().copySubgraph())
        np.flattenStrong()
        return np

    def makeEnds(self, pos=Vec3(0, 0, 0), quat=None):
        """
        add initial stem-end to the stack of ends
        """
        if quat is None:
            quat = Quat()
        self.ends = [(pos, quat, 0)]

    def makeFromStack(self, makeColl=False):
        """
        update tree geometry using existing ends
        """
        stack = self.ends
        to = self.iterations
        lengthList = self.lengthList
        numCopiesList = self.numCopiesList
        radiusList = self.radiusList
        ends = []
        while stack:
            pos, quat, depth = stack.pop()
            length = lengthList[depth]
            if depth != to and depth + 1 < len(lengthList):
                self.drawBody(pos, quat, radiusList[depth])
                #move foward along the right axis
                newPos = pos + quat.xform(length)
                if makeColl:
                    self.makeColl(pos, newPos, radiusList[depth])
                numCopies = numCopiesList[depth]
                if numCopies:
                    for i in xrange(numCopies):
                        stack.append((newPos,
                                      _angleRandomAxis(quat,
                                                       2 * math.pi * i /
                                                       numCopies),
                                      depth + 1))
                        #stack.append((newPos, _randomAxis(vecList,3),
                        #depth + 1))
                else:
                    #just make another branch connected to this one with a
                    #small variation in direction
                    stack.append((newPos, _randomBend(quat, 20), depth + 1))
            else:
                ends.append((pos, quat, depth))
                self.drawBody(pos, quat, radiusList[depth], False)
                self.drawLeaf(pos, quat)
        self.ends = ends

    def makeColl(self, pos, newPos, radius):
        """
        make a collision tube for the given stem-parameters
        """
        tube = CollisionTube(Point3(pos), Point3(newPos), radius)
        self.coll.node().addSolid(tube)

    def drawBody(self, pos, quat, radius=1, keepDrawing=True, numVertices=16):
        """
        this draws the body of the tree. This draws a ring of vertices and
        connects the rings with triangles to from the body.

        the keepDrawing parameter tells the function whether or not we're
        at an end
        if the vertices before were an end, don't draw branches to it
        """
        vdata = self.bodydata
        circleGeom = Geom(vdata)
        vertWriter = GeomVertexWriter(vdata, "vertex")
        normalWriter = GeomVertexWriter(vdata, "normal")
        texReWriter = GeomVertexRewriter(vdata, "texcoord")
        startRow = vdata.getNumRows()
        vertWriter.setRow(startRow)
        normalWriter.setRow(startRow)
        sCoord = 0
        if (startRow != 0):
            texReWriter.setRow(startRow - numVertices)
            sCoord = texReWriter.getData2f().getX() + 1
            draw = (startRow - numVertices) in self.drawFlags
            if not draw:
                sCoord -= 1
        drawIndex = startRow
        texReWriter.setRow(startRow)

        angleSlice = 2 * math.pi / numVertices
        currAngle = 0
        perp1 = quat.getRight()
        perp2 = quat.getForward()
        #vertex information is written here
        for i in xrange(numVertices + 1):
            #doubles the last vertex to fix UV seam
            adjCircle = pos + (perp1 * math.cos(currAngle) +
                               perp2 * math.sin(currAngle)) * radius
            normal = perp1 * math.cos(currAngle) + perp2 * math.sin(currAngle)
            normalWriter.addData3f(normal)
            vertWriter.addData3f(adjCircle)
            texReWriter.addData2f(1.0 * i / numVertices, sCoord)
            if keepDrawing:
                self.drawFlags.add(drawIndex)
            drawIndex += 1
            currAngle += angleSlice
        draw = (startRow - numVertices) in self.drawFlags
        #we cant draw quads directly so we use Tristrips
        if (startRow != 0) and draw:
            lines = GeomTristrips(Geom.UHStatic)
            for i in xrange(numVertices + 1):
                lines.addVertex(i + startRow)
                lines.addVertex(i + startRow - numVertices - 1)
            lines.addVertex(startRow)
            lines.addVertex(startRow - numVertices)
            lines.closePrimitive()
            #lines.decompose()
            circleGeom.addPrimitive(lines)
            circleGeomNode = GeomNode("Debug")
            circleGeomNode.addGeom(circleGeom)
            self.numPrimitives += numVertices * 2
            self.bodies.attachNewNode(circleGeomNode)

    def drawLeaf(self, pos=Vec3(0, 0, 0), quat=None, scale=0.125):
        """
        this draws leafs when we reach an end
        """
        #use the vectors that describe the direction the branch grows to make
        #the right rotation matrix
        newCs = Mat4()
        quat.extractToMatrix(newCs)
        axisAdj = Mat4.scaleMat(scale) * newCs * Mat4.translateMat(pos)
        leafModel = NodePath("leaf")
        self.leafModel.instanceTo(leafModel)
        leafModel.reparentTo(self.leaves)
        leafModel.setTransform(TransformState.makeMat(axisAdj))

    def grow(self, num=1, removeLeaves=True, leavesScale=1, scale=1.125):
        """
        Grows the tree num steps
        """
        self.iterations += num
        while num > 0:
            self.setScale(self, scale)
            self.leafModel.setScale(self.leafModel, leavesScale / scale)
            if removeLeaves:
                for c in self.leaves.getChildren():
                    c.removeNode()
            self.makeFromStack()
            self.bodies.setTexture(self.barkTexture)
            num -= 1


class SimpleTree(FractalTree):
    """
    Baseclass for simple trees
    """
    @staticmethod
    def makeRadiusList(radius, iterations, numCopiesList, scale=1.125):
        """
        make a basic radiuslist
        """
        l = [radius]
        for i in xrange(1, iterations):
            if i != 1 and numCopiesList[i - 2]:
                radius /= numCopiesList[i - 2] ** 0.5
            else:
                radius /= scale
            l.append(radius)
        return l

    @staticmethod
    def makeLengthList(length, iterations, sx=1.125, sy=1.125, sz=1.125):
        """
        make a basic lengthlist
        """
        l = [length]
        for i in xrange(1, iterations):
            length = Vec3(length.getX() / sx,
                          length.getY() / sy,
                          length.getZ() / sz)
            l.append(length)
        return l

    @staticmethod
    def makeNumCopiesList(numCopies, branchat, iterations):
        """
        make a basic numpobieslist
        branching each branchat iterations with numCopies branches each
        """
        l = list()
        for i in xrange(iterations):
            if i % int(branchat) == 0:
                l.append(numCopies)
            else:
                l.append(0)
        return l


class DefaultTree(SimpleTree):
    """
    Example tree class
    """
    barkTexturePath = "models/tree/default/barkTexture.jpg"
    leafModelPath = 'models/tree/default/shrubbery'
    leafTexturePath = 'models/tree/default/material-10-cl.png'

    def __init__(self, radius=0.5, numCopies=3, branchat=3, iterations=64):
        """
        make new tree using few parameters
        """
        barkTexture = base.loader.loadTexture(self.barkTexturePath)
        leafModel = base.loader.loadModel(self.leafModelPath)
        leafModel.clearModelNodes()
        leafModel.flattenStrong()
        leafTexture = base.loader.loadTexture(self.leafTexturePath)
        leafModel.setTexture(leafTexture, 1)
        lengthList = self.makeLengthList(Vec3(0, 0, 1), iterations)
        numCopiesList = self.makeNumCopiesList(numCopies, branchat, iterations)
        radiusList = self.makeRadiusList(radius, iterations, numCopiesList)
        SimpleTree.__init__(self, barkTexture, leafModel,
                            lengthList, numCopiesList, radiusList)


#this grows a tree
if __name__ == "__main__":
    from direct.showbase.ShowBase import ShowBase
    base = ShowBase()
    base.cam.setPos(0, -10, 10)
    t = DefaultTree()
    t.reparentTo(base.render)
    #make an optimized snapshot of the current tree
    np = t.getStatic()
    np.setPos(10, 10, 0)
    np.reparentTo(base.render)
    #demonstrate growing
    last = [0]  # a bit hacky

    def grow(task):
        if task.time > last[0] + 1:
            t.grow()
            last[0] = task.time
            #t.leaves.detachNode()
        if last[0] > 10:
            return task.done
        return task.cont

    base.taskMgr.add(grow, "growTask")
    base.run()
