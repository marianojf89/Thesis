from rdflib import Graph, Namespace, URIRef, Literal, BNode
from typing import List, Dict
from rdflib.collection import Collection
import pprint

# Class which describes the functions related to a shape integration object.
class ShapeIntegration():
    def __init__(self, inputShapes: Graph, currentIrm: str):
        self.shaclNS = Namespace('http://www.w3.org/ns/shacl#')
        self.rdfSyntax = Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        self.targetDeclarationNS = [self.shaclNS.targetClass, self.shaclNS.targetNode, self.shaclNS.targetSubjectsOf, self.shaclNS.targetObjectsOf]
        self.propertyPathNS = [self.shaclNS.path]
        self.inputShapes = inputShapes
        self.currentIrm = currentIrm
        self.SHACL = Graph().parse(currentIrm, format='turtle') # Initialize a graph with the shapes that were already loaded in the currentIRM version
        self.integrated_identifier = []
        self.compoundNodeKindValue = [self.shaclNS.BlankNodeOrIRI, self.shaclNS.BlankNodeOrLiteral, self.shaclNS.IRIOrLiteral]

    # Get the simple targets (NodeShapeIRI, targetIRI) that are found in the shape graphs.
    def getNodeShapesSimpleTargets(self, shape: Graph):
        NodeShapesTargetID = []
        for s, p, o in shape.triples((None, self.rdfSyntax.type, self.shaclNS.NodeShape)):
            nodeShapeIRI = s
            isSimpleTarget = True
            for s2, p2, o2 in shape.triples((nodeShapeIRI, None, None)):
                if p2 == self.shaclNS["property"]:
                    isSimpleTarget = False
            if isSimpleTarget == True:
                for s3, p3, o3 in shape.triples((s, None, None)):
                    if p3 in self.targetDeclarationNS:
                        nodeShapeFocusNode =  o3
                        NodeShapesTargetID.append([nodeShapeIRI,nodeShapeFocusNode])
        return NodeShapesTargetID
    
    # Get the compound targets (NodeShapeIRI, targetIRI, pathValueIRI) that are found in the shape graphs.
    def getCompoundFocusNodePropertyTargets(self, shape: Graph):
        CompoundShapesTargetID = []
        for s, p, o in shape.triples((None, self.rdfSyntax.type, self.shaclNS.NodeShape)):
            nodeShapeIRI = s
            isCompoundTarget = False
            propertyBlankNode = []
            for s2, p2, o2 in shape.triples((nodeShapeIRI, None, None)):
                if p2 == self.shaclNS["property"]:
                    isCompoundTarget = True
                    propertyBlankNode.append(o2)
                elif p2 in self.targetDeclarationNS:
                    nodeShapeFocusNode = o2
            if isCompoundTarget == True:
                for blankNodeID in propertyBlankNode:
                    for s3, p3, o3 in shape.triples((blankNodeID, None, None)):
                        if p3 in self.propertyPathNS:
                            pathID = o3
                            CompoundShapesTargetID.append([nodeShapeIRI,nodeShapeFocusNode,pathID])
        return CompoundShapesTargetID
    
    # This function receives two shape graphs, one that is part of the integration and another that is the outcome, and a list of simple shapes [[nodeShapeIRI, targetIRI]] which don't have an equivalence. Furthermore, the objective is to insert these in the updated version of the IRM.
    def insertSimpleTargetsWithoutEquivalence(self, shapeGraph, updatedIRM: Graph, targetsWithoutEq : List):
        for inputShape in targetsWithoutEq:
            targetIRI = ''
            nodeShapeIRI = inputShape[0]
            nodeShapeTargetIRI = inputShape[1]
            targetIRI = nodeShapeTargetIRI + '_sup'
            for s, p, o in shapeGraph.triples((nodeShapeIRI, None, None)):
                updatedIRM.add((targetIRI,p,o))

    # This function receives two shape graphs, one that is the input shape graph and another that is the outcome, and a list of compound shapes [[nodeShapeIRI, targetIRI, pathValueIRI]] which don't have an equivalence. Furthermore, the objective is to insert these in the updated version of the IRM.
    def insertCompoundInputTargetsWithoutEquivalence(self, shapeGraph, updatedIRM: Graph, targetsWithoutEq : List):
        for inputShape in targetsWithoutEq:
            nodeShapeIRI = inputShape[0]
            targetIRI = inputShape[1]
            pathValueIRI = inputShape[2]
            insertTriple = False
            focusNode = ''
            PathValue = ''
            indexFocusNode = targetIRI.rfind('/')
            focusNode = targetIRI[indexFocusNode + 1:]
            indexPathValue = pathValueIRI.rfind('/')
            PathValue = pathValueIRI[indexPathValue + 1:]
            groupID = focusNode + '_' + PathValue
            prefixIndex = nodeShapeIRI.rfind('/')
            prefixValue = nodeShapeIRI[:prefixIndex + 1]
            nodeShapeIrmIRI = prefixValue + groupID + '_sup'
            groupIdIRI = prefixValue + groupID
            for s, p, o in shapeGraph.triples((nodeShapeIRI, None, None)):
                if p != self.shaclNS["property"]:
                    updatedIRM.add((URIRef(nodeShapeIrmIRI),p,o))
                else:
                    for s1, p1, o1 in shapeGraph.triples((o, None, None)):
                        if p1 in self.propertyPathNS and o1 == pathValueIRI:
                            insertTriple = True
                            updatedIRM.add((s1,self.shaclNS.group,URIRef(groupIdIRI)))
                            updatedIRM.add((URIRef(groupIdIRI), self.rdfSyntax.type, self.shaclNS.PropertyGroup))
                            updatedIRM.add((URIRef(nodeShapeIrmIRI),self.shaclNS["property"],s1))
                if insertTriple == True:
                    for s2, p2, o2 in shapeGraph.triples((s1, None, None)):
                        if p2 != self.shaclNS['in'] and p2 != self.shaclNS.hasValue and p2 != self.shaclNS['or']:
                            updatedIRM.add((s2,p2,o2))
                        elif p2 == self.shaclNS['in'] or p2 == self.shaclNS.hasValue:
                            # Get the content of the RDF lists that contain the values of sh:in
                            inputRDFlist = self.getElementsOfRDFlist(self.inputShapes, o2)
                            values = sorted(inputRDFlist)
                            list_node = self.createRDFListFromList(values, updatedIRM)
                            updatedIRM.add((s2, p2, list_node))
                        elif p2 == self.shaclNS['or']:
                            # Get the content of the RDF lists that contain the values of sh:or [contraintType,constraintValue]
                            inputRDFlist = self.getElementsOfRDFlistOr(self.inputShapes, o2) 
                            list_node_superShapeOr = self.createRDFListFromListOr(inputRDFlist, updatedIRM) 
                            updatedIRM.add((s2, p2, list_node_superShapeOr))
                    break

            
    # This function receives two shape graphs, one that is part of the integration (IRM) and another that is the outcome, and a list of compound shapes [[nodeShapeIRI, targetIRI, pathValueIRI]] which don't have an equivalence. Furthermore, the objective is to insert these in the updated version of the IRM.
    def insertCompoundIRMTargetsWithoutEquivalence(self, shapeGraph, updatedIRM: Graph, targetsWithoutEq : List):
        for inputShape in targetsWithoutEq:
            nodeShapeIRI = inputShape[0]
            pathValueIRI = inputShape[2]
            insertTriple = False
            for s, p, o in shapeGraph.triples((nodeShapeIRI, None, None)):
                if p != self.shaclNS["property"]:
                    updatedIRM.add((s,p,o))
                else:
                    for s1, p1, o1 in shapeGraph.triples((o, None, None)):
                        if p1 in self.propertyPathNS and o1 == pathValueIRI:
                            insertTriple = True
                            updatedIRM.add((nodeShapeIRI,self.shaclNS["property"],s1))
                if insertTriple == True:
                    for s2, p2, o2 in shapeGraph.triples((s1, None, None)):
                        if p2 != self.shaclNS['in'] and p2 != self.shaclNS.hasValue and p2 != self.shaclNS['or']:
                            updatedIRM.add((s2,p2,o2))
                        elif p2 == self.shaclNS['in'] or p2 == self.shaclNS.hasValue:
                            # Get the content of the RDF lists that contain the values of sh:in
                            inputRDFlist = self.getElementsOfRDFlist(self.SHACL, o2)
                            values = sorted(inputRDFlist)
                            list_node = self.createRDFListFromList(values, updatedIRM)
                            updatedIRM.add((s2, p2, list_node))
                        elif p2 == self.shaclNS['or']:
                            # Get the content of the RDF lists that contain the values of sh:or [contraintType,constraintValue]
                            inputRDFlist = self.getElementsOfRDFlistOr(self.SHACL, o2) 
                            list_node_superShapeOr = self.createRDFListFromListOr(inputRDFlist, updatedIRM) 
                            updatedIRM.add((s2, p2, list_node_superShapeOr))
                    break

    # This function looks for the simple shapes that were found as equivalent (from the IRM and the input), looks for their respective constraints and call the procedure integrateSimpleShapes which will integrate the shapes and insert them in the updated IRM graph
    def integrateSimpleShapesWithEquivalence(self, inputShapeGraph, currentIRMGraph, updatedIRM: Graph, IrmSimpleShapesWithEquivalence, InputGraphSimpleShapesWithEquivalence : List):
        # Treat each shape from the IRM which are simple shapes and had an equivalence [[nodeShapeIRI, targetIRI]]
        for IRMshape in IrmSimpleShapesWithEquivalence:
            irmShapeIRI = IRMshape[0]
            irmShapeTargetIRI = IRMshape[1]
            inputConstraints = []
            irmConstraints = []
            # Get the constraints of this specific IRM shape
            for s1,p1,o1 in currentIRMGraph.triples((irmShapeIRI, None, None)):
                if p1 != self.rdfSyntax.type and p1 not in self.targetDeclarationNS and p1 != self.shaclNS["property"]: # The latter condition is for treating the compound nodeShapes
                    irmConstraints.append([p1,o1])
            # Look for the equivalent simple shape found in the input shape graph
            for inputGraphShape in InputGraphSimpleShapesWithEquivalence:
                # If the target IRIs are the same, this means that I found the equivalent shape from the input shape graph
                if irmShapeTargetIRI == inputGraphShape[1]:
                    # Get the constraints of the equivalent simple shape from the input shape graph
                    for s,p,o in inputShapeGraph.triples((inputGraphShape[0], None, None)):
                        if p != self.rdfSyntax.type and p not in self.targetDeclarationNS and p != self.shaclNS["property"]: # The latter condition is for treating the compound nodeShapes:
                            inputConstraints.append([p,o])
                    # Compare constraint per constraint and integrate
                    self.integrateSimpleShapes(updatedIRM, irmShapeIRI, irmShapeTargetIRI, inputConstraints, irmConstraints)

    # This procedure receives the constraints from two equivalent simple shapes, integrates them and then inserts the outcome in the updated IRM graph
    def integrateSimpleShapes(self, updatedIRM: Graph, irmShapeIRI, irmShapeTargetIRI: str, inputConstraints, irmConstraints: List):
        # Create a temporal graph for the temporal integration of the shapes
        temporalOutcome = Graph()
        temporalOutcome.add((irmShapeIRI, self.rdfSyntax.type, self.shaclNS.NodeShape))
        temporalOutcome.add((irmShapeIRI, self.shaclNS.targetClass, irmShapeTargetIRI))
        #temporalOutcome.add((irmShapeIRI, self.shaclNS.deactivated, True))
        # For each constraint of the input, save the constraint type, the constraint value and compare it against all the constraints of the equivalent IRM shape
        for inputConstraint in inputConstraints:
            inputConstraintType = inputConstraint[0]
            inputConstraintValue = inputConstraint[1]
            for irmConstraint in irmConstraints:
                irmConstraintType = irmConstraint[0]
                irmConstraintValue = irmConstraint[1]
                # Scenario 1 = C_IN1x and C_IN2x are the same type of constraint and their value spaces are contained in each other, meaning that C_IN1x is contained in C_IN2x and vice-versa (C_IN1x = C_IN2x).
                if inputConstraintType == irmConstraintType and inputConstraintValue == irmConstraintValue:
                    temporalOutcome.add((irmShapeIRI, irmConstraintType, irmConstraintValue))
        # Insert the temporal shapes to the updated IRM graph
        for triple in temporalOutcome:
            updatedIRM.add(triple)
                    
    # This procedure receives the inputShapeGraph, currentIRMGraph and updatedIRM graphs, the lists IrmCompoundTargetWithEquivalence and InputCompoundTargetWithEquivalence with the compound shapes that had an equivalence
    def integrateCompoundShapesWithEquivalence(self, inputShapeGraph, currentIRMGraph, updatedIRM: Graph, IrmCompoundTargetWithEquivalence, InputCompoundTargetWithEquivalence : List):
        # Integrate first the related node shapes
        self.integrateSimpleShapesWithEquivalence(inputShapeGraph, currentIRMGraph, updatedIRM, IrmCompoundTargetWithEquivalence, InputCompoundTargetWithEquivalence)
        # Treat each shape from the IRM which are compound shapes and had an equivalence [[nodeShapeIRI, targetIRI, pathValueIRI]]
        for IRMshape in IrmCompoundTargetWithEquivalence:
            irmShapeIRI = IRMshape[0]
            irmShapeTargetIRI = IRMshape[1]
            irmShapePathValueIRI = IRMshape[2]
            inputPropertyConstraints = []
            irmPropertyConstraints = []
            # Get the property constraints of this specific IRM shape
            for s1,p1,o1 in currentIRMGraph.triples((irmShapeIRI, self.shaclNS["property"], None)):
                for s6,p6,o6 in currentIRMGraph.triples((o1,self.propertyPathNS[0], None)):
                    if o6 == irmShapePathValueIRI:
                        for s2,p2,o2 in currentIRMGraph.triples((s6, None, None)):
                            blankNodePropertyIRI = s6
                            if p2 not in self.propertyPathNS and p2 != self.shaclNS.group:
                                irmPropertyConstraints.append([p2,o2])
                            elif p2 ==  self.shaclNS.group:
                                groupID = o2
            # Look for the equivalent compound shape found in the input shape graph
            for inputGraphShape in InputCompoundTargetWithEquivalence:
                # If the target IRIs and the pathValue IRIs are the same, this means that I found the equivalent shape from the input shape graph
                if irmShapeTargetIRI == inputGraphShape[1] and irmShapePathValueIRI == inputGraphShape[2]:
                    # Get the constraints of the equivalent compound shape from the input shape graph
                    for s3,p3,o3 in inputShapeGraph.triples((inputGraphShape[0], self.shaclNS["property"], None)):
                        for s4,p4,o4 in inputShapeGraph.triples((o3, self.propertyPathNS[0], None)):
                            if o4 == inputGraphShape[2]:
                                for s5,p5,o5 in inputShapeGraph.triples((s4,None,None)):
                                    if p5 not in self.propertyPathNS:
                                        inputPropertyConstraints.append([p5,o5])
            ## Compare constraint per constraint and integrate
            self.integrateCompoundShapes(updatedIRM, inputShapeGraph, currentIRMGraph, irmShapeIRI, irmShapeTargetIRI, irmShapePathValueIRI, blankNodePropertyIRI, groupID, inputPropertyConstraints, irmPropertyConstraints)

    # This procedure receives the constraints from two equivalent compound shapes, integrates them and then inserts the outcome in the updated IRM graph
    def integrateCompoundShapes(self, updatedIRM, inputGraph, irmGraph: Graph, irmShapeIRI, irmShapeTargetIRI, irmShapePathValueIRI, blankNodePropertyIRI, groupID: str, inputPropertyConstraints, irmPropertyConstraints: List):
        # Create a temporal graph for the temporal integration of the shapes
        temporalOutcome = Graph()
        temporalOutcome.add((irmShapeIRI, self.shaclNS["property"], blankNodePropertyIRI))
        temporalOutcome.add((blankNodePropertyIRI, self.propertyPathNS[0], irmShapePathValueIRI))
        temporalOutcome.add((blankNodePropertyIRI, self.shaclNS.group, groupID))
        temporalOutcome.add((groupID, self.rdfSyntax.type, self.shaclNS.PropertyGroup))
        nodeShapeProperties = []
        # Get the node shape triples
        for s,p,o in updatedIRM.triples((irmShapeIRI,None,None)):
            if (p != self.shaclNS.type and p not in self.targetDeclarationNS and p != self.shaclNS["property"]):
                nodeShapeProperties.append([p,o])
        # Create a copy of the constraints from CIN2 which is used for checking if at the end of the comparison, there exist a CIN2x which didn't have any conflict (and so it must be added at the end).
        irmConstraintWithoutConflict = irmPropertyConstraints
        # First set of integrations  
        self.resolveConflictsAndIntegrate(inputPropertyConstraints, irmPropertyConstraints, nodeShapeProperties, irmConstraintWithoutConflict, temporalOutcome, inputGraph, irmGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)
        # Get the constraints of the new super shape of the temporal structure
        irmPropertyConstraintsUpdatedSuperShape = []
        for s1,p1,o1 in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
            if p1 not in self.propertyPathNS and p1 != self.shaclNS.group:
                irmPropertyConstraintsUpdatedSuperShape.append([p1,o1])
        # Scenario 6 - Integrations of the IRM constraints (C_IN2x) which didn't have any conflict with any constraint C_IN1x.
        if len(irmConstraintWithoutConflict) > 0:
            #print(irmConstraintWithoutConflict)
            #print(irmPropertyConstraintsUpdatedSuperShape)
            self.resolveConflictsAndIntegrate(irmConstraintWithoutConflict, irmPropertyConstraintsUpdatedSuperShape, nodeShapeProperties, irmConstraintWithoutConflict, temporalOutcome, irmGraph, inputGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)
        # Insert the temporal shapes to the updated IRM graph
        for triple in temporalOutcome:
            updatedIRM.add(triple)


    # This procedure receives two sets of constraints and integrates them into the temporalOutcome graph. In addition, if there is a constraint from the IRM shape which didn't have any conflict, this is saved in the list irmConstraintWithoutConflict.
    def resolveConflictsAndIntegrate(self, inputPropertyConstraints, irmPropertyConstraints, nodeShapeProperties, irmConstraintWithoutConflict: list, temporalOutcome, inputGraph, irmGraph: Graph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI: str):
        # For each constraint of the input, save the constraint type, the constraint value and compare it against all the constraints of the equivalent IRM shape
        for inputConstraint in inputPropertyConstraints:
            inputConstraintType = inputConstraint[0]
            inputConstraintValue = inputConstraint[1]
            inputConstraintScenario3 = True
            inputConstraintConflictCounter = 0
            for irmConstraint in irmPropertyConstraints:
                irmConstraintType = irmConstraint[0]
                irmConstraintValue = irmConstraint[1]
                irmFoundConstraint = False
                temporalSuperShapeConstraints = []
                temporalSubShapes = []
                # Get the property constraints of the temporal super shape (if it exists and has property constraints)
                for s,p,o in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                    if p != self.propertyPathNS[0] and p != self.shaclNS.group:
                        temporalSuperShapeConstraints.append([p,o])
                # Retrieve the existing nodeShapes of the structure and their sh:property blankNodes (apart from the super shape, since it's already accessible)
                for s,p,o in temporalOutcome.triples((None, self.rdfSyntax.type, self.shaclNS.NodeShape)):
                    for s1,p1,o1 in temporalOutcome.triples((s, self.shaclNS["property"], None)): 
                        if o1 != blankNodePropertyIRI:
                            temporalSubShapes.append([s,o1])
                # Scenario 1 = C_IN1x and C_IN2x are the same type of constraint and their value spaces are contained in each other, meaning that C_IN1x is contained in C_IN2x and vice-versa (C_IN1x = C_IN2x).
                if inputConstraintType == irmConstraintType and inputConstraintValue == irmConstraintValue:
                    temporalOutcome.add((blankNodePropertyIRI, irmConstraintType, irmConstraintValue))
                    # Temporal structure with multiple shapes
                    if len(temporalSubShapes) > 0:
                        for blankNodeSubShape in temporalSubShapes:
                            temporalOutcome.add((blankNodeSubShape[1], irmConstraintType, irmConstraintValue))
                    inputConstraintScenario3 = False
                    irmFoundConstraint = True
                    inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                # Other scenarios in which the constraints types are the same but their values are different
                elif inputConstraintType == irmConstraintType and inputConstraintValue != irmConstraintValue:
                    # nodeKind constraint
                    if inputConstraintType == self.shaclNS.nodeKind:
                        if inputConstraintConflictCounter == 0:
                            # Scenario 2-b (nodeKind) = C_IN1x and C_IN2x are the same type of constraint C_IN1x not_contained_in C_IN2x, C_IN2x not_contained_in C_IN1x and there's no super constraint value C3 between the predefined values for this specific type of SHACL constraint
                            if inputConstraintValue in self.compoundNodeKindValue and  irmConstraintValue in self.compoundNodeKindValue:
                                # Add a super shape with an sh:or linking both constraints
                                orBlankNode = BNode()
                                c1BlankNode = BNode()
                                c2BlankNode = BNode()
                                temporalOutcome.add((c1BlankNode, inputConstraintType, inputConstraintValue))
                                temporalOutcome.add((c2BlankNode, irmConstraintType, irmConstraintValue))
                                Collection(temporalOutcome, orBlankNode, [c1BlankNode, c2BlankNode])
                                temporalOutcome.add((blankNodePropertyIRI, self.shaclNS["or"], orBlankNode))
                                # There are no temporal shapes
                                if len(temporalSuperShapeConstraints) == 0:
                                    self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties)
                                    self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties)
                                # Scenario in which the temporal structure has already one super shape
                                elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) == 0:
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                # Scenario in which the temporal structure has already multiple shapes
                                elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) > 0:
                                    self.hierarchyReorganizationProcess(temporalOutcome, irmShapeIRI, irmConstraintType, irmConstraintValue, 1)
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                            # Scenario 4 (nodeKind) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN1x is_contained_in C_IN2x or the inverse. 
                            # Scenario 4-a (nodeKind) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN1x is_contained_in C_IN2x.
                            elif (inputConstraintValue not in self.compoundNodeKindValue and  irmConstraintValue in self.compoundNodeKindValue):
                                if (inputConstraintValue == self.shaclNS.IRI and (irmConstraintValue == self.shaclNS.IRIOrLiteral or irmConstraintValue == self.shaclNS.BlankNodeOrIRI)) or (inputConstraintValue == self.shaclNS.Literal and (irmConstraintValue == self.shaclNS.IRIOrLiteral or irmConstraintValue == self.shaclNS.BlankNodeOrLiteral)) or (inputConstraintValue == self.shaclNS.BlankNode and (irmConstraintValue == self.shaclNS.BlankNodeOrIRI or irmConstraintValue == self.shaclNS.BlankNodeOrLiteral)):
                                    self.scenario4aConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes) 
                            # Scenario 4-b (nodeKind) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN2x is_contained_in C_IN1x.
                            elif (inputConstraintValue in self.compoundNodeKindValue and  irmConstraintValue not in self.compoundNodeKindValue):
                                if (irmConstraintValue == self.shaclNS.IRI and (inputConstraintValue == self.shaclNS.IRIOrLiteral or inputConstraintValue == self.shaclNS.BlankNodeOrIRI)) or (irmConstraintValue == self.shaclNS.Literal and (inputConstraintValue == self.shaclNS.IRIOrLiteral or inputConstraintValue == self.shaclNS.BlankNodeOrLiteral)) or (irmConstraintValue == self.shaclNS.BlankNode and (inputConstraintValue == self.shaclNS.BlankNodeOrIRI or inputConstraintValue == self.shaclNS.BlankNodeOrLiteral)):
                                    self.scenario4bConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                            # Scenario 5 (nodeKind) = C_IN1x and C_IN2x are the same type of constraint and they are not compatible, meaning that they have values that target different spaces. Furthermore, there exists a super constraint value C3 between the predefined values for this specific SHACL constraint which contains C_IN1x and C_IN2x, such as C_IN1x is_contained_in C3 and C_IN2x is_contained_in C3
                            elif inputConstraintValue not in self.compoundNodeKindValue and irmConstraintValue not in self.compoundNodeKindValue and inputConstraintValue != irmConstraintValue:
                                if (inputConstraintValue == self.shaclNS.IRI and irmConstraintValue == self.shaclNS.Literal) or (inputConstraintValue == self.shaclNS.Literal and irmConstraintValue == self.shaclNS.IRI):
                                    superPredefinedConstraintValue = self.shaclNS.IRIOrLiteral
                                elif (inputConstraintValue == self.shaclNS.IRI and irmConstraintValue == self.shaclNS.BlankNode) or (inputConstraintValue == self.shaclNS.BlankNode and irmConstraintValue == self.shaclNS.IRI):
                                    superPredefinedConstraintValue = self.shaclNS.BlankNodeOrIRI
                                elif (inputConstraintValue == self.shaclNS.Literal and irmConstraintValue == self.shaclNS.BlankNode) or (inputConstraintValue == self.shaclNS.BlankNode and irmConstraintValue == self.shaclNS.Literal):
                                    superPredefinedConstraintValue = self.shaclNS.BlankNodeOrLiteral
                                #temporalOutcome.add((blankNodePropertyIRI, inputConstraintType, superPredefinedConstraintValue))
                                # There are no temporal shapes
                                if len(temporalSuperShapeConstraints) == 0:
                                    temporalOutcome.add((blankNodePropertyIRI, inputConstraintType, superPredefinedConstraintValue))
                                    self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties)
                                    self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties)
                                # Scenario in which the temporal structure has already one super shape
                                elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) == 0:
                                    temporalOutcome.add((blankNodePropertyIRI, inputConstraintType, superPredefinedConstraintValue))
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                # Scenario in which the temporal structure has already multiple shapes
                                elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) > 0:
                                    # C3 is added to all the sub shapes of the lower level (only if C3 doesn't have a conflict with any of the constraints of the specific subshape).
                                    # get the nodeShape IRIs and the associated blankNode of the lower existing level of the TEMPORAL_SHAPE structure.
                                    nodeShapeIRIsLowerLevel = []
                                    nodeShapeIRIsLowerLevel = self.getTemporalHierarchyLowerLevel(temporalSubShapes)
                                    # If there's no conflict of C3 with at least all the constraints of a shape of this level. In nodeShapeIRIsLowerLevel there is [[nodeShapeIRI,blankNodeID,HierarchyLevelInt]]
                                    for nodeShapeIRI in nodeShapeIRIsLowerLevel:
                                        conflictAgainstTemporalLowerSubShape = False
                                        lowerLevelShapePropertyConstraints = []
                                        for s,p,o in temporalOutcome.triples((nodeShapeIRI[1], None, None)): 
                                            if p != self.propertyPathNS[0] and p != self.shaclNS.group:
                                                lowerLevelShapePropertyConstraints.append([p,o])
                                        conflictAgainstTemporalLowerSubShape = self.isThereConflict(lowerLevelShapePropertyConstraints, inputConstraintType, superPredefinedConstraintValue) 
                                        # No conflict with a shape of the lower level, then C3 is added
                                        if conflictAgainstTemporalLowerSubShape == False:
                                            temporalOutcome.add((nodeShapeIRI[1], inputConstraintType, superPredefinedConstraintValue))
                                            # Each shape of the lower level of each branch that was updated is taken and divided into two new subshapes (copying every element except C3), where the first one will have C_IN1x and the second one C_IN2x.
                                            # How to put the correct hiearchyId, meaning sub{lowerLevel+1}_{lastBranch+1}
                                            followingHierarchyLevel = nodeShapeIRI[2] + 1
                                            lastSiblingOfLowerLevel = self.getTemporalHierarchyLevelLastSibling(temporalOutcome, followingHierarchyLevel, blankNodePropertyIRI)
                                            followingSibling1 = lastSiblingOfLowerLevel + 1
                                            followingSibling2 = lastSiblingOfLowerLevel + 2
                                            hierarchyId1 = '_sub' + str(followingHierarchyLevel) + '_' + str(followingSibling1)
                                            hierarchyId2 = '_sub' + str(followingHierarchyLevel) + '_' + str(followingSibling2)
                                            self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, hierarchyId1, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, nodeShapeIRI[0], nodeShapeProperties, lowerLevelShapePropertyConstraints)
                                            self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, hierarchyId2, irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, nodeShapeIRI[0], nodeShapeProperties, lowerLevelShapePropertyConstraints)
                        # C_IN1x WITH MULTIPLE CONFLICTS: C_IN2y is the constraint that is attempted to be added to the super shape of the TEMPORAL_SHAPE
                        elif inputConstraintConflictCounter > 0:
                            irmPropertyConstraintsUpdatedSuperShape = []
                            for s1,p1,o1 in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                                if p1 not in self.propertyPathNS and p1 != self.shaclNS.group:
                                    irmPropertyConstraintsUpdatedSuperShape.append([p1,o1])
                            # To not loose the irmConstraintWithoutConflict list, I create and pass a new empty one
                            emptyList = []
                            self.resolveConflictsAndIntegrate([irmConstraintType,irmConstraintValue], irmPropertyConstraintsUpdatedSuperShape, nodeShapeProperties, emptyList, temporalOutcome, irmGraph, inputGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)    
                        irmFoundConstraint = True
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                    # minCount constraint
                    elif inputConstraintType == self.shaclNS.minCount:
                        if inputConstraintConflictCounter == 0:
                            # Scenario 4-a (minCount) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN1x is_contained_in C_IN2x.
                            if inputConstraintValue > irmConstraintValue:
                                self.scenario4aConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                            # Scenario 4-b (minCount) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN2x is_contained_in C_IN1x.
                            elif inputConstraintValue < irmConstraintValue:
                                self.scenario4bConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                        # C_IN1x WITH MULTIPLE CONFLICTS: C_IN2y is the constraint that is attempted to be added to the super shape of the TEMPORAL_SHAPE
                        elif inputConstraintConflictCounter > 0:
                            irmPropertyConstraintsUpdatedSuperShape = []
                            for s1,p1,o1 in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                                if p1 not in self.propertyPathNS and p1 != self.shaclNS.group:
                                    irmPropertyConstraintsUpdatedSuperShape.append([p1,o1])
                            # To not loose the irmConstraintWithoutConflict list, I create and pass a new empty one
                            emptyList = []
                            self.resolveConflictsAndIntegrate([irmConstraintType,irmConstraintValue], irmPropertyConstraintsUpdatedSuperShape, nodeShapeProperties, emptyList, temporalOutcome, irmGraph, inputGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)    
                        irmFoundConstraint = True
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                    # maxCount constraint
                    elif inputConstraintType == self.shaclNS.maxCount:
                        if inputConstraintConflictCounter == 0:
                            # Scenario 4-a (maxCount) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN1x is_contained_in C_IN2x.
                            if inputConstraintValue < irmConstraintValue:
                                self.scenario4aConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                            # Scenario 4-b (maxCount) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN2x is_contained_in C_IN1x.
                            elif inputConstraintValue > irmConstraintValue:
                                self.scenario4bConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                        # C_IN1x WITH MULTIPLE CONFLICTS: C_IN2y is the constraint that is attempted to be added to the super shape of the TEMPORAL_SHAPE
                        elif inputConstraintConflictCounter > 0:
                            irmPropertyConstraintsUpdatedSuperShape = []
                            for s1,p1,o1 in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                                if p1 not in self.propertyPathNS and p1 != self.shaclNS.group:
                                    irmPropertyConstraintsUpdatedSuperShape.append([p1,o1])
                            # To not loose the irmConstraintWithoutConflict list, I create and pass a new empty one
                            emptyList = []
                            self.resolveConflictsAndIntegrate([irmConstraintType,irmConstraintValue], irmPropertyConstraintsUpdatedSuperShape, nodeShapeProperties, emptyList, temporalOutcome, irmGraph, inputGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)    
                        irmFoundConstraint = True
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                    # minInclusive constraint
                    elif inputConstraintType == self.shaclNS.minInclusive:
                        if inputConstraintConflictCounter == 0:
                            # Scenario 4-a (minInclusive) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN1x is_contained_in C_IN2x.
                            if inputConstraintValue > irmConstraintValue:
                                self.scenario4aConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                            # Scenario 4-b (minInclusive) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN2x is_contained_in C_IN1x.
                            elif inputConstraintValue < irmConstraintValue:
                                self.scenario4bConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                        # C_IN1x WITH MULTIPLE CONFLICTS: C_IN2y is the constraint that is attempted to be added to the super shape of the TEMPORAL_SHAPE
                        elif inputConstraintConflictCounter > 0:
                            irmPropertyConstraintsUpdatedSuperShape = []
                            for s1,p1,o1 in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                                if p1 not in self.propertyPathNS and p1 != self.shaclNS.group:
                                    irmPropertyConstraintsUpdatedSuperShape.append([p1,o1])
                            # To not loose the irmConstraintWithoutConflict list, I create and pass a new empty one
                            emptyList = []
                            self.resolveConflictsAndIntegrate([irmConstraintType,irmConstraintValue], irmPropertyConstraintsUpdatedSuperShape, nodeShapeProperties, emptyList, temporalOutcome, irmGraph, inputGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)    
                        irmFoundConstraint = True
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                    # maxInclusive constraint
                    elif inputConstraintType == self.shaclNS.maxInclusive:
                        if inputConstraintConflictCounter == 0:
                            # Scenario 4-a (maxInclusive) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN1x is_contained_in C_IN2x.
                            if inputConstraintValue < irmConstraintValue:
                                self.scenario4aConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                            # Scenario 4-b (maxInclusive) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN2x is_contained_in C_IN1x.
                            elif inputConstraintValue > irmConstraintValue:
                                self.scenario4bConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                        # C_IN1x WITH MULTIPLE CONFLICTS: C_IN2y is the constraint that is attempted to be added to the super shape of the TEMPORAL_SHAPE
                        elif inputConstraintConflictCounter > 0:
                            irmPropertyConstraintsUpdatedSuperShape = []
                            for s1,p1,o1 in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                                if p1 not in self.propertyPathNS and p1 != self.shaclNS.group:
                                    irmPropertyConstraintsUpdatedSuperShape.append([p1,o1])
                            # To not loose the irmConstraintWithoutConflict list, I create and pass a new empty one
                            emptyList = []
                            self.resolveConflictsAndIntegrate([irmConstraintType,irmConstraintValue], irmPropertyConstraintsUpdatedSuperShape, nodeShapeProperties, emptyList, temporalOutcome, irmGraph, inputGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)    
                        irmFoundConstraint = True
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                    # minLength constraint
                    elif inputConstraintType == self.shaclNS.minLength:
                        if inputConstraintConflictCounter == 0:
                            # Scenario 4-a (minLength) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN1x is_contained_in C_IN2x.
                            if inputConstraintValue > irmConstraintValue:
                                self.scenario4aConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                            # Scenario 4-b (minLength) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN2x is_contained_in C_IN1x.
                            elif inputConstraintValue < irmConstraintValue:
                                self.scenario4bConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                        # C_IN1x WITH MULTIPLE CONFLICTS: C_IN2y is the constraint that is attempted to be added to the super shape of the TEMPORAL_SHAPE
                        elif inputConstraintConflictCounter > 0:
                            irmPropertyConstraintsUpdatedSuperShape = []
                            for s1,p1,o1 in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                                if p1 not in self.propertyPathNS and p1 != self.shaclNS.group:
                                    irmPropertyConstraintsUpdatedSuperShape.append([p1,o1])
                            # To not loose the irmConstraintWithoutConflict list, I create and pass a new empty one
                            emptyList = []
                            self.resolveConflictsAndIntegrate([irmConstraintType,irmConstraintValue], irmPropertyConstraintsUpdatedSuperShape, nodeShapeProperties, emptyList, temporalOutcome, irmGraph, inputGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)    
                        irmFoundConstraint = True
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                    # maxLength constraint
                    elif inputConstraintType == self.shaclNS.maxLength:
                        if inputConstraintConflictCounter == 0:
                            # Scenario 4-a (maxLength) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN1x is_contained_in C_IN2x.
                            if inputConstraintValue < irmConstraintValue:
                                self.scenario4aConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                            # Scenario 4-b (maxLength) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN2x is_contained_in C_IN1x.
                            elif inputConstraintValue > irmConstraintValue:
                                self.scenario4bConflictResolution(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes)
                        # C_IN1x WITH MULTIPLE CONFLICTS: C_IN2y is the constraint that is attempted to be added to the super shape of the TEMPORAL_SHAPE
                        elif inputConstraintConflictCounter > 0:
                            irmPropertyConstraintsUpdatedSuperShape = []
                            for s1,p1,o1 in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                                if p1 not in self.propertyPathNS and p1 != self.shaclNS.group:
                                    irmPropertyConstraintsUpdatedSuperShape.append([p1,o1])
                            # To not loose the irmConstraintWithoutConflict list, I create and pass a new empty one
                            emptyList = []
                            self.resolveConflictsAndIntegrate([irmConstraintType,irmConstraintValue], irmPropertyConstraintsUpdatedSuperShape, nodeShapeProperties, emptyList, temporalOutcome, irmGraph, inputGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)    
                        irmFoundConstraint = True
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                    # hasValue constraint
                    elif inputConstraintType == self.shaclNS.hasValue:
                        if inputConstraintConflictCounter == 0:
                            # Get the content of the RDF lists that contain the values of sh:hasValue
                            inputRDFlist = self.getElementsOfRDFlist(inputGraph, inputConstraintValue) 
                            irmRDFlist = self.getElementsOfRDFlist(irmGraph, irmConstraintValue) 
                            equalValues = False
                            for item1 in inputRDFlist:
                                for item2 in irmRDFlist:
                                    if str(item1) == str(item2):
                                        equalValues = True
                            # Scenario 1 = C_IN1x and C_IN2x are the same type of constraint and their value spaces are contained in each other, meaning that C_IN1x is contained in C_IN2x and vice-versa (C_IN1x = C_IN2x).
                            if equalValues == True:
                                values = sorted(inputRDFlist)
                                list_node = self.createRDFListFromList(values, temporalOutcome)
                                temporalOutcome.add((blankNodePropertyIRI, irmConstraintType, list_node))
                                # Temporal structure with multiple shapes
                                if len(temporalSubShapes) > 0:
                                    for blankNodeSubShape in temporalSubShapes:
                                        list_node = self.createRDFListFromList(values, temporalOutcome)
                                        temporalOutcome.add((blankNodeSubShape[1], irmConstraintType, list_node))
                            # Scenario 2-b (hasValue) = C_IN1x and C_IN2x are the same type of constraint C_IN1x not_contained_in C_IN2x, C_IN2x not_contained_in C_IN1x and there's no super constraint value C3 between the predefined values for this specific type of SHACL constraint
                            elif equalValues == False:
                                # Add a super shape with an sh:or linking both constraints (in this case is just adding sh:hasValue twice, once for each value)
                                values = sorted(inputRDFlist)
                                list_node_in1 = self.createRDFListFromList(values, temporalOutcome)
                                temporalOutcome.add((blankNodePropertyIRI, irmConstraintType, list_node_in1))
                                values = sorted(irmRDFlist)
                                list_node_irm = self.createRDFListFromList(values, temporalOutcome)
                                temporalOutcome.add((blankNodePropertyIRI, inputConstraintType, list_node_irm))
                                # There are no temporal shapes
                                if len(temporalSuperShapeConstraints) == 0:
                                    self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, list_node_irm, irmShapeIRI, nodeShapeProperties)
                                    self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, list_node_in1, irmShapeIRI, nodeShapeProperties)
                                # Scenario in which the temporal structure has already one super shape
                                elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) == 0:
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, list_node_irm, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, list_node_in1, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                # Scenario in which the temporal structure has already multiple shapes
                                elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) > 0:
                                    self.hierarchyReorganizationProcess(temporalOutcome, irmShapeIRI, irmConstraintType, irmConstraintValue, 1)
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, list_node_irm, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, list_node_in1, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                        # C_IN1x WITH MULTIPLE CONFLICTS: C_IN2y is the constraint that is attempted to be added to the super shape of the TEMPORAL_SHAPE
                        elif inputConstraintConflictCounter > 0:
                            irmPropertyConstraintsUpdatedSuperShape = []
                            for s1,p1,o1 in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                                if p1 not in self.propertyPathNS and p1 != self.shaclNS.group:
                                    irmPropertyConstraintsUpdatedSuperShape.append([p1,o1])
                            # To not loose the irmConstraintWithoutConflict list, I create and pass a new empty one
                            emptyList = []
                            irmConstraints = []
                            irmConstraints.append([irmConstraintType,irmConstraintValue])
                            self.resolveConflictsAndIntegrate(irmConstraints, irmPropertyConstraintsUpdatedSuperShape, nodeShapeProperties, emptyList, temporalOutcome, irmGraph, inputGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)    
                        irmFoundConstraint = True
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                    # sh:in constraint
                    elif inputConstraintType == self.shaclNS["in"]:
                        # Get the content of the RDF lists that contain the values of sh:in
                        inputRDFlist = self.getElementsOfRDFlist(inputGraph, inputConstraintValue)
                        irmRDFlist = self.getElementsOfRDFlist(irmGraph, irmConstraintValue) 
                        # Scenario 1 = C_IN1x and C_IN2x are the same type of constraint and their value spaces are contained in each other, meaning that C_IN1x is contained in C_IN2x and vice-versa (C_IN1x = C_IN2x).
                        if inputRDFlist == irmRDFlist:
                            values = sorted(inputRDFlist)
                            list_node = self.createRDFListFromList(values, temporalOutcome)
                            temporalOutcome.add((blankNodePropertyIRI, irmConstraintType, list_node))
                            # Temporal structure with multiple shapes
                            if len(temporalSubShapes) > 0:
                                for blankNodeSubShape in temporalSubShapes:
                                    list_node = self.createRDFListFromList(values, temporalOutcome)
                                    temporalOutcome.add((blankNodeSubShape[1], irmConstraintType, list_node))
                            #irmFoundConstraint = True
                        # Scenario 2-b, 4-a and 4-b (in)
                        elif inputRDFlist != irmRDFlist:
                            # Scenario 4-a (in) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN1x is_contained_in C_IN2x.
                            if inputRDFlist.issubset(irmRDFlist):
                                self.scenario4aConflictResolutionIn(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes, inputRDFlist, irmRDFlist)
                            # Scenario 4-b (in) = C_IN1x and C_IN2x are the same type of constraint and their value spaces present a containment relationship where C_IN2x is_contained_in C_IN1x.
                            elif irmRDFlist.issubset(inputRDFlist):
                                self.scenario4bConflictResolutionIn(temporalOutcome, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes, inputRDFlist, irmRDFlist)
                            else:
                                combinedSet = inputRDFlist | irmRDFlist
                                CombinedSetValues = sorted(combinedSet)
                                list_node_combinedValues = self.createRDFListFromList(CombinedSetValues, temporalOutcome)
                                temporalOutcome.add((blankNodePropertyIRI, inputConstraintType, list_node_combinedValues))
                                # There are no temporal shapes
                                if len(temporalSuperShapeConstraints) == 0:
                                    inputSetValues = sorted(inputRDFlist)
                                    list_node_inputValues = self.createRDFListFromList(inputSetValues, temporalOutcome)
                                    irmSetValues = sorted(irmRDFlist)
                                    list_node_irmValues = self.createRDFListFromList(irmSetValues, temporalOutcome)
                                    self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, list_node_irmValues, irmShapeIRI, nodeShapeProperties)
                                    self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, list_node_inputValues, irmShapeIRI, nodeShapeProperties)
                                # Scenario in which the temporal structure has already one super shape
                                elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) == 0:
                                    inputSetValues = sorted(inputRDFlist)
                                    list_node_inputValues = self.createRDFListFromList(inputSetValues, temporalOutcome)
                                    irmSetValues = sorted(irmRDFlist)
                                    list_node_irmValues = self.createRDFListFromList(irmSetValues, temporalOutcome)
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, list_node_irmValues, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, list_node_inputValues, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                # Scenario in which the temporal structure has already multiple shapes
                                elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) > 0:
                                    inputSetValues = sorted(inputRDFlist)
                                    list_node_inputValues = self.createRDFListFromList(inputSetValues, temporalOutcome)
                                    irmSetValues = sorted(irmRDFlist)
                                    list_node_irmValues = self.createRDFListFromList(irmSetValues, temporalOutcome)
                                    list_node_irmValues2 = self.createRDFListFromList(irmSetValues, temporalOutcome)
                                    self.hierarchyReorganizationProcess(temporalOutcome, irmShapeIRI, irmConstraintType, list_node_irmValues2, 1)
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, list_node_irmValues, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                    self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, list_node_inputValues, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                        inputConstraintScenario3 = False
                        irmFoundConstraint = True
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                    # class constraint
                    elif inputConstraintType == self.shaclNS['class']:
                        if inputConstraintConflictCounter == 0:
                            # Scenario 2-b (class) = C_IN1x and C_IN2x are the same type of constraint C_IN1x not_contained_in C_IN2x, C_IN2x not_contained_in C_IN1x and there's no super constraint value C3 between the predefined values for this specific type of SHACL constraint
                            # Add a super shape with an sh:or linking both constraints
                            orBlankNode = BNode()
                            c1BlankNode = BNode()
                            c2BlankNode = BNode()
                            temporalOutcome.add((c1BlankNode, inputConstraintType, inputConstraintValue))
                            temporalOutcome.add((c2BlankNode, irmConstraintType, irmConstraintValue))
                            Collection(temporalOutcome, orBlankNode, [c1BlankNode, c2BlankNode])
                            temporalOutcome.add((blankNodePropertyIRI, self.shaclNS["or"], orBlankNode))
                            # There are no temporal shapes
                            if len(temporalSuperShapeConstraints) == 0:
                                self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties)
                                self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties)
                            # Scenario in which the temporal structure has already one super shape
                            elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) == 0:
                                self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                            # Scenario in which the temporal structure has already multiple shapes
                            elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) > 0:
                                self.hierarchyReorganizationProcess(temporalOutcome, irmShapeIRI, irmConstraintType, irmConstraintValue, 1)
                                self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                        # C_IN1x WITH MULTIPLE CONFLICTS: C_IN2y is the constraint that is attempted to be added to the super shape of the TEMPORAL_SHAPE
                        elif inputConstraintConflictCounter > 0:
                            irmPropertyConstraintsUpdatedSuperShape = []
                            for s1,p1,o1 in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                                if p1 not in self.propertyPathNS and p1 != self.shaclNS.group:
                                    irmPropertyConstraintsUpdatedSuperShape.append([p1,o1])
                            # To not loose the irmConstraintWithoutConflict list, I create and pass a new empty one
                            emptyList = []
                            irmConstraints = []
                            irmConstraints.append([irmConstraintType,irmConstraintValue])
                            self.resolveConflictsAndIntegrate(irmConstraints, irmPropertyConstraintsUpdatedSuperShape, nodeShapeProperties, emptyList, temporalOutcome, irmGraph, inputGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)    
                        irmFoundConstraint = True
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                    inputConstraintScenario3 = False
                # Other scenarios in which the constraints types are different but their values are equal
                elif inputConstraintType != irmConstraintType and inputConstraintValue == irmConstraintValue:
                    # Scenario 2-a = C_IN1x is sh:not constraint, C_IN2x is sh:node and they refer to the same shape s1. The opposite also is true. Then there's a contradiction. C_IN1 not_contained_in C_IN2 and C_IN2 not_contained_in C_IN1. 
                    if (inputConstraintType == self.shaclNS["not"] and irmConstraintType == self.shaclNS.node) or (irmConstraintType == self.shaclNS["not"] and inputConstraintType == self.shaclNS.node):
                        # There are no temporal shapes
                        if len(temporalSuperShapeConstraints) == 0:
                            self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties)
                            self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties)
                        # Scenario in which the temporal structure has already one super shape
                        elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) == 0:
                            self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                            self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                        # Scenario in which the temporal structure has already multiple shapes
                        elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) > 0:
                            self.hierarchyReorganizationProcess(temporalOutcome, irmShapeIRI, irmConstraintType, irmConstraintValue, 1)
                            self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                            self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                        inputConstraintScenario3 = False
                        irmFoundConstraint = True
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                # Other scenarios in which the constraints types and their values are different
                elif inputConstraintType != irmConstraintType and inputConstraintValue != irmConstraintValue: 
                    # (nodeKind != Literal and [minInclusive or maxInclusive or minLength or maxLength])
                    if ((inputConstraintType == self.shaclNS.nodeKind and inputConstraintValue != self.shaclNS.Literal) and ((irmConstraintType == self.shaclNS.minInclusive) or (irmConstraintType == self.shaclNS.maxInclusive) or (irmConstraintType == self.shaclNS.minLength) or (irmConstraintType == self.shaclNS.maxLength))) or ((irmConstraintType == self.shaclNS.nodeKind and irmConstraintValue != self.shaclNS.Literal) and ((inputConstraintType == self.shaclNS.minInclusive) or (inputConstraintType == self.shaclNS.maxInclusive) or (inputConstraintType == self.shaclNS.minLength) or (inputConstraintType == self.shaclNS.maxLength))):
                        if inputConstraintConflictCounter == 0:
                            # Scenario 2-b (nodeKind != Literal and [minInclusive or maxInclusive or minLength or maxLength]) = C_IN1x and C_IN2x are the same type of constraint C_IN1x not_contained_in C_IN2x, C_IN2x not_contained_in C_IN1x and there's no super constraint value C3 between the predefined values for this specific type of SHACL constraint
                            # Add a super shape with an sh:or linking both constraints
                            orBlankNode = BNode()
                            c1BlankNode = BNode()
                            c2BlankNode = BNode()
                            temporalOutcome.add((c1BlankNode, inputConstraintType, inputConstraintValue))
                            temporalOutcome.add((c2BlankNode, irmConstraintType, irmConstraintValue))
                            Collection(temporalOutcome, orBlankNode, [c1BlankNode, c2BlankNode])
                            temporalOutcome.add((blankNodePropertyIRI, self.shaclNS["or"], orBlankNode))
                            # There are no temporal shapes
                            if len(temporalSuperShapeConstraints) == 0:
                                self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties)
                                self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties)
                            # Scenario in which the temporal structure has already one super shape
                            elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) == 0:
                                self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                            # Scenario in which the temporal structure has already multiple shapes
                            elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) > 0:
                                self.hierarchyReorganizationProcess(temporalOutcome, irmShapeIRI, irmConstraintType, irmConstraintValue, 1)
                                self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                        # C_IN1x WITH MULTIPLE CONFLICTS: C_IN2y is the constraint that is attempted to be added to the super shape of the TEMPORAL_SHAPE
                        elif inputConstraintConflictCounter > 0:
                            irmPropertyConstraintsUpdatedSuperShape = []
                            for s1,p1,o1 in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                                if p1 not in self.propertyPathNS and p1 != self.shaclNS.group:
                                    irmPropertyConstraintsUpdatedSuperShape.append([p1,o1])
                            # To not loose the irmConstraintWithoutConflict list, I create and pass a new empty one
                            emptyList = []
                            irmConstraints = []
                            irmConstraints.append([irmConstraintType,irmConstraintValue])
                            self.resolveConflictsAndIntegrate(irmConstraints, irmPropertyConstraintsUpdatedSuperShape, nodeShapeProperties, emptyList, temporalOutcome, irmGraph, inputGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)    
                        irmFoundConstraint = True
                        inputConstraintScenario3 = False
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                    # (minCount > maxCount OR minInclusive > maxInclusive)
                    elif (inputConstraintType == self.shaclNS.minCount and irmConstraintType == self.shaclNS.maxCount and inputConstraintValue > irmConstraintValue) or (irmConstraintType == self.shaclNS.minCount and inputConstraintType == self.shaclNS.maxCount and inputConstraintValue < irmConstraintValue) or (inputConstraintType == self.shaclNS.minInclusive and irmConstraintType == self.shaclNS.maxInclusive and inputConstraintValue > irmConstraintValue) or (inputConstraintType == self.shaclNS.maxInclusive and irmConstraintType == self.shaclNS.minInclusive and inputConstraintValue < irmConstraintValue) or (inputConstraintType == self.shaclNS.minInclusive and irmConstraintType == self.shaclNS.maxInclusive and inputConstraintValue > irmConstraintValue) or (inputConstraintType == self.shaclNS.minLength and irmConstraintType == self.shaclNS.maxLength and inputConstraintValue > irmConstraintValue) or (inputConstraintType == self.shaclNS.maxLength and irmConstraintType == self.shaclNS.minLength and inputConstraintValue < irmConstraintValue):
                        if inputConstraintConflictCounter == 0:
                            # Scenario 2-b (minCount > maxCount) = C_IN1x and C_IN2x are the same type of constraint C_IN1x not_contained_in C_IN2x, C_IN2x not_contained_in C_IN1x and there's no super constraint value C3 between the predefined values for this specific type of SHACL constraint
                            # Add a super shape with an sh:or linking both constraints
                            orBlankNode = BNode()
                            c1BlankNode = BNode()
                            c2BlankNode = BNode()
                            temporalOutcome.add((c1BlankNode, inputConstraintType, inputConstraintValue))
                            temporalOutcome.add((c2BlankNode, irmConstraintType, irmConstraintValue))
                            Collection(temporalOutcome, orBlankNode, [c1BlankNode, c2BlankNode])
                            temporalOutcome.add((blankNodePropertyIRI, self.shaclNS["or"], orBlankNode))
                            # There are no temporal shapes
                            if len(temporalSuperShapeConstraints) == 0:
                                self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties)
                                self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties)
                            # Scenario in which the temporal structure has already one super shape
                            elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) == 0:
                                self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                            # Scenario in which the temporal structure has already multiple shapes
                            elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) > 0:
                                self.hierarchyReorganizationProcess(temporalOutcome, irmShapeIRI, irmConstraintType, irmConstraintValue, 1)
                                self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                                self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_2', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
                        # C_IN1x WITH MULTIPLE CONFLICTS: C_IN2y is the constraint that is attempted to be added to the super shape of the TEMPORAL_SHAPE
                        elif inputConstraintConflictCounter > 0:
                            irmPropertyConstraintsUpdatedSuperShape = []
                            for s1,p1,o1 in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                                if p1 not in self.propertyPathNS and p1 != self.shaclNS.group:
                                    irmPropertyConstraintsUpdatedSuperShape.append([p1,o1])
                            # To not loose the irmConstraintWithoutConflict list, I create and pass a new empty one
                            emptyList = []
                            irmConstraints = []
                            irmConstraints.append([irmConstraintType,irmConstraintValue])
                            self.resolveConflictsAndIntegrate(irmConstraints, irmPropertyConstraintsUpdatedSuperShape, nodeShapeProperties, emptyList, temporalOutcome, irmGraph, inputGraph, blankNodePropertyIRI, groupID, irmShapeTargetIRI, irmShapePathValueIRI, irmShapeIRI)    
                        irmFoundConstraint = True
                        inputConstraintScenario3 = False
                        inputConstraintConflictCounter = inputConstraintConflictCounter + 1
                # If the IRM constraint was treated, delete it from the backup irm list of properties
                if irmFoundConstraint == True:
                    for row in irmConstraintWithoutConflict:
                        if (row[0] == irmConstraintType and row[1] == irmConstraintValue):
                            irmConstraintWithoutConflict.remove(row)
            # Scenario 3 - C_IN1x doesn't have a conflict with any C_IN2x. C_IN1x and C_IN2x are not the same type of constraint and their value spaces are compatible (C_IN1x != C_IN2x and C_IN1x != not( C_IN2x )). In addition, C_IN1x accomplishes this for each constraint of C_IN2. 
            if inputConstraintScenario3 == True:
                temporalSuperShapeConstraintsScenario3 = []
                temporalSubShapesScenario3 = []
                # Get the property constraints of the temporal super shape (if it exists and has property constraints)
                for s,p,o in temporalOutcome.triples((blankNodePropertyIRI, None, None)):
                    if p != self.propertyPathNS[0] and p != self.shaclNS.group:
                        temporalSuperShapeConstraintsScenario3.append([p,o])
                # Retrieve the existing nodeShapes of the structure and their sh:property blankNodes (apart from the super shape, since it's already accessible)
                for s,p,o in temporalOutcome.triples((None, self.rdfSyntax.type, self.shaclNS.NodeShape)):
                    for s1,p1,o1 in temporalOutcome.triples((s, self.shaclNS["property"], None)): 
                        if o1 != blankNodePropertyIRI:
                            temporalSubShapesScenario3.append([s,o1])
                # Scenario 3 without temporal shapes
                if len(temporalSuperShapeConstraintsScenario3) == 0:
                    if inputConstraintType != self.shaclNS['in'] and inputConstraintType != self.shaclNS.hasValue:
                        temporalOutcome.add((blankNodePropertyIRI, inputConstraintType, inputConstraintValue))
                    elif inputConstraintType == self.shaclNS['in'] or inputConstraintType == self.shaclNS.hasValue:
                        # Get the content of the RDF lists that contain the values of sh:in
                        inputRDFlist = self.getElementsOfRDFlist(inputGraph, inputConstraintValue)
                        values = sorted(inputRDFlist)
                        list_node = self.createRDFListFromList(values, temporalOutcome)
                        temporalOutcome.add((blankNodePropertyIRI, inputConstraintType, list_node))
                # Scenario 3 in which the temporal structure has already one super shape
                elif len(temporalSuperShapeConstraintsScenario3) > 0 and len(temporalSubShapesScenario3) == 0:
                    #print('1 shape temporal')
                    #print(inputConstraintType)
                    self.feedTemporalStructurWithExistingSuperInScenario3(temporalOutcome, inputGraph, groupID, '_sub1_1', irmShapeTargetIRI, irmShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraintsScenario3)
                # Scenario 3 in which the temporal structure has already multiple shapes
                elif len(temporalSuperShapeConstraintsScenario3) > 0 and len(temporalSubShapesScenario3) > 0:
                    #print('multiple temporal shapes')
                    #print(inputConstraintType)
                    # C_IN1x is compared against the super TEMPORAL_SHAPE
                    conflictAgainstTemporalSuperShape = self.isThereConflict(temporalSuperShapeConstraintsScenario3, inputConstraintType, inputConstraintValue) 
                    # IF C_IN1x has no conflict with neither of the respective constraints
                    if conflictAgainstTemporalSuperShape == False:
                        # C_IN1x is attempted to be added to the lower existing level of the TEMPORAL_SHAPE structure. 
                        # get the nodeShape IRIs and the associated blankNode of the lower existing level of the TEMPORAL_SHAPE structure.
                        nodeShapeIRIsLowerLevel = []
                        nodeShapeIRIsLowerLevel = self.getTemporalHierarchyLowerLevel(temporalSubShapesScenario3)
                        insertedInLowerLevel = False
                        # If there's no conflict of C_IN1x with at least all the constraints of one shape of this level
                        for nodeShapeIRI in nodeShapeIRIsLowerLevel:
                            conflictAgainstTemporalLowerSubShape = False
                            lowerLevelShapePropertyConstraints = []
                            for s,p,o in temporalOutcome.triples((nodeShapeIRI[1], None, None)): 
                                if p != self.propertyPathNS[0] and p != self.shaclNS.group:
                                    lowerLevelShapePropertyConstraints.append([p,o])
                            conflictAgainstTemporalLowerSubShape = self.isThereConflict(lowerLevelShapePropertyConstraints, inputConstraintType, inputConstraintValue) 
                            # No conflict with a shape of the lower level
                            if conflictAgainstTemporalLowerSubShape == False:
                                if inputConstraintType != self.shaclNS['in'] and inputConstraintType != self.shaclNS.hasValue:
                                    temporalOutcome.add((nodeShapeIRI[1], inputConstraintType, inputConstraintValue))
                                elif inputConstraintType == self.shaclNS['in'] or inputConstraintType == self.shaclNS.hasValue:
                                    #print('Inserta el in aca')
                                    # Get the content of the RDF lists that contain the values of sh:in
                                    inputRDFlist = self.getElementsOfRDFlist(inputGraph, inputConstraintValue)
                                    #print('in values')
                                    #print(inputRDFlist)
                                    values = sorted(inputRDFlist)
                                    list_node = self.createRDFListFromList(values, temporalOutcome)
                                    temporalOutcome.add((nodeShapeIRI[1], inputConstraintType, list_node))
                                insertedInLowerLevel = True
                        # IF there's one or more conflicts with all the shapes of the lower level
                        if insertedInLowerLevel == False:
                            # C_IN1x is attempted to be added through an sh:or to the super TEMPORAL_SHAPE. The sh:or involves all the original constraints of the shape.
                            orBlankNode = BNode()
                            c1BlankNode = BNode()
                            c2BlankNode = BNode()
                            if inputConstraintType != self.shaclNS['in'] and inputConstraintType != self.shaclNS.hasValue:
                                temporalOutcome.add((c1BlankNode, inputConstraintType, inputConstraintValue))
                            elif inputConstraintType == self.shaclNS['in'] or inputConstraintType == self.shaclNS.hasValue:
                                # Get the content of the RDF lists that contain the values of sh:in
                                inputRDFlist = self.getElementsOfRDFlist(inputGraph, inputConstraintValue)
                                values = sorted(inputRDFlist)
                                list_node = self.createRDFListFromList(values, temporalOutcome)
                                temporalOutcome.add((c1BlankNode, inputConstraintType, list_node))
                            temporalOutcome.add((c2BlankNode, irmConstraintType, irmConstraintValue))
                            Collection(temporalOutcome, orBlankNode, [c1BlankNode, c2BlankNode])
                            temporalOutcome.remove((blankNodePropertyIRI,irmConstraintType, irmConstraintValue))
                            temporalOutcome.add((blankNodePropertyIRI, self.shaclNS["or"], orBlankNode))       

    def feedTemporalShapes(self, temporalOutcomeGraph: Graph, groupId, hiearchyId, ShapeTargetIRI, ShapePathValueIRI, ConstraintType, ConstraintValue, superShapeIRI:str, nodeShapeProperties:list):
        bNodeNodeShape = BNode()
        nodeShape_IRI = groupId + hiearchyId
        temporalOutcomeGraph.add((nodeShape_IRI, self.rdfSyntax.type, self.shaclNS.NodeShape))
        temporalOutcomeGraph.add((nodeShape_IRI, self.shaclNS.targetClass, ShapeTargetIRI))
        #temporalOutcomeGraph.add((nodeShape_IRI, self.shaclNS.deactivated, True))
        for nodeShapeProperty in nodeShapeProperties:
            temporalOutcomeGraph.add((nodeShape_IRI, nodeShapeProperty[0], nodeShapeProperty[1]))
        temporalOutcomeGraph.add((nodeShape_IRI, self.shaclNS["property"], bNodeNodeShape))
        temporalOutcomeGraph.add((bNodeNodeShape, self.propertyPathNS[0], ShapePathValueIRI))
        temporalOutcomeGraph.add((bNodeNodeShape, ConstraintType, ConstraintValue))
        temporalOutcomeGraph.add((bNodeNodeShape, self.shaclNS.group, groupId))
        temporalOutcomeGraph.add((nodeShape_IRI, self.shaclNS.node, superShapeIRI))

    def feedTemporalStructurWithExistingSuper(self, temporalOutcomeGraph: Graph, groupId, hiearchyId, ShapeTargetIRI, ShapePathValueIRI, ConstraintType, ConstraintValue, superShapeIRI:str, nodeShapeProperties, temporalSuperShapeConstraints: list):
        bNodeNodeShape = BNode()
        nodeShape_IRI = groupId + hiearchyId
        temporalOutcomeGraph.add((nodeShape_IRI, self.rdfSyntax.type, self.shaclNS.NodeShape))
        temporalOutcomeGraph.add((nodeShape_IRI, self.shaclNS.targetClass, ShapeTargetIRI))
        #temporalOutcomeGraph.add((nodeShape_IRI, self.shaclNS.deactivated, True))
        for nodeShapeProperty in nodeShapeProperties:
            temporalOutcomeGraph.add((nodeShape_IRI, nodeShapeProperty[0], nodeShapeProperty[1]))
        temporalOutcomeGraph.add((nodeShape_IRI, self.shaclNS["property"], bNodeNodeShape))
        temporalOutcomeGraph.add((bNodeNodeShape, self.propertyPathNS[0], ShapePathValueIRI))
        for temporalConstraint in temporalSuperShapeConstraints:
            temporalOutcomeGraph.add((bNodeNodeShape, temporalConstraint[0], temporalConstraint[1]))
        temporalOutcomeGraph.add((bNodeNodeShape, ConstraintType, ConstraintValue))
        temporalOutcomeGraph.add((bNodeNodeShape, self.shaclNS.group, groupId))
        temporalOutcomeGraph.add((nodeShape_IRI, self.shaclNS.node, superShapeIRI))
    
    def feedTemporalStructurWithExistingSuperInScenario3(self, temporalOutcomeGraph, inputGraph: Graph, groupId, hiearchyId, ShapeTargetIRI, ShapePathValueIRI, ConstraintType, ConstraintValue, superShapeIRI:str, nodeShapeProperties, temporalSuperShapeConstraints: list):
        bNodeNodeShape = BNode()
        nodeShape_IRI = groupId + hiearchyId
        temporalOutcomeGraph.add((nodeShape_IRI, self.rdfSyntax.type, self.shaclNS.NodeShape))
        temporalOutcomeGraph.add((nodeShape_IRI, self.shaclNS.targetClass, ShapeTargetIRI))
        #temporalOutcomeGraph.add((nodeShape_IRI, self.shaclNS.deactivated, True))
        for nodeShapeProperty in nodeShapeProperties:
            temporalOutcomeGraph.add((nodeShape_IRI, nodeShapeProperty[0], nodeShapeProperty[1]))
        temporalOutcomeGraph.add((nodeShape_IRI, self.shaclNS["property"], bNodeNodeShape))
        temporalOutcomeGraph.add((bNodeNodeShape, self.propertyPathNS[0], ShapePathValueIRI))
        for temporalConstraint in temporalSuperShapeConstraints:
            if temporalConstraint[0] != self.shaclNS['in'] and temporalConstraint[0] != self.shaclNS.hasValue:
                temporalOutcomeGraph.add((bNodeNodeShape, temporalConstraint[0], temporalConstraint[1]))
            elif temporalConstraint[0] == self.shaclNS['in'] or temporalConstraint[0] == self.shaclNS.hasValue:
                # Get the content of the RDF lists that contain the values of sh:in
                superShapeInRDFlist = self.getElementsOfRDFlist(temporalOutcomeGraph, temporalConstraint[1])
                valuesSuperShapeIn = sorted(superShapeInRDFlist)
                list_node_superShapeIn = self.createRDFListFromList(valuesSuperShapeIn, temporalOutcomeGraph)
                temporalOutcomeGraph.add((bNodeNodeShape, temporalConstraint[0], list_node_superShapeIn))
        if ConstraintType != self.shaclNS['in'] and ConstraintType != self.shaclNS.hasValue and ConstraintType != self.shaclNS['or']:
            temporalOutcomeGraph.add((bNodeNodeShape, ConstraintType, ConstraintValue))
        elif ConstraintType == self.shaclNS['in'] or ConstraintType == self.shaclNS.hasValue:
            # Get the content of the RDF lists that contain the values of sh:in
            inputRDFlist = self.getElementsOfRDFlist(inputGraph, ConstraintValue)
            values = sorted(inputRDFlist)
            list_node = self.createRDFListFromList(values, temporalOutcomeGraph)
            temporalOutcomeGraph.add((bNodeNodeShape, ConstraintType, list_node))
        elif ConstraintType == self.shaclNS['or']:
            # Get the content of the RDF lists that contain the values of sh:or [contraintType,constraintValue]
            inputRDFlist = self.getElementsOfRDFlistOr(inputGraph, ConstraintValue) 
            list_node_superShapeOr = self.createRDFListFromListOr(inputRDFlist, temporalOutcomeGraph) 
            temporalOutcomeGraph.add((bNodeNodeShape, ConstraintType, list_node_superShapeOr))
        temporalOutcomeGraph.add((bNodeNodeShape, self.shaclNS.group, groupId))
        temporalOutcomeGraph.add((nodeShape_IRI, self.shaclNS.node, superShapeIRI))

    # HIERARCHY_REORGANIZATION_PROCESS
    def hierarchyReorganizationProcess(self, temporalShapeStructure: Graph, superShapeIRI, irmConstraintType, irmConstraintValue: str, startLevel: int):
        substring = '_sub'
        for s,p,o in temporalShapeStructure.triples((None, self.rdfSyntax.type, self.shaclNS.NodeShape)):
            if s != superShapeIRI:
                for s1,p1,o1 in temporalShapeStructure.triples((s, None, None)):
                    # Take the shape IRI until the hierarchy value
                    index = s.find(substring)
                    if index != -1:
                        shapeIRIroot = s[:index + len(substring)]
                        # Take the hierachy value
                        hierarchyValue = s[index + len(substring)]
                        if int(hierarchyValue) >= startLevel:
                            # Take the rest of the IRI after the hierarchy value
                            shapeIRIrest = s[index + len(substring) + 1:]
                            # sum up one to the hierarchy value             
                            newHierarchyValue = int(hierarchyValue) + 1
                            # Put everything together in the IRI with the new hierarchy value
                            newShapeIRI = shapeIRIroot + str(newHierarchyValue) + shapeIRIrest
                            if p1 != self.shaclNS.node:
                                # Delete the triples that have the old IRI
                                temporalShapeStructure.remove((s,p1,o1))
                                # Insert the triples with the new IRI
                                temporalShapeStructure.add((URIRef(newShapeIRI),p1,o1))
                                # Add the C_IN2 constraint to the shapes moved
                                if p1 == self.shaclNS["property"]:
                                    temporalShapeStructure.add((o1,irmConstraintType,irmConstraintValue))
                            # Update also the shape referenced in sh:node
                            elif p1 == self.shaclNS.node:
                                # Take the shape IRI until the hierarchy value
                                indexNode = o1.rfind('_')
                                if indexNode != -1:
                                    hierarchyNode = o1[indexNode + 1:]
                                    if hierarchyNode == 'sup':
                                        newNodeObject = o1[:indexNode + 1] + '_sub1_1'
                                        # Delete the node triples that reference the old IRI
                                        temporalShapeStructure.remove((s,p1,o1))
                                        # Insert the triples with the new IRI
                                        temporalShapeStructure.add((URIRef(newShapeIRI),p1,URIRef(newNodeObject)))
                                    elif hierarchyNode != 'sup': ### *** THIS NEEDS TO BE TESTED ###
                                        indexCompleteHierarchyID = o1.rfind('_', 0, indexNode)
                                        nodeIRIroot = o1[:indexCompleteHierarchyID + 1]
                                        sibling = o1[indexNode + 1:]
                                        nodeHierarchyValue = s[indexCompleteHierarchyID + len(substring) - 1]
                                        nodeNewHierarchyValue = int(nodeHierarchyValue) + 1
                                        newNodeObject = nodeIRIroot + substring + str(nodeNewHierarchyValue) + str(sibling)
                                        # Delete the node triples that reference the old IRI
                                        temporalShapeStructure.remove((s,p1,o1))
                                        # Insert the triples with the new IRI
                                        temporalShapeStructure.add((URIRef(newShapeIRI),p1,URIRef(newNodeObject)))

    # Function for checking if a constraint has a conflict (scenarios 1, 2-a, 2-b, 4-a, 4-b, 5) with a shape
    def isThereConflict(self: Graph, temporalSuperShapeConstraintsScenario3: list, inputConstraintType, inputConstraintValue: str):
        conflictFound = False
        for shapeConstraint in temporalSuperShapeConstraintsScenario3:
            if (inputConstraintType == shapeConstraint[0] and inputConstraintValue == shapeConstraint[1]) or (inputConstraintType == shapeConstraint[0] and inputConstraintValue != shapeConstraint[1]) or (inputConstraintType != shapeConstraint[0] and (inputConstraintType == self.shaclNS["not"] or shapeConstraint[0] == self.shaclNS["not"]) and inputConstraintValue == shapeConstraint[1]) or ((inputConstraintType != shapeConstraint[0] and inputConstraintValue != shapeConstraint[1]) and (((((inputConstraintType == self.shaclNS.nodeKind and inputConstraintValue != self.shaclNS.Literal) and ((shapeConstraint[0] == self.shaclNS.minInclusive) or (shapeConstraint[0] == self.shaclNS.maxInclusive) or (shapeConstraint[0] == self.shaclNS.minLength) or (shapeConstraint[0] == self.shaclNS.maxLength))) or ((shapeConstraint[0] == self.shaclNS.nodeKind and shapeConstraint[1] != self.shaclNS.Literal) and ((inputConstraintType == self.shaclNS.minInclusive) or (inputConstraintType == self.shaclNS.maxInclusive) or (inputConstraintType == self.shaclNS.minLength) or (inputConstraintType == self.shaclNS.maxLength))))) or ((inputConstraintType == self.shaclNS.minCount and shapeConstraint[0] == self.shaclNS.maxCount and inputConstraintValue > shapeConstraint[1]) or (shapeConstraint[0] == self.shaclNS.minCount and inputConstraintType == self.shaclNS.maxCount and inputConstraintValue < shapeConstraint[1]) or (inputConstraintType == self.shaclNS.minInclusive and shapeConstraint[0] == self.shaclNS.maxInclusive and inputConstraintValue > shapeConstraint[1]) or (inputConstraintType == self.shaclNS.maxInclusive and shapeConstraint[0] == self.shaclNS.minInclusive and inputConstraintValue < shapeConstraint[1]) or (inputConstraintType == self.shaclNS.minInclusive and shapeConstraint[0] == self.shaclNS.maxInclusive and inputConstraintValue > shapeConstraint[1]) or (inputConstraintType == self.shaclNS.minLength and shapeConstraint[0] == self.shaclNS.maxLength and inputConstraintValue > shapeConstraint[1]) or (inputConstraintType == self.shaclNS.maxLength and shapeConstraint[0] == self.shaclNS.minLength and inputConstraintValue < shapeConstraint[1])))):
                conflictFound = True
                break
        return conflictFound
    
    # Find the lower level of the hierarchy and retrieve the IRIs of the node shapes which belong to this level ([nodeShapeIRI, blankNodeID, lowerHierarchyLevelInteger])
    def getTemporalHierarchyLowerLevel(self, temporalSubShapesScenario3: list): 
        preHierarchyNumber = '_sub'
        postHierarchyNumber = '_'
        hierarchyLowerLevel = 0
        nodeShapeIRIsLowerLevel = []
        for nodeShapeIRI in temporalSubShapesScenario3:
            start_index = nodeShapeIRI[0].rfind(preHierarchyNumber) + 1
            end_index = nodeShapeIRI[0].rfind(postHierarchyNumber)
            if start_index != -1 and end_index != -1 and start_index < end_index:
                hierarchyLevel = int(nodeShapeIRI[0][start_index+3:end_index])
                if hierarchyLevel > hierarchyLowerLevel:
                    hierarchyLowerLevel = hierarchyLevel
                    nodeShapeIRIsLowerLevel = []
                    nodeShapeIRIsLowerLevel.append([nodeShapeIRI[0],nodeShapeIRI[1],hierarchyLowerLevel])
                elif hierarchyLevel == hierarchyLowerLevel:
                    nodeShapeIRIsLowerLevel.append([nodeShapeIRI[0],nodeShapeIRI[1],hierarchyLowerLevel])
        return nodeShapeIRIsLowerLevel
    
    # Function to return the last sibling of the lower level of a temporal structure of shapes
    def getTemporalHierarchyLevelLastSibling(self, temporalOutcome: Graph, hierarchyCurrentLevel: int, blankNodePropertyIRI: str): 
        preHierarchyNumber = '_sub'
        postHierarchyNumber = '_'
        lastSiblingValue = 0
        temporalSubShapes = []
        for s,p,o in temporalOutcome.triples((None, self.rdfSyntax.type, self.shaclNS.NodeShape)):
            for s1,p1,o1 in temporalOutcome.triples((s, self.shaclNS["property"], None)): 
                if o1 != blankNodePropertyIRI:
                    temporalSubShapes.append([s,o1])
        for nodeShapeIRI in temporalSubShapes:
            start_index = nodeShapeIRI[0].rfind(preHierarchyNumber) + 1
            end_index = nodeShapeIRI[0].rfind(postHierarchyNumber)
            if start_index != -1 and end_index != -1 and start_index < end_index:
                hierarchyLevel = int(nodeShapeIRI[0][start_index+3:end_index])
                siblingValue = int(nodeShapeIRI[0][end_index+1:])
                if hierarchyLevel == hierarchyCurrentLevel:
                    if lastSiblingValue < siblingValue:
                        lastSiblingValue = siblingValue
        return lastSiblingValue
    
    def scenario4aConflictResolution(self, temporalOutcome: Graph, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, ShapeTargetIRI, ShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI: str, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes: list):
        temporalOutcome.add((blankNodePropertyIRI, irmConstraintType, irmConstraintValue))
        # There are no temporal shapes
        if len(temporalSuperShapeConstraints) == 0:
            self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_1', ShapeTargetIRI, ShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties)
        # Scenario in which the temporal structure has already one super shape
        elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) == 0:
            self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', ShapeTargetIRI, ShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
        # Scenario in which the temporal structure has already multiple shapes
        elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) > 0:
            # C_IN1x is added all the temporal sub shapes (** only if there's no conflict).
            for subShapeBnode in temporalSubShapes:
                temporalSubShapePropertyConstraints = []
                conflictAgainstTemporalSubShape = False
                # Get the constraints of this sub shape
                for s,p,o in temporalOutcome.triples((subShapeBnode[1], None, None)): 
                    if p != self.propertyPathNS[0] and p != self.shaclNS.group:
                        temporalSubShapePropertyConstraints.append([p,o])
                # Check if the sub shape has a conflict with C_IN1x
                conflictAgainstTemporalSubShape = self.isThereConflict(temporalSubShapePropertyConstraints, inputConstraintType, inputConstraintValue) 
                if conflictAgainstTemporalSubShape == False:
                    temporalOutcome.add((subShapeBnode[1], inputConstraintType, inputConstraintValue))

    
    def scenario4bConflictResolution(self, temporalOutcome: Graph, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, ShapeTargetIRI, ShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI: str, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes: list):
        temporalOutcome.add((blankNodePropertyIRI, inputConstraintType, inputConstraintValue))
        # There are no temporal shapes
        if len(temporalSuperShapeConstraints) == 0:
            self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_1', ShapeTargetIRI, ShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties)
        # Scenario in which the temporal structure has already one super shape
        elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) == 0:
            self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', ShapeTargetIRI, ShapePathValueIRI, irmConstraintType, irmConstraintValue, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
        # Scenario in which the temporal structure has already multiple shapes
        elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) > 0:
            # C_IN2x is added all the temporal sub shapes (** only if there's no conflict).
            for subShapeBnode in temporalSubShapes:
                temporalSubShapePropertyConstraints = []
                conflictAgainstTemporalSubShape = False
                # Get the constraints of this sub shape
                for s,p,o in temporalOutcome.triples((subShapeBnode[1], None, None)): 
                    if p != self.propertyPathNS[0] and p != self.shaclNS.group:
                        temporalSubShapePropertyConstraints.append([p,o])
                # Check if the sub shape has a conflict with C_IN2x
                conflictAgainstTemporalSubShape = self.isThereConflict(temporalSubShapePropertyConstraints, irmConstraintType, irmConstraintValue) 
                if conflictAgainstTemporalSubShape == False:
                    temporalOutcome.add((subShapeBnode[1], irmConstraintType, irmConstraintValue)) 

    def getElementsOfRDFlist(self, shapeGraph: Graph, inputConstraintValue: str):
        setOfElements = set()
        current = inputConstraintValue
        while current != self.rdfSyntax.nil:
            first = str(shapeGraph.value(subject=current, predicate=self.rdfSyntax.first))
            if first:
                setOfElements.add(first)
            current = shapeGraph.value(subject=current, predicate=self.rdfSyntax.rest)
            if current is None:
                break
        return setOfElements
    
    def createRDFListFromList(self, values:List, temporalOutcome: Graph):
        current = self.rdfSyntax.nil
        for value in reversed(values):
            list_node = BNode()
            temporalOutcome.add((list_node, self.rdfSyntax.first, Literal(value)))
            temporalOutcome.add((list_node, self.rdfSyntax.rest, current))
            current = list_node
        return current
    
    def createRDFListFromListOr(self, values:List, temporalOutcome: Graph):
        current = self.rdfSyntax.nil
        for value in reversed(values):
            list_node = BNode()
            contraintBnode = BNode()
            temporalOutcome.add((list_node, self.rdfSyntax.first, contraintBnode))
            temporalOutcome.add((contraintBnode, value[0], value[1]))
            temporalOutcome.add((list_node, self.rdfSyntax.rest, current))
            current = list_node
        return current
    
    def getElementsOfRDFlistOr(self, shapeGraph: Graph, inputConstraintValue: str):
        current = inputConstraintValue
        # First get the blank nodes that are aimed by the sh:or list
        orBnodes = []
        ListOfConstraintValues = []
        while current != self.rdfSyntax.nil:
            first = shapeGraph.value(subject=current, predicate=self.rdfSyntax.first)
            if first:
                orBnodes.append(first)
            current = shapeGraph.value(subject=current, predicate=self.rdfSyntax.rest)
            if current is None:
                break
        for blankNode in orBnodes:
            for s,p,o in shapeGraph.triples((blankNode, None, None)):
                ListOfConstraintValues.append([p,o])
        return ListOfConstraintValues
    
    def scenario4aConflictResolutionIn(self, temporalOutcome: Graph, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, ShapeTargetIRI, ShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI: str, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes: list, inputRDFlist, irmRDFlist: set):
        inputValues = sorted(inputRDFlist)
        irmValues = sorted(irmRDFlist)
        list_node_irmValues = self.createRDFListFromList(irmValues, temporalOutcome)
        temporalOutcome.add((blankNodePropertyIRI, irmConstraintType, list_node_irmValues))
        # There are no temporal shapes
        if len(temporalSuperShapeConstraints) == 0:
            list_node_sub_inputValues = self.createRDFListFromList(inputValues, temporalOutcome)
            self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_1', ShapeTargetIRI, ShapePathValueIRI, inputConstraintType, list_node_sub_inputValues, irmShapeIRI, nodeShapeProperties)
        # Scenario in which the temporal structure has already one super shape
        elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) == 0:
            list_node_sub_inputValues = self.createRDFListFromList(inputValues, temporalOutcome)
            self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', ShapeTargetIRI, ShapePathValueIRI, inputConstraintType, list_node_sub_inputValues, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
        # Scenario in which the temporal structure has already multiple shapes
        elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) > 0:
            # C_IN1x is added all the temporal sub shapes (** only if there's no conflict).
            for subShapeBnode in temporalSubShapes:
                temporalSubShapePropertyConstraints = []
                conflictAgainstTemporalSubShape = False
                # Get the constraints of this sub shape
                for s,p,o in temporalOutcome.triples((subShapeBnode[1], None, None)): 
                    if p != self.propertyPathNS[0] and p != self.shaclNS.group:
                        temporalSubShapePropertyConstraints.append([p,o])
                # Check if the sub shape has a conflict with C_IN1x
                conflictAgainstTemporalSubShape = self.isThereConflict(temporalSubShapePropertyConstraints, inputConstraintType, inputValues) 
                if conflictAgainstTemporalSubShape == False:
                    # Temporal structure with multiple shapes
                    list_node = self.createRDFListFromList(inputValues, temporalOutcome)
                    temporalOutcome.add((subShapeBnode[1], inputConstraintType, list_node))

    def scenario4bConflictResolutionIn(self, temporalOutcome: Graph, blankNodePropertyIRI, irmConstraintType, irmConstraintValue, groupID, ShapeTargetIRI, ShapePathValueIRI, inputConstraintType, inputConstraintValue, irmShapeIRI: str, temporalSuperShapeConstraints, nodeShapeProperties, temporalSubShapes: list, inputRDFlist, irmRDFlist: set):
        inputValues = sorted(inputRDFlist)
        irmValues = sorted(irmRDFlist)
        list_node_inputValues = self.createRDFListFromList(inputValues, temporalOutcome)
        temporalOutcome.add((blankNodePropertyIRI, irmConstraintType, list_node_inputValues))
        # There are no temporal shapes
        if len(temporalSuperShapeConstraints) == 0:
            list_node_sub_irmValues = self.createRDFListFromList(irmValues, temporalOutcome)
            self.feedTemporalShapes(temporalOutcome, groupID, '_sub1_1', ShapeTargetIRI, ShapePathValueIRI, irmConstraintType, list_node_sub_irmValues, irmShapeIRI, nodeShapeProperties)
        # Scenario in which the temporal structure has already one super shape
        elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) == 0:
            list_node_sub_irmValues = self.createRDFListFromList(irmValues, temporalOutcome)
            self.feedTemporalStructurWithExistingSuper(temporalOutcome, groupID, '_sub1_1', ShapeTargetIRI, ShapePathValueIRI, irmConstraintType, list_node_sub_irmValues, irmShapeIRI, nodeShapeProperties, temporalSuperShapeConstraints)
        # Scenario in which the temporal structure has already multiple shapes
        elif len(temporalSuperShapeConstraints) > 0 and len(temporalSubShapes) > 0:
            # C_IN2x is added all the temporal sub shapes (** only if there's no conflict).
            for subShapeBnode in temporalSubShapes:
                temporalSubShapePropertyConstraints = []
                conflictAgainstTemporalSubShape = False
                # Get the constraints of this sub shape
                for s,p,o in temporalOutcome.triples((subShapeBnode[1], None, None)): 
                    if p != self.propertyPathNS[0] and p != self.shaclNS.group:
                        temporalSubShapePropertyConstraints.append([p,o])
                # Check if the sub shape has a conflict with C_IN2x
                conflictAgainstTemporalSubShape = self.isThereConflict(temporalSubShapePropertyConstraints, irmConstraintType, irmValues) 
                if conflictAgainstTemporalSubShape == False:
                    list_node = self.createRDFListFromList(irmValues, temporalOutcome)
                    temporalOutcome.add((subShapeBnode[1], irmConstraintType, list_node))

    def deactivateShapesOfUpdatedIRM(self, updatedIRM: Graph):
        for s,p,o in updatedIRM.triples((None, self.rdfSyntax.type, self.shaclNS.NodeShape)):
            insertDeactivate = True
            for s1,p1,o1 in updatedIRM.triples((s, None, None)):
                if p1 == self.shaclNS.deactivated and o1 == False:
                    updatedIRM.remove((s1,p1,o1))
                    updatedIRM.add((s1,p1,True))
                    insertDeactivate = False
                elif p1 == self.shaclNS.deactivated and o1 == True:
                    insertDeactivate = False
            if insertDeactivate == True:
                updatedIRM.add((s,self.shaclNS.deactivated,Literal(True)))

    # Integrating a set of shapes into a single shape
    def integration(self):

        updatedIRM = Graph()

        IrmNodeShapesSimpleTarget = self.getNodeShapesSimpleTargets(self.SHACL) # Retrieves those simple targets as lists [[nodeShapeIRI, targetIRI]] from the current IRM.

        InputNodeShapesSimpleTarget = self.getNodeShapesSimpleTargets(self.inputShapes) # Retrieves those simple targets as lists [[nodeShapeIRI, targetIRI]] from the input Shape graph.

        IrmNodeShapesSimpleTargetWithEquivalence = []
        InputNodeShapesSimpleTargetWithEquivalence = []
        IrmNodeShapesSimpleTargetWithoutEquivalence = []
        InputNodeShapesSimpleTargetWithoutEquivalence = []

        # This block of code creates two new lists [[nodeShapeIRI, targetIRI]] where it saves those simple targets that had equivalence. One for the IRM and another for the input shape graph.
        # In addition, it saves in another list [[nodeShapeIRI, targetIRI]] the IRM simple targets that didn't have an equivalence.
        for irmElement in IrmNodeShapesSimpleTarget:
            irmTargetFound = False
            for inputElement in InputNodeShapesSimpleTarget:
                if irmElement[1] == inputElement[1]:
                    IrmNodeShapesSimpleTargetWithEquivalence.append([irmElement[0],irmElement[1]])
                    InputNodeShapesSimpleTargetWithEquivalence.append([inputElement[0],inputElement[1]])
                    irmTargetFound = True
            if irmTargetFound == False:
                IrmNodeShapesSimpleTargetWithoutEquivalence.append([irmElement[0],irmElement[1]])
        
        # This block calculates the differences between the input shape graph simple targets that have an equivalence, and its complete simple target list. This is done for the creation of another list with the input shape graph simple targets which didn't have an equivalence in the IRM.
        for inputElement2 in InputNodeShapesSimpleTarget:
            inputTargetFound = False
            for inputElement3 in InputNodeShapesSimpleTargetWithEquivalence:
                if inputElement3[0] == inputElement2[0]:
                    inputTargetFound = True
            if inputTargetFound == False:
                InputNodeShapesSimpleTargetWithoutEquivalence.append([inputElement2[0],inputElement2[1]])

        # Retrieving compound targets
        IrmCompoundTargets = self.getCompoundFocusNodePropertyTargets(self.SHACL) # Retrieves those compound targets as lists [[nodeShapeIRI, targetIRI, pathValueIRI]] from the current IRM.

        InputCompoundTargets = self.getCompoundFocusNodePropertyTargets(self.inputShapes) # Retrieves those compound targets as lists [[nodeShapeIRI, targetIRI, pathValueIRI]] from the input shape graph.

        IrmCompoundTargetWithEquivalence = []
        InputCompoundTargetWithEquivalence = []
        IrmCompoundTargetWithoutEquivalence = []
        InputCompoundTargetWithoutEquivalence = []

        # This block of code creates two new lists [[nodeShapeIRI, targetIRI, pathValueIRI]] where it saves those compound targets that had equivalence. One for the IRM and another for the input shape graph.
        # In addition, it saves in another list [[nodeShapeIRI, targetIRI, pathValueIRI]] the IRM compound targets that didn't have an equivalence.
        for irmCompoundElement in IrmCompoundTargets:
            irmCompoundTargetFound = False
            for inputCompoundElement in InputCompoundTargets:
                if irmCompoundElement[1] == inputCompoundElement[1] and irmCompoundElement[2] == inputCompoundElement[2]:
                    IrmCompoundTargetWithEquivalence.append([irmCompoundElement[0],irmCompoundElement[1],irmCompoundElement[2]])
                    InputCompoundTargetWithEquivalence.append([inputCompoundElement[0],inputCompoundElement[1],inputCompoundElement[2]])
                    irmCompoundTargetFound = True
            if irmCompoundTargetFound == False:
                IrmCompoundTargetWithoutEquivalence.append([irmCompoundElement[0],irmCompoundElement[1],irmCompoundElement[2]])

        # This block calculates the differences between the input shape graph compound targets that have an equivalence, and its complete compound target list. This is done for the creation of another list with the input shape graph compound targets which didn't have an equivalence in the IRM.
        for inputCompoundElement2 in InputCompoundTargets:
            inputCompoundTargetFound = False
            for inputCompoundElement3 in InputCompoundTargetWithEquivalence:
                if inputCompoundElement3[1] == inputCompoundElement2[1] and inputCompoundElement3[2] == inputCompoundElement2[2] :
                    inputCompoundTargetFound = True
            if inputCompoundTargetFound == False:
                InputCompoundTargetWithoutEquivalence.append([inputCompoundElement2[0],inputCompoundElement2[1],inputCompoundElement2[2]])

        # Insert simple shapes without equivalence from the current IRM in the updated IRM
        self.insertSimpleTargetsWithoutEquivalence(self.SHACL, updatedIRM, IrmNodeShapesSimpleTargetWithoutEquivalence)

        # Insert simple shapes without equivalence from the input shape graph in the updated IRM
        self.insertSimpleTargetsWithoutEquivalence(self.inputShapes, updatedIRM, InputNodeShapesSimpleTargetWithoutEquivalence)

        # Insert compound shapes without equivalence from input shape graph in the updated IRM
        #self.insertCompoundInputTargetsWithoutEquivalence(self.inputShapes, updatedIRM, IrmCompoundTargetWithoutEquivalence)
        self.insertCompoundInputTargetsWithoutEquivalence(self.inputShapes, updatedIRM, InputCompoundTargetWithoutEquivalence)

        # Insert compound shapes without equivalence from the  current IRMin the updated IRM
        #self.insertCompoundIRMTargetsWithoutEquivalence(self.SHACL, updatedIRM, InputCompoundTargetWithoutEquivalence)
        self.insertCompoundIRMTargetsWithoutEquivalence(self.SHACL, updatedIRM, IrmCompoundTargetWithoutEquivalence)

        # Insert the integration of the equivalent simple shapes
        self.integrateSimpleShapesWithEquivalence(self.inputShapes, self.SHACL, updatedIRM, IrmNodeShapesSimpleTargetWithEquivalence, InputNodeShapesSimpleTargetWithEquivalence)

        #print('graph before integration')
        #for triple in updatedIRM:
        #    print(triple)
        # Insert the integration of the equivalent compound shapes
        self.integrateCompoundShapesWithEquivalence(self.inputShapes, self.SHACL, updatedIRM, IrmCompoundTargetWithEquivalence, InputCompoundTargetWithEquivalence)

        #print('graph after integration')
        #for triple in updatedIRM:
        #    print(triple)

        # Set all the node shapes with sh:deactivated True
        self.deactivateShapesOfUpdatedIRM(updatedIRM)

        updatedIRM.serialize('C:/Users/micae/OneDrive - lifia.info.unlp.edu.ar/Documents/Doctorado/My research/Integration procedure/Implementation and experimentation/inputs/Integrations/Integration use case 1/Execution - Chamonix first/Execution - Annecy second/updatedIRM.ttl', format='turtle')

# Main program. Loads the input shape graphs in a List of shape graphs. (SCOOP)
if __name__ == "__main__":
    
    InputShape1Path = 'C:/Users/micae/OneDrive - lifia.info.unlp.edu.ar/Documents/Doctorado/My research/Integration procedure/Implementation and experimentation/inputs/Integrations/Integration use case 1/Execution - Chamonix first/Execution - Annecy second/Annecy.shacl'
    currentIrmPath = 'C:/Users/micae/OneDrive - lifia.info.unlp.edu.ar/Documents/Doctorado/My research/Integration procedure/Implementation and experimentation/inputs/Integrations/Integration use case 1/Execution - Chamonix first/Execution - Annecy second/currentIRM.ttl'

    InputShapeGraph = Graph()
    
    InputShapeGraph = Graph().parse(InputShape1Path, format='turtle')

    shapeIntegrator = ShapeIntegration(InputShapeGraph, currentIrmPath)
    shapeIntegrator.integration()