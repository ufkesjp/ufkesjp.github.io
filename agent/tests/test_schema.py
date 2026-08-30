"""Tests for agent/ontology/schema.py: the real eval_boards.yml must load
cleanly, and each class of referential-integrity mistake must fail loudly."""

import pytest
from pydantic import ValidationError

from ontology.schema import Ontology, load_ontology

MINIMAL_VALID = {
    "object_types": {
        "Widget": {
            "primary_key": "widget_id",
            "properties": {"widget_id": "string", "name": "string"},
        },
        "Factory": {
            "primary_key": "factory_id",
            "properties": {"factory_id": "string"},
        },
    },
    "links": [
        {
            "name": "made_at",
            "from": "Widget",
            "to": "Factory",
            "cardinality": "many_to_one",
            "from_key": "widget_id",
            "to_key": "factory_id",
        }
    ],
    "actions": {
        "scrap_widget": {
            "target_object_type": "Widget",
            "parameters": {"widget_id": "string"},
            "preconditions": [
                {
                    "field": "name",
                    "op": "not_equals",
                    "value": "scrapped",
                    "description": "must not already be scrapped",
                }
            ],
            "required_evidence": "a reason",
        }
    },
    "metrics": {
        "widget_count": {
            "definition": "count of widgets",
            "grain": ["widget"],
            "allowed_filters": ["name"],
            "owner": "someone",
            "rationale": "because",
        }
    },
}


def _deep_copy(d):
    import copy

    return copy.deepcopy(d)


def test_real_ontology_loads_and_validates():
    ontology = load_ontology()
    assert "Deck" in ontology.object_types
    assert "delamination_claim_rate" in ontology.metrics
    assert any(link.name == "consumes" for link in ontology.links)


def test_real_ontology_has_all_required_object_types():
    ontology = load_ontology()
    expected = {
        "Deck", "ProductionBatch", "MaterialLot", "Supplier",
        "QualityInspection", "WarrantyClaim", "Order", "RetailAccount",
        "PressLine",
    }
    assert expected <= set(ontology.object_types)


def test_minimal_valid_ontology_parses():
    Ontology.model_validate(_deep_copy(MINIMAL_VALID))


def test_link_referencing_undefined_object_type_fails():
    data = _deep_copy(MINIMAL_VALID)
    data["links"][0]["to"] = "NoSuchType"
    with pytest.raises(ValidationError, match="NoSuchType"):
        Ontology.model_validate(data)


def test_link_from_key_not_a_real_property_fails():
    data = _deep_copy(MINIMAL_VALID)
    data["links"][0]["from_key"] = "not_a_real_field"
    with pytest.raises(ValidationError, match="not_a_real_field"):
        Ontology.model_validate(data)


def test_metric_allowed_filter_not_a_real_property_fails():
    data = _deep_copy(MINIMAL_VALID)
    data["metrics"]["widget_count"]["allowed_filters"] = ["not_a_real_field"]
    with pytest.raises(ValidationError, match="not_a_real_field"):
        Ontology.model_validate(data)


def test_action_precondition_unknown_field_fails():
    data = _deep_copy(MINIMAL_VALID)
    data["actions"]["scrap_widget"]["preconditions"][0]["field"] = "not_a_real_field"
    with pytest.raises(ValidationError, match="not_a_real_field"):
        Ontology.model_validate(data)


def test_action_target_object_type_undefined_fails():
    data = _deep_copy(MINIMAL_VALID)
    data["actions"]["scrap_widget"]["target_object_type"] = "NoSuchType"
    with pytest.raises(ValidationError, match="NoSuchType"):
        Ontology.model_validate(data)


def test_primary_key_must_be_a_listed_property():
    data = _deep_copy(MINIMAL_VALID)
    data["object_types"]["Widget"]["primary_key"] = "not_listed"
    with pytest.raises(ValidationError, match="not_listed"):
        Ontology.model_validate(data)


def test_many_to_many_link_requires_join_fields():
    data = _deep_copy(MINIMAL_VALID)
    data["links"][0]["cardinality"] = "many_to_many"
    with pytest.raises(ValidationError, match="join_table"):
        Ontology.model_validate(data)
