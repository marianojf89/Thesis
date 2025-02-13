from rdflib import Graph, Namespace, URIRef, Literal, BNode
import time

start_time = time.time()

rdfSyntax = Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
owlSyntax = Namespace('http://www.w3.org/2002/07/owl#')
shaclSyntax = Namespace('http://www.w3.org/ns/shacl#')

## Set input files
InputRDFdata = 'pathToRDFgraphWhichContainsTheContextKnowledge'
InputOntologyContext = 'pathToTheOntologyContext'
OutputSubOntologyContext = 'pathToDepositTheSubOntologyThatMatchesTheContext'
CurrentIRM = 'pathToTheCurrentIRMversion'
updatedIRMfile = 'pathToDepositTheConfiguredIRM'

### Set the RDF graph which has the active context
InputRDFdataGraph = Graph()
InputRDFdataGraph = Graph().parse(InputRDFdata, format='turtle')

### Set the graph which has the context ontology
InputOntologyContextGraph = Graph()
InputOntologyContextGraph = Graph().parse(InputOntologyContext, format='turtle')

### Set the current IRM graph
InputCurrentIRMGraph = Graph()
InputCurrentIRMGraph = Graph().parse(CurrentIRM, format='turtle')

### Query for retrieving the active context from the RDF
firstContextQuery = """
PREFIX : <http://www.semanticweb.org/esfvel_context#>

SELECT ?subject
WHERE { ?subject a :Context ; 
:Current_Status :Active . }"""

## Retrieve the active context from the RDF
qres = InputRDFdataGraph.query(firstContextQuery)
for row in qres:
    activeContext = row.subject

### Query for retrieving the subgraph of the ontology which has the characteristics related to the active context
secondContextQuery = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX onto: <http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/>
CONSTRUCT { 
    ?class rdf:type owl:class .
    ?class ?path ?constraint1 . 
	?constraint1 ?property ?constraint2 . }
WHERE { 
SELECT ?class ?path ?property ?constraint2  ?constraint1
	WHERE { ?subject onto:related_to_context ?context .
		?subject rdf:type ?class .
		?context rdf:type onto:Context .
		?class owl:equivalentClass ?characteristics .
?characteristics owl:intersectionOf ?Bnode1 .
?Bnode1 rdf:rest ?Bnode2 .
?Bnode2 rdf:first ?constraint1 .
?constraint1 ?property ?constraint2 .
?constraint1 owl:onProperty ?path .
FILTER( regex(str(?class), "^(?!http://www.w3.org/2002/07/owl#).+")) .
FILTER( regex(str(?class), "^(?!http://www.w3.org/1999/02/22-rdf-syntax-ns#).+")) .
FILTER( regex(str(?class), "^(?!http://www.w3.org/2000/01/rdf-schema#).+")) .
FILTER( str(?context) != ?activeContext)  . # This value comes from an input parameter.
FILTER NOT EXISTS { ?constraint1 rdf:type ?constraint2 . }
FILTER NOT EXISTS { ?constraint1 owl:onProperty ?constraint2 . }
}
}"""

## Retrieve the subgraph of the ontology which has the characteristics related to the active context
qres2 = InputOntologyContextGraph.query(secondContextQuery, initBindings={"activeContext": Literal(activeContext)})
InputOntologyContextSUBGraph = Graph()
for row2 in qres2:
    InputOntologyContextSUBGraph.add(row2)
InputOntologyContextSUBGraph.serialize(destination=OutputSubOntologyContext,format="ttl")

subContextOntologyRetrieved = []

## From the subgraph of the ontology, retrieve [[class, path], [constraint1, constraintValue1], [constraint2, constraintValue2],...,['end','end'],[class2, path2],...)
for s,p,o in InputOntologyContextSUBGraph.triples((None, rdfSyntax.type, None)):
    for s1,p1,o1 in InputOntologyContextSUBGraph.triples((s, None, None)):
          if p1 != rdfSyntax.type:
                subContextOntologyRetrieved.append([s,p1])
                for s2,p2,o2 in InputOntologyContextSUBGraph.triples((o1, None, None)):
                     subContextOntologyRetrieved.append([p2,o2])
                subContextOntologyRetrieved.append(['end','end'])

### Query for retrieveing those shapes from the IRM which accomplish the context characteristics
IRMcontextBaseQuery = """
PREFIX sh: <http://www.w3.org/ns/shacl#> 
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> 
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#> 
PREFIX ex: <http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/> 

