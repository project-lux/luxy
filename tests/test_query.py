"""Tests for the luxql-backed query construction layer."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from luxql import LuxAPI, LuxBoolean, LuxLeaf, LuxRelationship

from luxy import (
    Concepts,
    Objects,
    PeopleGroups,
    Works,
    complexity,
)
from luxy.query import Chain, FilterBuilder


# ---------------------------------------------------------------------------
# Graph-style filter chains
# ---------------------------------------------------------------------------

def test_chain_two_hop():
    q = PeopleGroups().filter(produced__classification__name="painting")
    assert q.to_dict() == {
        "AND": [{"produced": {"classification": {"name": "painting"}}}]
    }


def test_chain_three_hop():
    q = PeopleGroups().filter(
        produced__classification__broader__name="art"
    )
    assert q.to_dict() == {
        "AND": [
            {
                "produced": {
                    "classification": {"broader": {"name": "art"}}
                }
            }
        ]
    }


def test_chain_with_comparator_alias():
    q = Objects().filter(height__gte=1)
    assert q.to_dict() == {"AND": [{"height": "1", "_comp": ">="}]}


def test_chain_with_eq_alias_is_fine():
    q = Objects().filter(name__eq="frame")
    # eq normalises to ==
    assert q.to_dict() == {"AND": [{"name": "frame", "_comp": "=="}]}


def test_chain_legacy_dict_value_unchanged():
    """Passing a legacy dict value still produces the same shape."""
    q = PeopleGroups().filter(gender={"name": "male"})
    assert q.to_dict() == {"AND": [{"gender": {"name": "male"}}]}


def test_filter_or_with_dicts():
    q = Objects().filter(OR=[{"name": "test1"}, {"name": "test2"}])
    assert q.to_dict() == {
        "AND": [{"OR": [{"name": "test1"}, {"name": "test2"}]}]
    }


def test_filter_and_with_dicts():
    q = Objects().filter(AND=[{"name": "test1"}, {"hasDigitalImage": True}])
    assert q.to_dict() == {
        "AND": [{"AND": [{"name": "test1"}, {"hasDigitalImage": "1"}]}]
    }


def test_filter_or_with_baselux_instances():
    inner1 = Objects().filter(name="painting")
    inner2 = Objects().filter(name="drawing")
    q = Objects().filter(OR=[inner1, inner2])
    assert q.to_dict() == {
        "AND": [{"OR": [{"name": "painting"}, {"name": "drawing"}]}]
    }


def test_filter_relationship_with_baselux_value():
    """Embedding a BaseLux as a relationship value."""
    inner = Objects().filter(name="painting")
    q = PeopleGroups().filter(produced=inner)
    assert q.to_dict() == {"AND": [{"produced": {"name": "painting"}}]}


# ---------------------------------------------------------------------------
# luxql tree round-tripping
# ---------------------------------------------------------------------------

def test_to_luxql_returns_tree():
    q = PeopleGroups().filter(name="John").filter(hasDigitalImage=True)
    tree = q.to_luxql()
    assert isinstance(tree, LuxAPI)
    assert tree.provides_scope == "agent"
    js = tree.to_json()
    assert js == {"AND": [{"name": "John"}, {"hasDigitalImage": "1"}]}


def test_to_luxql_graph_chain_uses_relationships():
    q = PeopleGroups().filter(produced__classification__name="painting")
    tree = q.to_luxql()
    js = tree.to_json()
    assert js == {
        "AND": [{"produced": {"classification": {"name": "painting"}}}]
    }
    # Walk the tree to verify the actual node types
    root_and = tree.children[0]
    assert isinstance(root_and, LuxBoolean)
    rel1 = root_and.children[0]
    assert isinstance(rel1, LuxRelationship) and rel1.field == "produced"
    rel2 = rel1.children[0]
    assert isinstance(rel2, LuxRelationship) and rel2.field == "classification"
    leaf = rel2.children[0]
    assert isinstance(leaf, LuxLeaf) and leaf.field == "name"


def test_to_dict_empty_query():
    q = Objects()
    assert q.to_dict() == {}


# ---------------------------------------------------------------------------
# luxql validation
# ---------------------------------------------------------------------------

def test_unknown_field_is_rejected():
    """luxql validates against the LUX advanced-search-config."""
    with pytest.raises((ValueError, Exception)):
        PeopleGroups().filter(noSuchField="x")


def test_relationship_used_as_leaf_is_rejected():
    """``produced`` is a relationship, so it can't be a plain leaf."""
    with pytest.raises((ValueError, Exception)):
        PeopleGroups().filter(produced="painting")


def test_field_in_wrong_scope_is_rejected():
    """``encounteredDate`` is on Objects, not on Works."""
    with pytest.raises((ValueError, Exception)):
        Works().filter(encounteredDate=("2000-01-01T00:00:00.000Z", ">"))


# ---------------------------------------------------------------------------
# Complexity
# ---------------------------------------------------------------------------

def test_complexity_simple_query_is_low():
    q = Objects().filter(name="painting")
    assert q.query_complexity() < complexity.COST_RELATIONSHIP


def test_complexity_relationship_query_is_high():
    q = PeopleGroups().filter(produced__classification__name="painting")
    assert q.query_complexity() >= complexity.COST_RELATIONSHIP


def test_complexity_category_assignment():
    simple = Objects().filter(name="x")
    assert simple._category_for_query() == "simple"

    rel = PeopleGroups().filter(produced__classification__name="x")
    assert rel._category_for_query() == "relationship"


def test_complexity_score_directly():
    q = PeopleGroups().filter(produced__classification__name="painting")
    score = complexity.score(q.to_luxql())
    assert score >= complexity.COST_RELATIONSHIP


# ---------------------------------------------------------------------------
# Chain materialisation
# ---------------------------------------------------------------------------

def test_chain_materialises_under_baselux():
    """A Chain can be embedded directly as a value of filter()."""
    fb = FilterBuilder()
    chain = fb.classification.name("painting")
    q = PeopleGroups().filter(produced=chain)
    assert q.to_dict() == {
        "AND": [{"produced": {"classification": {"name": "painting"}}}]
    }


def test_chain_in_or_list():
    """Chains can appear inside OR/AND/NOT lists."""
    fb = FilterBuilder()
    q = Objects().filter(
        OR=[
            fb.memberOf("Letters", depth=2),
            fb.memberOf("Letters", depth=3),
        ]
    )
    assert q.to_dict() == {
        "AND": [
            {
                "OR": [
                    {"memberOf": {"memberOf": {"text": "Letters"}}},
                    {"memberOf": {"memberOf": {"memberOf": {"text": "Letters"}}}},
                ]
            }
        ]
    }
