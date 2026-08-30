"""Guard tests that keep the public ontology diagram/data model page
(eval_boards/index.html + eval_boards/data/datamodel.json) from drifting out
of sync with the ontology YAML, since the SVG diagram is hand-authored and
the tables are transcribed by hand rather than templated at build time."""

from pathlib import Path

from ontology.describe import build_datamodel
from ontology.schema import load_ontology

SVG_PATH = Path(__file__).resolve().parents[2] / "eval_boards" / "index.html"


def test_datamodel_covers_every_object_type_and_link(ontology, db_connection):
    datamodel = build_datamodel(ontology, db_connection)

    datamodel_types = {o["name"] for o in datamodel["object_types"]}
    assert datamodel_types == set(ontology.object_types)

    datamodel_links = {(l["source"], l["name"], l["target"]) for l in datamodel["links"]}
    ontology_links = {(link.from_, link.name, link.to) for link in ontology.links}
    assert datamodel_links == ontology_links


def test_svg_names_every_object_type_and_link():
    ontology = load_ontology()
    svg_markup = SVG_PATH.read_text()

    for object_type_name in ontology.object_types:
        assert object_type_name in svg_markup, (
            f"object type '{object_type_name}' does not appear in the "
            f"ontology diagram SVG ({SVG_PATH}) — the diagram is hand-"
            "authored and must be updated to match the ontology"
        )

    for link in ontology.links:
        assert link.name in svg_markup, (
            f"link '{link.name}' does not appear in the ontology diagram "
            f"SVG ({SVG_PATH}) — the diagram is hand-authored and must be "
            "updated to match the ontology"
        )
