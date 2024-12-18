import os
import sys

# Change directory to parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from luxy import (
    PeopleGroups, Objects, Works, Places, 
    Concepts, Events, Collections, FilterBuilder
)

# Test FilterBuilder
def test_filter_builder_basic():
    fb = FilterBuilder()
    result = fb.someField("test")
    assert result == {"someField": {"name": "test"}}

def test_filter_builder_nested():
    fb = FilterBuilder()
    result = fb.parent.child("test")
    assert result == {"parent": {"child": {"name": "test"}}}

def test_filter_builder_depth():
    fb = FilterBuilder()
    result = fb.memberOf("test", depth=2)
    assert result == {"memberOf": {"memberOf": {"name": "test"}}}

def test_filter_builder_invalid_depth():
    fb = FilterBuilder()
    with pytest.raises(ValueError):
        fb.memberOf("test", depth=0)

# Test Base Class functionality
def test_filter_validation():
    obj = Objects()
    with pytest.raises(ValueError):
        obj.get()  # Should raise error when no filters are set

def test_basic_filter():
    obj = Objects().filter(name="test").get()
    assert obj._cached_query_dict == {"AND": [{"name": "test"}]}

def test_multiple_filters():
    obj = Objects()
    obj.filter(name="test").filter(hasDigitalImage=True).get()
    query_dict = obj._cached_query_dict
    assert query_dict == {"AND": [{"name": "test"}, {"hasDigitalImage": 1}]}

def test_or_filter():
    obj = Objects()
    obj.filter(OR=[{"name": "test1"}, {"name": "test2"}]).get()
    query_dict = obj._cached_query_dict
    assert query_dict == {"AND": [{"OR": [{"name": "test1"}, {"name": "test2"}]}]}

# Test specific class instantiation
def test_class_initialization():
    classes = [
        (PeopleGroups, "agent"),
        (Objects, "item"),
        (Works, "work"),
        (Places, "place"),
        (Concepts, "concept"),
        (Events, "event"),
        (Collections, "set")
    ]
    
    for cls, expected_name in classes:
        instance = cls()
        assert instance.name == expected_name

def test_cache_clearing():
    obj = Objects()
    obj.filter(name="test")
    obj._cached_response = "dummy"
    obj._cached_query_dict = {"test": "data"}
    
    obj.clear_cache()
    assert obj._cached_response is None
    assert obj._cached_query_dict is None

def test_boolean_conversion():
    obj = Objects().filter(hasDigitalImage=True).get()
    query_dict = obj._cached_query_dict
    assert query_dict == {"AND": [{"hasDigitalImage": 1}]}

    obj = Objects().filter(hasDigitalImage=False).get()
    query_dict = obj._cached_query_dict
    assert query_dict == {"AND": [{"hasDigitalImage": 0}]}
