from builtins import range
from builtins import object
import rdflib
import os
import collections
import requests
from dataurl import DataURLStorage
from werkzeug.utils import secure_filename

import tempfile

from depot.io.utils import FileIntent
from depot.manager import DepotManager

from datetime import datetime
import pytz

from whyis.namespace import np, prov, dc, frbr, whyis
from uuid import uuid4

from datastore import create_id
from .nanopublication import Nanopublication

from rdflib.plugins.serializers import nquads

class NanopublicationManager(object):
    def __init__(self, store, prefix, app, update_listener=None):
        self.db = rdflib.ConjunctiveGraph(store)
        self.store = store
        self.app = app
        #self.depot = DepotManager.get('nanopublications')
        self.prefix = rdflib.Namespace(prefix)
        self.update_listener = update_listener

    def new(self):
        fileid = self._reserve_id()
        nanopub = Nanopublication(identifier=self.prefix[fileid])
        nanopub.nanopub_resource
        nanopub.assertion
        nanopub.provenance
        nanopub.pubinfo

        return nanopub

    def _reserve_id(self):
        # This needs to be a two-step write, since we need to store
        # the identifier in the nanopub for consistency, and we don't
        # get the identifier until we write the file!
        #fileid = self.depot.create(FileIntent(b'', create_id(), 'application/trig'))
        
        return create_id()

    def prepare(self, source_graph):
        graph = rdflib.ConjunctiveGraph(store=source_graph.store)
        new_nps = [Nanopublication(store=graph.store, identifier=npuri)
                   for npuri in graph.subjects(rdflib.RDF.type, np.Nanopublication)]
        assertion_graphs = set([nanopub.assertion.identifier for nanopub in new_nps])
        provenance_graphs = set([nanopub.provenance.identifier for nanopub in new_nps])
        pubinfo_graphs = set([nanopub.pubinfo.identifier for nanopub in new_nps])
        all_np_graphs = set([x.identifier for x in new_nps])
        all_np_graphs = all_np_graphs.union(assertion_graphs)
        all_np_graphs = all_np_graphs.union(provenance_graphs)
        all_np_graphs = all_np_graphs.union(pubinfo_graphs)

        loose_graphs = list([c for c in graph.contexts() if c.identifier not in all_np_graphs and len(c) > 0])
        for context in loose_graphs:
            new_np = Nanopublication(store=context.store, identifier=self.prefix[create_id()])
            if isinstance(context.identifier, rdflib.BNode):
                g = rdflib.Graph(store=context.store, identifier=new_np.assertion.identifier)
                g += context
                context.remove((None, None, None))
            else:
                new_np.add((new_np.identifier, np.hasAssertion, context.identifier))
                new_np.add((new_np.identifier, rdflib.RDF.type, np.Nanopublication))
                new_np.add((graph.identifier, rdflib.RDF.type, np.Assertion))
            new_np.assertion
            new_np.provenance
            new_np.pubinfo
            new_nps.append(new_np)

        i = 0
        remap_graphs = {}
        for nanopub in new_nps:
            i += 1
            new_np = nanopub
            if isinstance(nanopub.identifier, rdflib.BNode):
                new_np = Nanopublication(store=graph.store, identifier=self.prefix[create_id()])
                remap_graphs[nanopub.identifier] = new_np.identifier
            for identifier, suffix in [(nanopub.assertion.identifier, '_assertion'),
                                       (nanopub.provenance.identifier, '_provenance'),
                                       (nanopub.pubinfo.identifier, '_pubinfo')]:
                if isinstance(identifier, rdflib.BNode):
                    old_id = identifier
                    new_id = new_np.identifier+suffix
                    remap_graphs[old_id] = new_id
        for old, new in remap_graphs.items():
            old_g = rdflib.Graph(store=graph.store, identifier=old)
            new_g = rdflib.Graph(store=graph.store, identifier=new)
            new_g += old_g
            graph.remove_context(old_g)

            for s, p, o, g in graph.quads((old, None, None, None)):
                graph.add((new,p,o,g))
                graph.remove((s,p,o,g))
            # Predicates can't be bnodes.
            for s, p, o, g in graph.quads((None, None, old, None)):
                graph.add((s,p,new,g))
                graph.remove((s,p,o,g))
                
            #if nanopub.pubinfo.value(nanopub.identifier, frbr.realizationOf) is None:
            #    work = self.prefix[create_id()]
            #    nanopub.pubinfo.add((nanopub.identifier, frbr.realizationOf, work))
            #    nanopub.pubinfo.add((work, rdflib.RDF.type, frbr.Work))
            #    nanopub.pubinfo.add((nanopub.identifier, rdflib.RDF.type, frbr.Expression))
            # print "Total", len(output_graph)
            # print "Contexts", [g.identifier for g in output_graph.contexts()]

        for npuri in graph.subjects(rdflib.RDF.type, np.Nanopublication):
            yield Nanopublication(store=graph.store, identifier=npuri)

    def retire(self, *nanopub_uris):
        self.db.store.nsBindings = {}
        #graphs = []
        derived_query = '''select ?np where {
  ?np (np:hasAssertion/prov:wasDerivedFrom+/^np:hasAssertion)? ?r.
  ?np a np:Nanopublication.
''' + ('' if self.app.config.get('delete_archive_nanopubs',True) else 'minus { ?np a whyis:FRIRNanopublication }') + '''
}'''
        for nanopub_uri in nanopub_uris:
            for np_uri, in self.db.query(derived_query,
                                         initNs={"prov": prov, "np": np, "whyis" : whyis},
                                         initBindings={"r": nanopub_uri}):
                #graphs.extend([np_uri, assertion, provenance, pubinfo])
                nanopub = Nanopublication(store=self.db.store, identifier=np_uri)
                
                for fileid in nanopub.objects(predicate=whyis.hasFileID):
                    if self.app.file_depot.exists(fileid):
                        self.app.file_depot.delete(fileid)
                    elif self.app.nanopub_depot.exists(fileid):
                        f = self.app.nanopub_depot.delete(fileid)                    
                self.db.remove((None, None, None, nanopub.assertion.identifier))
                self.db.remove((None, None, None, nanopub.provenance.identifier))
                self.db.remove((None, None, None, nanopub.pubinfo.identifier))
                self.db.remove((None, None, None, nanopub.identifier))
        self.db.commit()
        # data = [('c', c.n3()) for c in graphs]
        # session = requests.session()
        # session.keep_alive = False
        # session.delete(self.db.store.endpoint, data=[('c', c.n3()) for c in graphs])

    def is_current(self, nanopub_uri):
        return (rdflib.URIRef(nanopub_uri), rdflib.RDF.type, np.Nanopublication) in self.db

    def get_path(self, nanopub_uri):
        # print self.prefix, nanopub_uri
        ident = nanopub_uri.replace(self.prefix, "")
        dir_name_length = 3
        path = [ident[i:i + dir_name_length] for i in range(0, len(ident), dir_name_length)]
        return [self.archive_path] + path[:-1] + [ident]

    def publish(self, *nanopubs):
        # self.db.store.nsBindings = {}
        stores = set()
        full_list = []
        with open(self.app.config['load_dir']+'/'+create_id()+'.nq', 'a+b') if 'load_dir' in self.app.config else tempfile.NamedTemporaryFile(delete=True) as data:
            to_retire = set([x.identifier for x in nanopubs])
            for npg in nanopubs:
                stores.add(npg.store)
                if isinstance(npg, Nanopublication):
                    to_process = [npg]
                else:
                    to_process = [Nanopublication(store=npg.store, identifier=npuri)
                                  for npuri in npg.subjects(rdflib.RDF.type, np.Nanopublication)]
                for np_graph in to_process:
                    for entity in np_graph.assertion.subjects(self.app.NS.whyis.hasContent):
                        localpart = self.db.qname(entity).split(":")[1]
                        filename = secure_filename(localpart)
                        f = DataURLStorage(np_graph.value(entity, self.app.NS.whyis.hasContent), filename=filename)
                        print('adding file', filename)
                        self.app.add_file(f, entity, np_graph)
                        np_graph.assertion.remove((entity, self.app.NS.whyis.hasContent, None))

                    r = False
                    now = rdflib.Literal(datetime.utcnow())
                    for part in [np_graph.assertion.identifier,
                                np_graph.pubinfo.identifier,
                                np_graph.provenance.identifier]:
                        np_query = '''select ?np where { ?np np:hasAssertion|np:hasProvenance|np:hasPublicationInfo ?x}'''
                        replacing = [x for x, in self.db.query(np_query, initNs=dict(np=np), initBindings=dict(x=part))]
                        to_retire = to_retire.union(replacing)
                    
                    for revised in np_graph.pubinfo.objects(np_graph.assertion.identifier, prov.wasRevisionOf):
                        for nanopub_uri in self.db.subjects(predicate=np.hasAssertion, object=revised):
                            np_graph.pubinfo.set((nanopub_uri, prov.invalidatedAtTime, now))
                            to_retire.add(nanopub_uri)
                            r = True
                            print("Retiring", nanopub_uri)
                    if r:
                        np_graph.pubinfo.set((np_graph.assertion.identifier, dc.modified, now))
                    else:
                        np_graph.pubinfo.set((np_graph.assertion.identifier, dc.created, now))
                    full_list.append(np_graph.identifier)

            bnode_cache = {}
            def skolemize(x):
                if isinstance(x, rdflib.BNode):
                    if x not in bnode_cache:
                        bnode_cache[x] = rdflib.URIRef('bnode:' + uuid4().hex)
                    return bnode_cache[x]
                return x
            for store in stores:
                for s, p, o, c in rdflib.ConjunctiveGraph(store).quads():
                    if self.app.config.get('BNODE_REWRITE', False):
                        s = skolemize(s)
                        o = skolemize(o)
                        # predicates can't be bnodes, and contexts have already been rewritten.
                    row = nquads._nq_row((s,p,o), c.identifier).encode('utf8')
                    data.write(row)
                data.write(b'\n')
                data.flush()
                # np_graph.serialize(data, format="trig")
                # data.write('\n')
                # data.flush()
                # print data.name
                # np_graph.serialize(data, format="trig")
                # data.write('\n')
                # data.flush()
            self.retire(*to_retire)
            data.seek(0)
            self.db.store.publish(data)

        for n in full_list:
            self.update_listener(n)

    _idmap = {}

    def get(self, nanopub_uri, graph=None):
        nanopub_uri = rdflib.URIRef(nanopub_uri)
        
        if graph is None:
            graph = rdflib.ConjunctiveGraph()

        quads = self.db.query('''select ?s ?p ?o ?g where {
        ?np np:hasAssertion?|np:hasProvenance?|np:hasPublicationInfo? ?g.
        graph ?g { ?s ?p ?o}
        }''', initNs={'np':np}, initBindings={'np':nanopub_uri})
        for s, p, o, g in quads:
            if self.app.config.get('BNODE_REWRITE', False):
                if isinstance(s, rdflib.URIRef) and s.startswith('bnode:'):
                    s = rdflib.BNode(s.replace('bnode:','',1))
                if isinstance(o, rdflib.URIRef) and o.startswith('bnode:'):
                    o = rdflib.BNode(o.replace('bnode:','',1))
            graph.add((s,p,o,g))
        nanopub = Nanopublication(store=graph.store, identifier=nanopub_uri)
        return nanopub
