"""Pydantic models that parse and validate agent/ontology/eval_boards.yml.

The ontology YAML is the only place object types, links, actions, and
metrics are defined. This module is the gate: anything that doesn't parse or
doesn't reference real object types/properties raises here, at load time,
rather than surfacing as a confusing failure deep in the SQL compiler or the
agent loop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

PropertyType = Literal["string", "int", "float", "date", "bool"]

DEFAULT_ONTOLOGY_PATH = Path(__file__).parent / "eval_boards.yml"


class ObjectType(BaseModel):
    description: str
    primary_key: str
    properties: dict[str, PropertyType]

    @model_validator(mode="after")
    def primary_key_is_a_property(self) -> "ObjectType":
        if self.primary_key not in self.properties:
            raise ValueError(
                f"primary_key '{self.primary_key}' is not listed in properties"
            )
        return self


class Link(BaseModel):
    name: str
    from_: str = Field(alias="from")
    to: str
    cardinality: Literal["many_to_many", "many_to_one", "one_to_many", "one_to_one"]
    description: str

    # many_to_one / one_to_many / one_to_one shape
    from_key: str | None = None
    to_key: str | None = None

    # many_to_many shape
    join_table: str | None = None
    join_from_key: str | None = None
    join_to_key: str | None = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def keys_present_for_cardinality(self) -> "Link":
        if self.cardinality == "many_to_many":
            missing = [
                field
                for field in ("join_table", "join_from_key", "join_to_key")
                if getattr(self, field) is None
            ]
            if missing:
                raise ValueError(
                    f"link '{self.name}' is many_to_many but missing {missing}"
                )
        else:
            missing = [
                field for field in ("from_key", "to_key") if getattr(self, field) is None
            ]
            if missing:
                raise ValueError(
                    f"link '{self.name}' ({self.cardinality}) is missing {missing}"
                )
        return self


class Precondition(BaseModel):
    field: str
    op: Literal["equals", "not_equals", "gt", "gte", "lt", "lte"]
    value: str
    description: str


class Action(BaseModel):
    target_object_type: str
    parameters: dict[str, PropertyType]
    preconditions: list[Precondition]
    required_evidence: str


class Metric(BaseModel):
    definition: str
    grain: list[str]
    allowed_filters: list[str]
    owner: str
    rationale: str


class Ontology(BaseModel):
    object_types: dict[str, ObjectType]
    links: list[Link]
    actions: dict[str, Action]
    metrics: dict[str, Metric]

    @model_validator(mode="after")
    def links_reference_defined_object_types(self) -> "Ontology":
        errors: list[str] = []
        for link in self.links:
            for end, type_name in (("from", link.from_), ("to", link.to)):
                if type_name not in self.object_types:
                    errors.append(
                        f"link '{link.name}': {end} object type "
                        f"'{type_name}' is not defined in object_types"
                    )
        if errors:
            raise ValueError("; ".join(errors))
        return self

    @model_validator(mode="after")
    def link_keys_are_real_properties(self) -> "Ontology":
        errors: list[str] = []
        for link in self.links:
            if link.cardinality == "many_to_many":
                from_type = self.object_types.get(link.from_)
                to_type = self.object_types.get(link.to)
                if from_type and link.join_from_key not in from_type.properties:
                    errors.append(
                        f"link '{link.name}': join_from_key "
                        f"'{link.join_from_key}' is not a property of {link.from_}"
                    )
                if to_type and link.join_to_key not in to_type.properties:
                    errors.append(
                        f"link '{link.name}': join_to_key "
                        f"'{link.join_to_key}' is not a property of {link.to}"
                    )
            else:
                from_type = self.object_types.get(link.from_)
                to_type = self.object_types.get(link.to)
                if from_type and link.from_key not in from_type.properties:
                    errors.append(
                        f"link '{link.name}': from_key '{link.from_key}' "
                        f"is not a property of {link.from_}"
                    )
                if to_type and link.to_key not in to_type.properties:
                    errors.append(
                        f"link '{link.name}': to_key '{link.to_key}' "
                        f"is not a property of {link.to}"
                    )
        if errors:
            raise ValueError("; ".join(errors))
        return self

    @model_validator(mode="after")
    def actions_reference_defined_object_types_and_fields(self) -> "Ontology":
        errors: list[str] = []
        for action_name, action in self.actions.items():
            if action.target_object_type not in self.object_types:
                errors.append(
                    f"action '{action_name}': target_object_type "
                    f"'{action.target_object_type}' is not defined in object_types"
                )
                continue
            target = self.object_types[action.target_object_type]
            for precondition in action.preconditions:
                if precondition.field not in target.properties:
                    errors.append(
                        f"action '{action_name}': precondition field "
                        f"'{precondition.field}' is not a property of "
                        f"{action.target_object_type}"
                    )
        if errors:
            raise ValueError("; ".join(errors))
        return self

    @model_validator(mode="after")
    def metrics_reference_real_properties(self) -> "Ontology":
        errors: list[str] = []
        all_properties: set[str] = set()
        for object_type in self.object_types.values():
            all_properties.update(object_type.properties.keys())

        for metric_name, metric in self.metrics.items():
            for filter_field in metric.allowed_filters:
                if filter_field not in all_properties:
                    errors.append(
                        f"metric '{metric_name}': allowed_filters entry "
                        f"'{filter_field}' is not a property of any object type"
                    )
        if errors:
            raise ValueError("; ".join(errors))
        return self


def load_ontology(path: Path | str = DEFAULT_ONTOLOGY_PATH) -> Ontology:
    """Parse and validate the ontology YAML. Raises pydantic.ValidationError
    (or ValueError from a model_validator) on any structural problem."""
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Ontology.model_validate(raw)
