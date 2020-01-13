# -*- coding: utf-8 -*-
"""
Bantukul Olarn
Bo.BantukulOlarn@gmail.com
==============================================================================
Script short explanation:

N/A
"""
from __future__ import (
    print_function,
    absolute_import,
    division,
)

import functools
import collections

import maya.OpenMaya as om
import maya.OpenMayaMPx as ommpx
import maya.cmds as cmds

_MANUAL_REDO_DATA = collections.namedtuple(
    "_MANUAL_REDO_DATA",
    [
        "shp_name",
        "trn_name",
    ]
)


class polyModifierNode(ommpx.MPxNode):
    inMesh = om.MObject()
    outMesh = om.MObject()

    def __init__(self):
        super(polyModifierNode, self).__init__()


class polyModifierFty(object):
    def doIt(self):
        pass


class polyModifierCmd(ommpx.MPxCommand):
    NULL_VECTOR = om.MObject()

    # region protected
    ## initialization
    def __init__(self):
        super(polyModifierCmd, self).__init__()

        # polymesh
        self._fDagPathInitialized = False
        self._fDagPath = om.MDagPath()
        self._fDuplicateDagPath = om.MDagPath()

        # modifier node type
        self._fModifierNodeTypeInitialized = False
        self._fModifierNodeNameInitialized = False
        self._fModifierNodeType = om.MTypeId()
        self._fModifierNodeName = ""

        # node state

        self._fHasHistory = False
        self._fHasTweaks = False
        self._fHasRecordHistory = False

        # cached tweak data

        self._fTweakIndexArray = om.MIntArray()
        self._fTweakVectorArray = om.MFloatVectorArray()

        # cached mesh data

        self._fMeshData = om.MObject()

        # dg and dag modifier

        self._fDGModifier = om.MDGModifier()
        self._fDagModifier = om.MDagModifier()

        # manual shape management
        self._manual_redo_queue = []

        numDataFn = om.MFnNumericData()
        numDataFn.create(om.MFnNumericData.k3Float)
        numDataFn.setData3Float(0.0, 0.0, 0.0)
        self.__class__.NULL_VECTOR = numDataFn.object()

    # target poly mesh
    def _setMeshNode(self, mesh):
        # type: (om.MDagPath) -> None
        self._fDagPath = mesh
        self._fDagPathInitialized = True

    def _getMeshNode(self):
        # type: () -> om.MDagPath
        return self._fDagPath

    # modifier node type
    def _setModifierNodeType(self, type):
        # type: (om.MTypeId) -> None
        self._fModifierNodeType = type
        self._fModifierNodeTypeInitialized = True

    def _setModifierNodeName(self, name):
        # type: (str) -> None
        self._fModifierNodeName = name
        self._fModifierNodeNameInitialized = True

    def _getModifierNodeType(self):
        # type: ()-> om.MTypeId
        return self._fModifierNodeType

    def _getModifierNodeName(self):
        # type: ()-> str
        return self._fModifierNodeName

    # execution
    def _initModifierNode(self, modifierNode):
        # type: (om.MObject) -> None
        pass

    def _directModifier(self, mesh):
        # type: (om.MObject) -> None
        pass

    def _doModifyPoly(self):
        # type: () -> None
        if self.__isCommandDataValid():
            self.__collectNodeState()
            if not self._fHasHistory and not self._fHasRecordHistory:
                meshNode = self._fDagPath.node()

                self.__cacheMeshData()
                self.__cacheMeshTweaks()

                self._directModifier(meshNode)

            else:
                modifierNode = om.MObject()
                self.__createModifierNode(modifierNode)
                self._initModifierNode(modifierNode)
                self.__connectNodes(modifierNode)

    def _redoModifyPoly(self):
        # type: () -> None
        if not self._fHasHistory and not self._fHasRecordHistory:
            meshNode = self._fDagPath.node()
            self._directModifier(meshNode)
        else:
            trn_dag = None

            data = self._modifyPolyData()
            self.__processMeshNode(data)

            mesh_shape_dep = om.MFnDependencyNode(data.meshNodeShape)
            mesh_tweak_plug = mesh_shape_dep.findPlug("pnts")

            # reset shape nodes here because dgmodifier will recreate tweak node already
            # with appropriate pnts and will lead to double tweak

            if not self._fHasHistory:

                if self._manual_redo_queue:
                    redo_data = self._manual_redo_queue.pop()
                    print("recreate dup mesh", redo_data)
                    trn_dag = self._create_duplicate_mesh_source(data, redo_data)

                self._fDagModifier.doIt()

            self._fDGModifier.doIt()

            # self.__reset_pnts(mesh_tweak_plug)

            if trn_dag:
                om.MGlobal.deleteNode(trn_dag.object())

    def _undoModifyPoly(self):
        # type: () -> None
        if not self._fHasHistory and not self._fHasRecordHistory:
            self.__undoDirectModifier()
        else:
            self._fDGModifier.undoIt()

            if not self._fHasHistory:
                self.__undoCacheMesh()
                self._fDagModifier.undoIt()

            self.__undoTweakProcessing()

            if self._fDuplicateDagPath.isValid():
                dupMesh_dep = om.MFnDependencyNode(self._fDuplicateDagPath.node())
                # if dupmesh.
                print("final dup mesh ", dupMesh_dep.name(), dupMesh_dep.absoluteName())
                dup_mesh_trn_dep = om.MFnDependencyNode(self._fDuplicateDagPath.transform())
                dup_mesh_trn_dag = om.MFnDagNode(self._fDuplicateDagPath.transform())
                print("final dup mesh trn", dup_mesh_trn_dep.name(),
                      dup_mesh_trn_dag.fullPathName())

                self._manual_redo_queue.append(
                    _MANUAL_REDO_DATA(
                        shp_name=dupMesh_dep.name(),
                        trn_name=dup_mesh_trn_dep.name(),
                    )
                )
                print("recreate cmd queued", self._manual_redo_queue)

                om.MGlobal.deleteNode(self._fDuplicateDagPath.transform())

                # self._fDGModifier.deleteNode(self._fDuplicateDagPath.node())
                # self._fDGModifier.deleteNode(self._fDuplicateDagPath.transform())
                # self._fDGModifier.doIt()

                # cmd = "delete {0};".format(dupMeshTrnDag.fullPathName())
                # print("execute", cmd)
                # om.MGlobal.executeCommand(cmd, True, False)
                # om.MGlobal.executeCommandOnIdle(cmd)
                # def _a():
                #     print("delayed delete shape node")
                #     print("still undoing?", om.MGlobal.isUndoing())
                #     # om.MGlobal.deleteNode(self._fDuplicateDagPath.transform())

                # cmds.evalDeferred(_a, evaluateNext=True)

                # self._fDGModifier.deleteNode(self._fDuplicateDagPath.transform())
                # self._fDGModifier.doIt()

            else:
                pass

        # self.__clear_tweak_data()
        # todo check and schedule delete for orphaned duplicate mesh

    # endregion

    # region private

    class _modifyPolyData(object):

        def __init__(self):
            self.meshNodeTransform = om.MObject()
            self.meshNodeShape = om.MObject()
            self.meshNodeDestPlug = om.MPlug()
            self.meshNodeDestAttr = om.MObject()

            self.upstreamNodeTransform = om.MObject()
            self.upstreamNodeShape = om.MObject()
            self.upstreamNodeSrcPlug = om.MPlug()
            self.upstreamNodeSrcAttr = om.MObject()

            self.modifierNodeSrcAttr = om.MObject()
            self.modifierNodeDestAttr = om.MObject()

            self.tweakNode = om.MObject()
            self.tweakNodeSrcAttr = om.MObject()
            self.tweakNodeDestAttr = om.MObject()

            self._initial_assign = self._maya_api_assign

        def debug(self, node):
            depNode = om.MFnDependencyNode()

            attrfn = om.MFnAttribute()

            depNode.setObject(self.upstreamNodeShape)
            attrfn.setObject(self.upstreamNodeSrcAttr)
            plug = om.MPlug(node, self.upstreamNodeSrcAttr)

            attrfn.setObject(self.modifierNodeSrcAttr)
            attrfn.setObject(self.modifierNodeDestAttr)

            depNode.setObject(self.meshNodeShape)
            attrfn.setObject(self.meshNodeDestAttr)
            plug = om.MPlug(node, self.meshNodeDestAttr)

        def _initial_assign(self, key, value):
            return super(polyModifierCmd._modifyPolyData, self).__setattr__(key, value)

        def _maya_api_assign(self, key, value):
            obj = getattr(self, key)
            obj.assign(value)

        def __setattr__(self, key, value):
            self._initial_assign(key, value)

    # internal method

    def __isCommandDataValid(self):
        valid = True

        if self._fDagPathInitialized:
            self._fDagPath.extendToShape()
            if not self._fDagPath.isValid() or not self._fDagPath.apiType() == om.MFn.kMesh:
                valid = False
        else:
            valid = False

        if not self._fModifierNodeTypeInitialized and not self._fModifierNodeNameInitialized:
            valid = False

        return valid

    def __collectNodeState(self):
        self._fDagPath.extendToShape()
        meshNodeShape = self._fDagPath.node()

        depNodeFn = om.MFnDependencyNode(meshNodeShape)

        inMeshPlug = depNodeFn.findPlug("inMesh")
        self._fHasHistory = inMeshPlug.isConnected()

        self._fHasTweaks = False

        tweakPlug = depNodeFn.findPlug("pnts")

        if not tweakPlug.isNull():
            if not tweakPlug.isArray():
                raise Exception(u"tweakPlug.isArray() -- tweakPlug is not an array plug");

            numElements = tweakPlug.numElements()

            for i in range(numElements):
                tweak = tweakPlug.elementByPhysicalIndex(i)
                if not float3PlugValueIsZero(tweak):
                    self._fHasTweaks = True
                    break

        self._fHasRecordHistory = cmds.constructionHistory(q=True, tgl=True)

    def __createModifierNode(self, modifierNode):
        if self._fModifierNodeTypeInitialized or self._fModifierNodeNameInitialized:
            if self._fModifierNodeTypeInitialized:
                modifierNode.assign(self._fDGModifier.createNode(self._fModifierNodeType))
            elif self._fModifierNodeNameInitialized:
                modifierNode.assign(self._fDGModifier.createNode(self._fModifierNodeName))

            depNodeFn = om.MFnDependencyNode(modifierNode)

            inMeshAttr = depNodeFn.attribute("inMesh")
            outMeshAttr = depNodeFn.attribute("outMesh")

            if inMeshAttr.isNull() or outMeshAttr.isNull():
                raise Exception(
                    u"Invalid Modifier Node: inMesh and outMesh attributes are required."
                )

    def __processMeshNode(self, data):
        # type: (polyModifierCmd.modifyPolyData) -> None
        data.meshNodeShape = self._fDagPath.node()
        dagNodeFn = om.MFnDagNode(data.meshNodeShape)

        if not 0 < dagNodeFn.parentCount():
            raise Exception(u"0 < dagNodeFn.parentCount() -- meshNodeshape has no parent transform")

        data.meshNodeTransform = dagNodeFn.parent(0)

        data.meshNodeDestPlug = dagNodeFn.findPlug("inMesh")
        data.meshNodeDestAttr = data.meshNodeDestPlug.attribute()

    def __processUpstreamNode(self, data):
        # type: (polyModifierCmd.modifyPolyData) -> None

        if self._fHasHistory:

            tempPlugArray = om.MPlugArray()

            data.meshNodeDestPlug.connectedTo(tempPlugArray, True, False)

            if not tempPlugArray.length() == 1:
                raise Exception(
                    u"0 < dagNodeFn.parentCount() -- meshNodeshape has no parent transform"
                )

            data.upstreamNodeSrcPlug = tempPlugArray[0]
            data.upstreamNodeShape = data.upstreamNodeSrcPlug.node()

            # depNodeFn.setObject(data.upstreamNodeShape)
            # depNodeFn.setObject(data.upstreamNodeShape)
            # todo check unnecessary?

            data.upstreamNodeSrcAttr = data.upstreamNodeSrcPlug.attribute()

            self._fDGModifier.disconnect(data.upstreamNodeSrcPlug, data.meshNodeDestPlug)

        else:
            self._create_duplicate_mesh_source(data)
            # dagNodeFn = om.MFnDagNode(data.meshNodeShape)
            # data.upstreamNodeTransform = dagNodeFn.duplicate(False, False)
            # dagNodeFn.setObject(data.upstreamNodeTransform)
            #
            # if not 0 < dagNodeFn.childCount():
            #     raise Exception(
            #         u"0 < dagNodeFn.childCount() -- Duplicate meshNode transform has no shape."
            #     )
            #
            # data.upstreamNodeShape = dagNodeFn.child(0)
            #
            # self._fDagModifier.reparentNode(data.upstreamNodeShape, data.meshNodeTransform)
            # self._fDagModifier.doIt()
            #
            # dagNodeFn.setObject(data.upstreamNodeShape)
            # dagNodeFn.setIntermediateObject(True)
            #
            # data.upstreamNodeSrcAttr = dagNodeFn.attribute("outMesh")
            # data.upstreamNodeSrcPlug = dagNodeFn.findPlug("outMesh")
            #
            # self._fDagModifier.deleteNode(data.upstreamNodeTransform)
            # self._fDagModifier.doIt()
            #
            # dagNodeFn.getPath(self._fDuplicateDagPath)

    def _create_duplicate_mesh_source(self, data, redo_data=None):
        # type: (polyModifierCmd._modifyPolyData, _MANUAL_REDO_DATA) -> om.MFnDagNode
        print("creating mesh")

        dep_fn = om.MFnDependencyNode()

        dag_fn = om.MFnDagNode(data.meshNodeShape)
        data.upstreamNodeTransform = dag_fn.duplicate(False, False)
        dag_fn.setObject(data.upstreamNodeTransform)

        if not 0 < dag_fn.childCount():
            raise Exception(
                u"0 < dagNodeFn.childCount() -- Duplicate meshNode transform has no shape."
            )

        data.upstreamNodeShape = dag_fn.child(0)

        if redo_data:
            pass
            # dag_fn.setObject(data.meshNodeTransform)
            # dag_fn.addChild(data.upstreamNodeShape)
        else:
            self._fDagModifier.reparentNode(data.upstreamNodeShape, data.meshNodeTransform)
            self._fDagModifier.doIt()

        dag_fn.setObject(data.upstreamNodeShape)
        # dag_fn.setIntermediateObject(True)

        if redo_data:
            trn_dag = om.MFnDagNode(dag_fn.parent(0))
            trn_dag.setName(redo_data.trn_name)
            dag_fn.setName(redo_data.shp_name)

        data.upstreamNodeSrcAttr = dag_fn.attribute("outMesh")
        data.upstreamNodeSrcPlug = dag_fn.findPlug("outMesh")

        if data:
            pass
            # om.MGlobal.deleteNode(data.upstreamNodeTransform)

        else:
            self._fDagModifier.deleteNode(data.upstreamNodeTransform)
            self._fDagModifier.doIt()

        dag_fn.getPath(self._fDuplicateDagPath)

        if redo_data:
            return trn_dag
        else:
            return None

    def __processModifierNode(self, modifierNode, data):
        depNodeFn = om.MFnDependencyNode(modifierNode)
        data.modifierNodeSrcAttr = depNodeFn.attribute("outMesh")
        data.modifierNodeDestAttr = depNodeFn.attribute("inMesh")

    def __clear_tweak_data(self):
        self._fTweakIndexArray.clear()
        self._fTweakVectorArray.clear()

    def __processTweaks(self, data):
        self.__clear_tweak_data()

        if self._fHasTweaks:
            depNodeFn = om.MFnDependencyNode()

            tweakData = om.MObject()
            tweakDataArray = om.MObjectArray()
            tweakVector = om.MFloatVector()

            tweakSrcConnectionCountArray = om.MIntArray()
            tweakSrcConnectionPlugArray = om.MPlugArray()
            tweakDstConnectionCountArray = om.MIntArray()
            tweakDstConnectionPlugArray = om.MPlugArray()

            tempPlugArray = om.MPlugArray()

            data.tweakNode = self._fDGModifier.createNode("polyTweak")

            depNodeFn.setObject(data.tweakNode)

            data.tweakNodeSrcAttr = depNodeFn.attribute("output")
            data.tweakNodeDestAttr = depNodeFn.attribute("inputPolymesh")
            tweakNodeTweakAttr = depNodeFn.attribute("tweak")

            depNodeFn.setObject(data.meshNodeShape)

            meshTweakPlug = depNodeFn.findPlug("pnts")

            if not meshTweakPlug.isArray():
                raise Exception(u"meshTweakPlug.isArray() -- meshTweakPlug is not an array plug")

            numElements = meshTweakPlug.numElements()

            for i in range(numElements):
                tweak = meshTweakPlug.elementByPhysicalIndex(i)

                if not tweak.isNull():
                    logicalIndex = tweak.logicalIndex()

                    tweakData.assign(tweak.asMObject())

                    tweakDataArray.append(tweakData)
                    getFloat3PlugValue(tweak, tweakVector)
                    self._fTweakIndexArray.append(logicalIndex)
                    self._fTweakVectorArray.append(tweakVector)

                    if not tweak.isCompound():
                        raise Exception(u"tweak.isCompound() -- Element tweak plug is not compound")

                    numChildren = tweak.numChildren()
                    for j in range(numChildren):
                        tweakChild = tweak.child(j)
                        if tweakChild.isConnected():

                            tempPlugArray.clear()
                            if tweakChild.connectedTo(tempPlugArray, False, True):
                                numSrcConnections = tempPlugArray.length()
                                tweakSrcConnectionCountArray.append(numSrcConnections)

                                for k in range(numSrcConnections):
                                    tweakSrcConnectionPlugArray.append(tempPlugArray[k])
                                    self._fDGModifier.disconnect(tweakChild, tempPlugArray[k])
                            else:
                                tweakSrcConnectionCountArray.append(0)

                            tempPlugArray.clear()

                            if tweakChild.connectedTo(tempPlugArray, True, False):
                                if not tempPlugArray.length() == 1:
                                    raise Exception(
                                        u"tempPlugArray.length() == 1 -- 0 or >1 connections on "
                                        u"tweakChild"
                                    )

                                tweakDstConnectionCountArray.append(1)
                                tweakDstConnectionPlugArray.append(tempPlugArray[0])
                                self._fDGModifier.disconnect(tempPlugArray[0], tweakChild)
                            else:
                                tweakDstConnectionCountArray.append(0)

                        else:
                            tweakSrcConnectionCountArray.append(0)
                            tweakDstConnectionCountArray.append(0)

            polyTweakPlug = om.MPlug(data.tweakNode, tweakNodeTweakAttr)
            numTweaks = self._fTweakIndexArray.length()
            srcOffset = 0
            dstOffset = 0

            for i in range(numTweaks):
                tweak = polyTweakPlug.elementByLogicalIndex(self._fTweakIndexArray[i])
                tweak.setMObject(tweakDataArray[i])

                if not tweak.isCompound():
                    raise Exception(u"tweak.isCompound() -- Element plug, 'tweak', is not compound")

                numChildren = tweak.numChildren()
                for j in range(numChildren):
                    tweakChild = tweak.child(j)

                    if 0 < tweakSrcConnectionCountArray[i * numChildren + j]:
                        for k in range(tweakSrcConnectionCountArray[i * numChildren + j]):
                            self._fDGModifier.connect(
                                tweakChild,
                                tweakSrcConnectionPlugArray[srcOffset]
                            )
                            srcOffset += 1

                    if 0 < tweakDstConnectionCountArray[i * numChildren + j]:
                        self._fDGModifier.connect(
                            tweakDstConnectionPlugArray[dstOffset],
                            tweakChild
                        )
                        dstOffset += 1

            # numDataFn = om.MFnNumericData()
            # numDataFn.create(om.MFnNumericData.k3Float)
            # numDataFn.setData3Float(0.0, 0.0, 0.0)
            # nullVector = numDataFn.object()
            #
            # for i in range(numTweaks):
            #     tweak = meshTweakPlug.elementByLogicalIndex(self._fTweakIndexArray[i])
            #     tweak.setMObject(nullVector)

            self.__reset_pnts(meshTweakPlug)

            if not self._fHasHistory and self._fHasRecordHistory:
                depNodeFn.setObject(data.upstreamNodeShape)
                upstreamTweakPlug = depNodeFn.findPlug("pnts")

                # if not upstreamTweakPlug.isNull():
                self.__reset_pnts(upstreamTweakPlug)

                # # for i in range(numTweaks):
                # #     tweak = meshTweakPlug.elementByLogicalIndex(self._fTweakIndexArray[i])
                # #     tweak.setMObject(nullVector)
                #
                # # reset upstream tweak plug instead
                # # numElements = upstreamTweakPlug.numElements()
                # # for i in range(numElements):
                # #     tweak = upstreamTweakPlug.elementByPhysicalIndex(i)
                # #     tweak.setMObject(nullVector)
                #
                # for i in range(numTweaks):
                #     tweak = upstreamTweakPlug.elementByLogicalIndex(self._fTweakIndexArray[i])
                #     tweak.setMObject(nullVector)

    def __reset_pnts(self, tweak_plug):
        # depNodeFn = om.MFnDependencyNode()
        # depNodeFn.setObject(shape_obj)
        # tweak_plug = depNodeFn.findPlug("pnts")
        numTweaks = self._fTweakIndexArray.length()
        # numTweaks = tweak_plug.numElements()

        # numDataFn = om.MFnNumericData()
        # numDataFn.create(om.MFnNumericData.k3Float)
        # numDataFn.setData3Float(0.0, 0.0, 0.0)
        # nullVector = numDataFn.object()

        # if not tweak_plug.isNull():
        #     for i in range(numTweaks):
        #         tweak = tweak_plug.elementByPhysicalIndex(self._fTweakIndexArray[i])
        #         tweak.setMObject(self.NULL_VECTOR)

        if not tweak_plug.isNull():
            for i in range(numTweaks):
                tweak = tweak_plug.elementByPhysicalIndex(i)
                tweak.setMObject(self.NULL_VECTOR)

    def __connectNodes(self, modifierNode):
        data = self._modifyPolyData()
        self.__processMeshNode(data)
        self.__processUpstreamNode(data)
        self.__processModifierNode(modifierNode, data)
        self.__processTweaks(data)

        data.debug(modifierNode)

        if self._fHasTweaks:
            tweakDestPlug = om.MPlug(data.tweakNode, data.tweakNodeDestAttr)
            self._fDGModifier.connect(data.upstreamNodeSrcPlug, tweakDestPlug)

            tweakSrcPlug = om.MPlug(data.tweakNode, data.tweakNodeSrcAttr)
            modifierDestPlug = om.MPlug(modifierNode, data.modifierNodeDestAttr)
            self._fDGModifier.connect(tweakSrcPlug, modifierDestPlug)
        else:
            modifierDestPlug = om.MPlug(modifierNode, data.modifierNodeDestAttr)
            self._fDGModifier.connect(data.upstreamNodeSrcPlug, modifierDestPlug)

        modifierSrcPlug = om.MPlug(modifierNode, data.modifierNodeSrcAttr)
        meshDestAttr = om.MPlug(data.meshNodeShape, data.meshNodeDestAttr)
        #
        self._fDGModifier.connect(modifierSrcPlug, meshDestAttr)

        self._fDGModifier.doIt()

    # caching method

    def __cacheMeshData(self):
        depNodeFn = om.MFnDependencyNode()
        dagNodeFn = om.MFnDagNode()

        meshNode = self._fDagPath.node()

        dagNodeFn.setObject(meshNode)
        dupMeshNode = dagNodeFn.duplicate()

        dupMeshDagPath = om.MDagPath()
        om.MDagPath.getAPathTo(dupMeshNode, dupMeshDagPath)
        dupMeshDagPath.extendToShape()

        depNodeFn.setObject(dupMeshDagPath.node())
        dupMeshNodeOutMeshPlug = depNodeFn.findPlug("outMesh")

        self._fMeshData = dupMeshNodeOutMeshPlug.asMObject()

        om.MGlobal.deleteNode(dupMeshNode)

    def __cacheMeshTweaks(self):
        self._fTweakIndexArray.clear()
        self._fTweakVectorArray.clear()

        if self._fHasTweaks:
            meshNode = self._fDagPath.node()

            depNodeFn = om.MFnDependencyNode(meshNode)
            meshTweakPlug = depNodeFn.findPlug("pnts")
            tweakVector = om.MFloatVector()

            if not meshTweakPlug.isArray():
                raise Exception(
                    u"meshTweakPlug.isArray() -- meshTweakPlug is not an array plug")

            numElements = meshTweakPlug.numElements()
            for i in range(numElements):
                tweak = meshTweakPlug.elementByPhysicalIndex(i)
                if not tweak.isNull():
                    logicalIndex = tweak.logicalIndex()
                    self._fTweakIndexArray.append(logicalIndex)

                    getFloat3PlugValue(tweak, tweakVector)
                    self._fTweakVectorArray.append(tweakVector)

    # undo

    def __undoCacheMesh(self):
        depNodeFn = om.MFnDependencyNode()

        meshNodeShape = self._fDagPath.node()
        dupMeshNodeShape = self._fDuplicateDagPath.node()

        depNodeFn.setObject(meshNodeShape)
        meshNodeName = depNodeFn.name()
        meshNodeDestPlug = depNodeFn.findPlug("inMesh")
        meshNodeOutMeshPlug = depNodeFn.findPlug("outMesh")

        depNodeFn.setObject(dupMeshNodeShape)
        dupMeshNodeSrcPlug = depNodeFn.findPlug("outMesh")

        if self._fHasTweaks:
            dgModifier = om.MDGModifier()
            dgModifier.connect(dupMeshNodeSrcPlug, meshNodeDestPlug)
            dgModifier.doIt()

            cmd = "dgeval {0}.inMesh".format(meshNodeName)
            om.MGlobal.executeCommand(cmd, False, False)
            dgModifier.undoIt()

            # attempt to delete dup mesh node here?

        else:
            meshData = om.MObject(dupMeshNodeSrcPlug.asMObject())
            meshNodeOutMeshPlug.setMObject(meshData)

    def __undoTweakProcessing(self):

        if not self._fHasHistory:
            # skip tweak processing if node had no history
            return

        if self._fHasTweaks:
            pass

            tweakData = om.MObject()

            meshNodeShape = self._fDagPath.node()
            depNodeFn = om.MFnDependencyNode(meshNodeShape)
            meshTweakPlug = depNodeFn.findPlug("pnts")

            if not meshTweakPlug.isArray():
                raise Exception(u"meshTweakPlug.isArray() -- meshTweakPlug is not an array plug")

            numElements = self._fTweakIndexArray.length()

            for i in range(numElements):
                tweak = meshTweakPlug.elementByLogicalIndex(self._fTweakIndexArray[i])
                # assign float to tweakData and set it to tweak
                getFloat3asMObject(self._fTweakVectorArray[i], tweakData)
                tweak.setMObject(tweakData)

    def __undoDirectModifier(self):
        depNodeFn = om.MFnDependencyNode()
        dagNodeFn = om.MFnDagNode()

        meshNode = self._fDagPath.node()
        depNodeFn.setObject(meshNode)

        if self._fHasTweaks:
            depNodeFn.setObject(meshNode)
            meshNodeInMeshPlug = depNodeFn.findPlug("inMesh")
            meshNodeName = depNodeFn.name()

            dagNodeFn.setObject(meshNode)
            dupMeshNode = dagNodeFn.duplicate()

            dupMeshDagPath = om.MDagPath()
            om.MDagPath.getAPathTo(dupMeshNode, dupMeshDagPath)
            dupMeshDagPath.extendToShape()

            depNodeFn.setObject(dupMeshDagPath.node())
            dupMeshNodeOutMeshPlug = depNodeFn.findPlug("outMesh")
            dupMeshNodeOutMeshPlug.setMObject(self._fMeshData)

            dgModifier = om.MDGModifier()
            dgModifier.connect(dupMeshNodeOutMeshPlug, meshNodeInMeshPlug)

            cmd = """dgeval {0}.inMesh""".format(meshNodeName)
            om.MGlobal.executeCommand(cmd, False, False)

            dgModifier.undoIt()
            om.MGlobal.deleteNode(dupMeshNode)

            self.__undoTweakProcessing()

        else:
            depNodeFn.setObject(meshNode)
            dupMeshNodeOutMeshPlug = depNodeFn.findPlug("outMesh")
            dupMeshNodeOutMeshPlug.setMObject(self._fMeshData)

    # endregion


# utility methods

def getFloat3PlugValue(plug, value):
    # type: (om.MPlug, om.MFloatVector) -> None
    u"""assign plug value by reference to mfloatvector

    plug must be compound (mvector)
    """

    value.x = plug.child(0).asFloat()
    value.y = plug.child(1).asFloat()
    value.z = plug.child(2).asFloat()


def float3PlugValueIsZero(plug):
    # type: (om.MPlug) -> None
    u"""assign plug value by reference to mfloatvector

    plug must be compound (mvector)
    """

    if plug.child(0).asFloat() == 0.0 and \
            plug.child(1).asFloat() == 0.0 and \
            plug.child(2).asFloat() == 0.0:
        return True
    else:
        return False


def getFloat3asMObject(value, tweakData):
    # type: (om.MObject) -> None
    u"""assign value to tweakData"""
    numDataFn = om.MFnNumericData()
    numDataFn.create(om.MFnNumericData.k3Float)
    numDataFn.setData3Float(value.x, value.y, value.z)
    tweakData.assign(numDataFn.object())
