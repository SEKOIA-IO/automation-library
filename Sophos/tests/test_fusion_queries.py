import re

import pytest

from sophos_module.fusion_queries import DETECTION_FIELDS, DETECTION_SEARCH, TENANT_MARKERS


@pytest.mark.parametrize("query", [DETECTION_SEARCH, TENANT_MARKERS])
def test_balanced_braces(query):
    assert query.count("{") == query.count("}")
    assert "{{" not in query and "}}" not in query


def test_detection_search():
    assert re.search(r"query DetectionSearch\(\$in: SearchRequestInput\)", DETECTION_SEARCH)
    assert "detectionSearch(in: $in)" in DETECTION_SEARCH
    assert "total_results" in DETECTION_SEARCH
    assert DETECTION_FIELDS in DETECTION_SEARCH


@pytest.mark.parametrize(
    "field",
    ["id", "status", "attack_technique_ids", "metadata {", "created_at { seconds nanos }", "source_entities {"],
)
def test_detection_fields(field):
    assert field in DETECTION_FIELDS


@pytest.mark.parametrize("excluded", ["resolution_history", "severity_history", "tuning_history", "observation_ids"])
def test_detection_fields_exclude_heavy_fields(excluded):
    assert excluded not in DETECTION_FIELDS


def test_tenant_markers():
    assert "tenant(id: $id)" in TENANT_MARKERS
    assert "centralTenant { xdrOwnership hydrateTo }" in TENANT_MARKERS
