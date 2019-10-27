import os
from base64 import b64encode

from rdflib import *

import json
from io import StringIO

from whyis import nanopub

from whyis import autonomic
from whyis.test.agent_unit_test_case import AgentUnitTestCase

test_setl_script = """
@prefix rdf:           <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:          <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:           <http://www.w3.org/2001/XMLSchema#> .
@prefix owl:           <http://www.w3.org/2002/07/owl#> .
@prefix prov:          <http://www.w3.org/ns/prov#> .
@prefix dcat:          <http://www.w3.org/ns/dcat#> .
@prefix dcterms:       <http://purl.org/dc/terms/> .
@prefix void:          <http://rdfs.org/ns/void#> .
@prefix setl:          <http://purl.org/twc/vocab/setl/> .
@prefix csvw:          <http://www.w3.org/ns/csvw#> .
@prefix pv:            <http://purl.org/net/provenance/ns#> .
@prefix :              <http://example.com/setl/> .

:table a owl:Class, prov:SoftwareAgent, setl:PythonScript;
  rdfs:subClassOf prov:Activity;
  prov:value '''
import pandas as pd
table = pd.DataFrame({
  "ID":['Alice', 'Bob', 'Charles', 'Dave'],
  "Name" : ['Alice Smith', 'Bob Smith', 'Charles Brown', 'Dave Jones'],
  'MarriedTo' : ['Bob','Alice',None,None],
  'Knows' : ['Bob; Charles', 'Alice; Charles', 'Alice; Bob', None],
  'DOB' : ['1/12/1983', '3/23/1985', '12/15/1955', '4/25/1967']
})
result = table.iterrows()
'''.

:social_setl a setl:SemanticETLScript.

<http://example.com/social> a void:Dataset;
  prov:wasGeneratedBy :social_setl, [
    a setl:Transform, setl:JSLDT;
    prov:used :table;
    setl:hasContext '''{
  "foaf" : "http://xmlns.com/foaf/0.1/"
}''';
    prov:value '''[{
  "@id": "https://example.com/social/{{row.ID}}",
  "@type": "foaf:Person",
  "foaf:name": "{{row.Name}}",
  "http://schema.org/spouse": [{
    "@if" : "not isempty(row.MarriedTo)",
    "@id" : "https://example.com/social/{{row.ID}}"
  }],
  "foaf:knows": [{
    "@if" : "not isempty(row.Knows)",
    "@for" : "friend in row.Knows.split('; ')",
    "@do" : { "@id" : "https://example.com/social/{{friend}}" }
  }]
}]'''].
"""

class SETLRAgentTestCase(AgentUnitTestCase):

    def test_foaf_import(self):
        self.dry_run = False
        
        np = nanopub.Nanopublication()
        np.assertion.parse(data=test_setl_script, format="turtle")
        #print(np.serialize(format="trig"))
        agent = autonomic.SETLr()

        results = self.run_agent(agent, nanopublication=np)

        persons = list(self.app.db.subjects(RDF.type, URIRef('http://xmlns.com/foaf/0.1/Person')))
        self.assertEquals(len(persons), 4)

