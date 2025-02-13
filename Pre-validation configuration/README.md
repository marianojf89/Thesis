This folder contains the pre-validation configuration process, which comprehends the following tasks defined in the thesis:

- Retrieve the active context from the RDF Data graph.
- Retrieve the ontology sub-graph which has the characteristics related to the active context.
- Retrieve and activate those shapes from the IRM which accomplish the contextual characteristics. This task includes the translation of elements from OWL to SHACL, more specifically of the properties owl:minCount and owl:maxCount.
- Detect and activate those shapes from the IRM which are unique in their groups.
- Retrieve those candidate node shapes which need a decision from the user, meaning those shapes which are active and are not the unique active shapes in their respective group.
- Retrieve the shapes from the groups which have all the shapes deactivated, meaning candidate shapes of a group which wasn't filtered by the context.
- Once the user selected which candidate shapes are decided to have active, process this list of shapes and activate them.

In summary, the implementation comprehends the interaction of the IRM manager with all the involved models, and includes an interesting set of actions for the configuration of the IRM. However, there are parts of the workflow which development is still in progress, such as adding the detection and translation of more constraint types (OWL-SPARQL), the generation of the validation reports, the construction of the reports based on them and finally the interaction with the user through an interface.
