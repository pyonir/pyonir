import sys
import types

from pyonir.core.utils import merge_dict, dict_to_class, get_attr, set_attr, set_deep_attr
from pyonir.core.parser import FILTER_KEY

def test_add_nested_from_path():

    # obj = type('foo', (object,), {'__frozen__': False})
    obj = {'__frozen__': False}
    set_deep_attr(obj,'app.datapath', 3)
    set_deep_attr(obj,'app.name', 'bar')
    set_deep_attr(obj,'app.name', 'zap')
    pass


def test_add_missing_keys():
    # Ensure parser module exists for import inside merge_dict
    derived = {"new": 123}
    src = {}
    merge_dict(derived, src)
    assert src["new"] == 123


def test_filter_key_merge_lists():

    derived = {"some_list": [3]}
    src = {"some_list": [1, 2]}
    merge_dict(derived, src)
    assert src["some_list"] == [1, 2, 3]


def test_filter_key_merge_dicts():

    derived = {"some_dict": {"x": 1}}
    src = {"some_dict": {"y": 2}}
    merge_dict(derived, src)
    # order not important; keys should be merged
    assert src["some_dict"]["y"] == 2
    assert src["some_dict"]["x"] == 1


def test_filter_key_type_mismatch_keeps_src():

    derived = {"mismatch": "not_a_list_or_dict"}
    src = {"mismatch": [1]}
    merge_dict(derived, src)
    # Should keep existing src value unchanged
    assert src["mismatch"] == [1]


def test_nested_dict_calls_update_nested():

    derived = {"nested": {"b": 2}}
    src = {"nested": {"a": 1}}
    merge_dict(derived, src)

    assert src["nested"] == {"a": 1, "b": 2}