SELECT ?nodeShape 
WHERE { ?nodeShape a sh:NodeShape . 
?nodeShape sh:targetClass ?focusClass . 
?nodeShape sh:property ?blankNodePath .
?blankNodePath sh:path ?path .
?blankNodePath ?constraintProperty ?constraintValue .
OPTIONAL{?constraintValue ?constraintTypeValueCompound ?constraintValueValueCompound}
  FILTER( str(?focusClass) = str(?varInputClass) ) .  
  FILTER( str(?path) = str(?varInputPath)  ) . 
"""

IRMcontextNewQuery = IRMcontextBaseQuery

### Query for activating those shapes from the IRM which accomplish the context characteristics
IRMupdateQuery = """
PREFIX sh: <http://www.w3.org/ns/shacl#> 
PREFIX ex: <http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/> 

DELETE { ?nodeShape sh:deactivated true . }
INSERT { ?nodeShape sh:deactivated false . }
WHERE
  { ?nodeShape sh:deactivated true .
    FILTER( str(?nodeShape) = str(?nodeShapeIRI) ) . # Input parameter
  } 
"""

### Query for retrieving those shapes of a group which haven't accomplished the context characteristics in a group in which at least one shape have accomplished them.
IRMcomplementGroupQueryBase = """
PREFIX sh: <http://www.w3.org/ns/shacl#> 
PREFIX ex: <http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/> 

SELECT DISTINCT ?nodeShape 
WHERE { ?nodeShape a sh:NodeShape . 
?nodeShape sh:targetClass ?focusClass . 
?nodeShape sh:property ?blankNodePath .
?blankNodePath sh:path ?path .
  FILTER( str(?focusClass) = str(?varInputClass) ) .  
  FILTER( str(?path) = str(?varInputPath)  ) . 
"""

IRMcontextNewQuery = IRMcontextBaseQuery

### Query for deactivating from the IRM the complement shapes of a group
IRMupdateDeactivateComplementQuery = """
PREFIX sh: <http://www.w3.org/ns/shacl#> 
PREFIX ex: <http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/> 

DELETE { ?nodeShape sh:deactivated false . }
INSERT { ?nodeShape sh:deactivated true . }
WHERE
  { ?nodeShape sh:deactivated false .
    FILTER( str(?nodeShape) = str(?nodeShapeIRI) ) . # Input parameter
  } 
"""

## Create the query to consult the IRM based on the subgraph ontology list [[class, path], [constraint1, constraintValue1], [constraint2, constraintValue2],...,['end','end']
counter = 0
for listPosition in subContextOntologyRetrieved:
      ## Start of a group
      if counter == 0:
            focusClass = listPosition[0]
            path = listPosition[1]
            counter = counter + 1
            filterLine = ''
            retrieveIRMcontext = []
      else:
            ## Constraints found
            if listPosition[0] != 'end':
                  counter = counter + 1
                  owlConstraintType = listPosition[0]
                  owlConstraintValue = listPosition[1]
                  IRMcontextNewQuery = IRMcontextBaseQuery
                  ## Add filter line to reuse the results of the previous execution (if there's any nodeShape that accomplished those constraints)
                  if len(retrieveIRMcontext) > 0:
                       nodeShapeIRIleft = ''
                       for nodeShapeResult in retrieveIRMcontext:
                            nodeShapeIRIleft = nodeShapeIRIleft + '\'' + nodeShapeResult[0] + '\','
                       nodeShapeIRIleftIndex = nodeShapeIRIleft.rfind(',')
                       nodeShapeIRIleftFinal = nodeShapeIRIleft[:nodeShapeIRIleftIndex]
                       filterPreviousObtainedShapes = 'FILTER( str(?nodeShape) in (' + nodeShapeIRIleftFinal + ') ) . \n'
                       IRMcontextNewQuery = IRMcontextNewQuery + filterPreviousObtainedShapes
                  ## Add more constraints and find out if there are shapes of this group which accomplish them
                  if owlConstraintType == owlSyntax.maxQualifiedCardinality:
                       irmConstraintType = str(shaclSyntax.qualifiedMaxCount)
                       ## Create FILTER line with the specific constraint and add it to the new query (baseQuery + Filter lines)
                       filterLine = 'FILTER( str(?constraintProperty) = \'' + irmConstraintType + '\' && ?constraintValue <= ' + owlConstraintValue + ' ) }'
                       IRMcontextNewQuery = IRMcontextNewQuery + filterLine
                       ## Retrieve shapes which accomplish to this constraint
                       retrieveIRMcontext = InputCurrentIRMGraph.query(IRMcontextNewQuery, initBindings={"varInputClass": Literal(focusClass), "varInputPath": Literal(path)})
                  if owlConstraintType == owlSyntax.minQualifiedCardinality:
                       irmConstraintType = str(shaclSyntax.qualifiedMinCount)
                       filterLine = 'FILTER( str(?constraintProperty) = \'' + irmConstraintType + '\' && ?constraintValue >= ' + owlConstraintValue + ' ) }'
                       IRMcontextNewQuery = IRMcontextNewQuery + filterLine
                       retrieveIRMcontext = InputCurrentIRMGraph.query(IRMcontextNewQuery, initBindings={"varInputClass": Literal(focusClass), "varInputPath": Literal(path)})
                  ## sh:qualifiedValueShape [ sh:class ex:Student ])
                  elif owlConstraintType == owlSyntax.onClass:
                       irmConstraintType = str(shaclSyntax["class"])
                       filterLine = 'FILTER( str(?constraintTypeValueCompound) = \'' + irmConstraintType + '\' && str(?constraintValueValueCompound) = \'' + owlConstraintValue + '\' ) }'
                       IRMcontextNewQuery = IRMcontextNewQuery + filterLine
                       retrieveIRMcontext = InputCurrentIRMGraph.query(IRMcontextNewQuery, initBindings={"varInputClass": Literal(focusClass), "varInputPath": Literal(path)})
                  elif owlConstraintType == owlSyntax.maxCardinality:
                       irmConstraintType = str(shaclSyntax["maxCount"])
                       filterLine = 'FILTER( str(?constraintProperty) = \'' + irmConstraintType + '\' && ?constraintValue <= ' + owlConstraintValue + ' ) }'
                       IRMcontextNewQuery = IRMcontextNewQuery + filterLine
                       retrieveIRMcontext = InputCurrentIRMGraph.query(IRMcontextNewQuery, initBindings={"varInputClass": Literal(focusClass), "varInputPath": Literal(path)})
                  elif owlConstraintType == owlSyntax.minCardinality:
                       irmConstraintType = str(shaclSyntax["minCount"])
                       filterLine = 'FILTER( str(?constraintProperty) = \'' + irmConstraintType + '\' && ?constraintValue >= ' + owlConstraintValue + ' ) }'
                       IRMcontextNewQuery = IRMcontextNewQuery + filterLine
                       retrieveIRMcontext = InputCurrentIRMGraph.query(IRMcontextNewQuery, initBindings={"varInputClass": Literal(focusClass), "varInputPath": Literal(path)})
            else:
                 ## End of the group treatment
                 counter = 0
                 # if len(retrieveIRMcontext) > 0 = Execute the activation of the shapes that accomplished the context characteristics.
                 # The values in ?focusClass and ?path represent the current respective group (focusClass, path)
                 # The values in retrieveIRMcontext are the nodeShapeIRIs which must be activated.
                 # The rest of the nodeShapeIRIs in the current respective group (focusClass, path) (complement shapes) must be deactivated.
                 if len(retrieveIRMcontext) > 0:
                    nodeShapeIRIcomplement = ''
                    ## Activation of the shapes that accomplished the context characteristics.
                    for nodeShapeIRI in retrieveIRMcontext:
                         nodeShapeIRIcomplement = nodeShapeIRIcomplement + '\'' + nodeShapeIRI[0] + '\','
                         InputCurrentIRMGraph.update(IRMupdateQuery, initBindings={"nodeShapeIRI": nodeShapeIRI[0]})
                    ## Retrieve from the group, the complement of shapes which haven't passed the context requirements.
                    nodeShapeIRIcomplementIndex = nodeShapeIRIcomplement.rfind(',')
                    nodeShapeIRIcomplementFinal = nodeShapeIRIcomplement[:nodeShapeIRIcomplementIndex]
                    filterComplementShapes = 'FILTER( str(?nodeShape) not in (' + nodeShapeIRIcomplementFinal + ') ) . } \n'
                    IRMcomplementGroupQuery = IRMcomplementGroupQueryBase + filterComplementShapes
                    IRMcomplementGroupShapes = InputCurrentIRMGraph.query(IRMcomplementGroupQuery, initBindings={"varInputClass": Literal(focusClass), "varInputPath": Literal(path)})
                    ## Deactivate the complement shapes of the group
                    if len(IRMcomplementGroupShapes) > 0:
                        for complementShape in IRMcomplementGroupShapes:
                            InputCurrentIRMGraph.update(IRMupdateDeactivateComplementQuery, initBindings={"nodeShapeIRI": complementShape[0]})

### Query for detecting those shapes which are unique in their groups
IRMdetectUniqueGroupShapesQuery = """
PREFIX sh: <http://www.w3.org/ns/shacl#> 
PREFIX ex: <http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/> 

SELECT ?nodeShape
WHERE { ?nodeShape a sh:NodeShape . 
?nodeShape sh:targetClass ?focusClass . 
?nodeShape sh:property ?blankNodePath .
?blankNodePath sh:path ?path .
}
GROUP BY ?focusClass ?path
HAVING(COUNT(?nodeShape) = 1)
"""

## Activate those shapes from the IRM which are unique in their groups
IRMuniqueGroupShapes = InputCurrentIRMGraph.query(IRMdetectUniqueGroupShapesQuery)
for uniqueShape in IRMuniqueGroupShapes:
     InputCurrentIRMGraph.update(IRMupdateQuery, initBindings={"nodeShapeIRI": uniqueShape[0]})

### Query for detecting the simple node shapes
IRMdetectSimpleNodeShapesQuery = """
PREFIX sh: <http://www.w3.org/ns/shacl#> 
PREFIX ex: <http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/> 

SELECT ?nodeShape
WHERE { ?nodeShape a sh:NodeShape . 
  FILTER NOT EXISTS { ?nodeShape ?property ?object .
  ?object sh:group ?groupValue . } .
}
"""

## Activate the simple node shapes
IRMsimpleNodeShapes = InputCurrentIRMGraph.query(IRMdetectSimpleNodeShapesQuery)
for uniqueShape in IRMsimpleNodeShapes:
     InputCurrentIRMGraph.update(IRMupdateQuery, initBindings={"nodeShapeIRI": uniqueShape[0]})

### Query for retrieving those groups which need a decision from the user, meaning those shapes which are active and are not the unique active shapes in their respective group
IRMcandidateGroupShapesFiltered = """
PREFIX sh: <http://www.w3.org/ns/shacl#> 

SELECT ?focusClass ?path
WHERE { ?nodeShape a sh:NodeShape . 
?nodeShape sh:targetClass ?focusClass . 
?nodeShape sh:deactivated false .
?nodeShape sh:property ?blankNodePath .
?blankNodePath sh:path ?path .
}
GROUP BY ?focusClass ?path
HAVING(COUNT(?nodeShape) > 1)
"""

### Query for retrieving those candidate node shapes which need a decision from the user, meaning those shapes which are active and are not the unique active shapes in their respective group
IRMcandidateShapesFiltered = """
PREFIX sh: <http://www.w3.org/ns/shacl#> 
PREFIX ex: <http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/> 

SELECT ?nodeShape
WHERE { ?nodeShape a sh:NodeShape . 
?nodeShape sh:targetClass ?focusClass . 
?nodeShape sh:deactivated false .
?nodeShape sh:property ?blankNodePath .
?blankNodePath sh:path ?path .
FILTER( str(?focusClass) = str(?varInputClass) ) .  
FILTER( str(?path) = str(?varInputPath)  ) . 
}
"""

### Retrieve those candidate shapes which need a decision from the user, meaning those shapes which are active and are not the unique active shapes in their respective group
## The respective nodeShapes are saved in the list candidateNodeShapesContextualized (*** This list will be sent to the user ***)
IRMgroupWithCandidatesContextualized = InputCurrentIRMGraph.query(IRMcandidateGroupShapesFiltered)
candidateNodeShapesContextualized = []
for group in IRMgroupWithCandidatesContextualized:
     NodeShapesContextualized = InputCurrentIRMGraph.query(IRMcandidateShapesFiltered, initBindings={"varInputClass": Literal(group[0]), "varInputPath": Literal(group[1])})
     for nodeShape in NodeShapesContextualized:
          candidateNodeShapesContextualized.append([nodeShape[0]])

### Retrieve the shapes from the groups which have all the shapes deactivated, meaning candidate shapes of a group which wasn't filtered by the context.
## Firstly retrieve those groups which have more than one shape (focusClass,pathValue)
IRMGroupsWithMultipleShapesQuery = """
PREFIX sh: <http://www.w3.org/ns/shacl#> 

SELECT ?focusClass ?path
WHERE { ?nodeShape a sh:NodeShape . 
?nodeShape sh:targetClass ?focusClass . 
?nodeShape sh:property ?blankNodePath .
?blankNodePath sh:path ?path . }
GROUP BY ?focusClass ?path
HAVING(COUNT(?nodeShape) > 1)
"""

IRMGroupsWithMultipleShapes = InputCurrentIRMGraph.query(IRMGroupsWithMultipleShapesQuery)
## Secondly retrieve those groups which have multiple shapes and all of them are deactivated
groupsWithMultipleShapesAllDeactivated = []
for group in IRMGroupsWithMultipleShapes:
     lookForActiveShapes = InputCurrentIRMGraph.query(IRMcandidateShapesFiltered, initBindings={"varInputClass": Literal(group[0]), "varInputPath": Literal(group[1])})
     if len(lookForActiveShapes) == 0:
          groupsWithMultipleShapesAllDeactivated.append([group[0], group[1]])

### Finally, retrieve the related list of nodeShapes of those groups which have multiple shapes and they are all deactivated.
## The list of nodeShape IRIs nodeShapesOfGroupsWithMultipleShapesAllDeactivated will be sent to the user
nodeShapesOfGroupsWithMultipleShapesAllDeactivated = []
IRMqueryNodeShapesOfGroup = IRMcomplementGroupQueryBase + ' }'
for group2 in groupsWithMultipleShapesAllDeactivated:
     groupNodeShapes = InputCurrentIRMGraph.query(IRMqueryNodeShapesOfGroup, initBindings={"varInputClass": Literal(group2[0]), "varInputPath": Literal(group2[1])})
     for nodeShape in groupNodeShapes:
          nodeShapesOfGroupsWithMultipleShapesAllDeactivated.append([nodeShape[0]])

### ...
### ...

#### After sending the reports to the user (corresponding to the two lists, one of the contextualized candidate shapes and the other of the not filtered candidate shapes), two lists of nodeShape IRIs which represent the user's selections are received, which must be activated in their groups.

### In the case of the candidateNodeShapesContextualized, the candidate shapes are active. In consequence, the candidates which were not selected for a group must be deactivated.
## The answer from the user is received as a list candidateShapeSelected = [selectedNodeShapeIRI, groupClass, groupPathValue],[selectedNodeShapeIRI2, groupClass2, groupPathValue2],...

## Query for retrieving those candidate node shapes which are active and were not selected by the user
IRMcandidateShapesNotSelected = """
PREFIX sh: <http://www.w3.org/ns/shacl#> 
PREFIX ex: <http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/> 

SELECT ?nodeShape
WHERE { ?nodeShape a sh:NodeShape . 
?nodeShape sh:targetClass ?focusClass . 
?nodeShape sh:deactivated false .
?nodeShape sh:property ?blankNodePath .
?blankNodePath sh:path ?path .
FILTER( str(?focusClass) = str(?varInputClass) ) .  
FILTER( str(?path) = str(?varInputPath)  ) . 
FILTER( str(?nodeShape) != str(?selectedNodeShape)  ) . 
}
"""

## Find those candidate shapes which were not selected by the user
candidateShapeSelected = []
# Simulation of the candidateShapeSelected list that would be received from the user
candidateShapeSelected.append(['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Student_has_insurance_sup', 'http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Student', 'http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/has_insurance'])
for usersDecision in candidateShapeSelected:
     notSelectedNodeShapes = InputCurrentIRMGraph.query(IRMcandidateShapesNotSelected, initBindings={"varInputClass": Literal(usersDecision[1]), "varInputPath": Literal(usersDecision[2]), "selectedNodeShape": Literal(usersDecision[0])})
## Deactivate those candidate shapes which were not selected by the user
for notSelectedNodeShapeIRI in notSelectedNodeShapes:
     InputCurrentIRMGraph.update(IRMupdateDeactivateComplementQuery, initBindings={"nodeShapeIRI": notSelectedNodeShapeIRI[0]})


### In the case of the nodeShapesOfGroupsWithMultipleShapesAllDeactivated list, the candidate shapes are deactivated. In consequence, the shapes which are selected by the user must be activated.
## The answer from the user is received as a list notFilteredGroupShapeSelected = [selectedNodeShapeIRI],[selectedNodeShapeIRI2],...

# Simulation of the nodeShapesOfGroupsWithMultipleShapesAllDeactivated list that would be received from the user
notFilteredGroupShapeSelected = []
notFilteredGroupShapeSelected = ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/CompetitionLesson_competitionAssociated_sup'],['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/GroupLesson_belongs_to_discipline_sup'],['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/GroupLesson_end_time_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/GroupLesson_given_in_language_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/GroupLesson_has_teachingLevel_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/GroupLesson_start_time_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Hotel_address_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Instructor_name_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Instructor_teaches_in_language_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Instructor_teaches_in_school_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Instructor_teaches_level_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Insurance_coverage_level_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Insurance_has_description_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Kindergarten_ages_welcome_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/MeetingPoint_Meeting_point_of_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Package_has_service_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/PrivateLesson_belongs_to_discipline_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/PrivateLesson_given_in_language_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/SkiRental_available_utils_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Student_has_age_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Student_inscribed_in_lesson_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/Student_learned_level_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/TeachingLanguage_has_country_provenance_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/TeachingSchool_closes_at_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/TeachingSchool_has_meetingPoint_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/TeachingSchool_offers_discipline_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/TeachingSchool_opens_at_sup'], ['http://www.semanticweb.org/valraiso/ontologies/2024/1/esfvel_ontology/TestLesson_lesson_type_sup']

## Activate those shapes of the not filtered groups which were selected by the user
for SelectedNodeShapeIRI in notFilteredGroupShapeSelected:
     InputCurrentIRMGraph.update(IRMupdateQuery, initBindings={"nodeShapeIRI": SelectedNodeShapeIRI[0]})

## Save the activated version of the IRM in the file
InputCurrentIRMGraph.serialize(destination=updatedIRMfile,format="ttl")

end_time = time.time()
execution_time = end_time - start_time
print(f"Execution time: {execution_time:.4f} seconds")
