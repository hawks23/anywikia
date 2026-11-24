"""Disposable browser fixture: real HTTP/write logic with an in-memory RDF backend.

No Docker, CampusAI or repository RDF is modified. For manual/automated UI smoke
testing run `python -m tests.browser_fixture`, then open port 8012.
"""
import tempfile
from http.server import ThreadingHTTPServer

import web_app
from functions import rdf_service
from functions.rdf_models import property_catalog, KB, UNIT_BASE
from functions.rdf_store import RDFStore, add_statement, predicate
from rdflib import Literal, URIRef, XSD
from tests.test_rdf_writes import MemoryRuntime


def sample_entity(name, qid, claims):
    properties = {p["field"]: {"property_id":p["property_id"], "label":p["label"], "value_type":p["value_type"], "claims":[]} for p in property_catalog()}
    for field, value, unit in claims:
        properties[field]["claims"].append({"value":value,"unit":unit,"evidence":"Fixture source", "warnings":[], "value_candidates":[], "value_id":"Q2" if field == "manufacturer" else None})
    return {"name":name,"subject_id":qid,"subject_candidates":[{"id":qid,"name":name}] if qid else [],"warnings":[],"properties":properties}


def main():
    with tempfile.TemporaryDirectory() as directory:
        runtime = MemoryRuntime(directory)
        add_statement(runtime.graph, KB.Q1, "P2", Literal("80",datatype=XSD.decimal), URIRef(UNIT_BASE+"Q174728"), "old width", URIRef("urn:fixture"), "fixture", False)
        rdf_service.runtime = runtime; rdf_service.store = RDFStore(runtime)
        rdf_service.status = lambda: {"ready":True,"message":"","properties":property_catalog(),"rebuild":None,"endpoint":"in-memory test"}
        web_app.extract = lambda text: {"entities":[
            sample_entity("Keyboard","Q1",[("keys","61",None),("width","81","cm"),("manufacturer","Maker",None)]),
            sample_entity("Test Synth",None,[("keys","73",None)])]}
        web_app.add_name_suggestions = lambda result: result
        def inspect(qid):
            rows = []
            for p in property_catalog():
                for value in runtime.graph.objects(KB[qid],predicate("direct/",p["property_id"])):
                    rows.append({"property":{"type":"uri","value":str(KB[p['property_id']])},"value":{"type":"literal","value":str(value)}})
            return {"id":qid,"properties":rows}
        web_app.inspect_entity = inspect
        print("Disposable browser fixture http://127.0.0.1:8012",flush=True)
        ThreadingHTTPServer(("127.0.0.1",8012),web_app.Handler).serve_forever()


if __name__ == "__main__": main()
