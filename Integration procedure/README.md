The implementation of the integration procedure has been done by using Python v3.13.1. In addition, the rdflib library (https://rdflib.readthedocs.io/en/stable/#) v7.1.1 has provided important functionalities for the manipulation of the IRM.
This implementation comprehends the following features so far:

- The shapes equivalence detection procedure, including the detection of simple and compound shapes equivalence. It's worth to mention that the implementation recognizes those property shapes which are defined as sh:property blankNode and expects a sh:targetClass definition in the defined node shapes. 
- The insertion of those shapes which don't have equivalence in the updated IRM.
- Integration of constraints for all the expected scenarios related to the structure of the temporal shapes.
	- Integration of simple shapes for the \textit{sh:nodeKind} constraint.
	- Integration of compound shapes for all the defined scenarios: Identical, Contradictory, Inconsistent, Independent, Unidirectional contained and Compatible with super predefined value,  including the following SHACL constraints: sh:nodeKind, sh:minCount, sh:maxCount, sh:minInclusive, sh:maxInclusive, sh:minLength, sh:maxLength, sh:hasValue, sh:in and sh:class.
