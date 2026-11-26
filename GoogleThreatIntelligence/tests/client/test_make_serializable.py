from googlethreatintelligence.client import VTAPIConnector


def test_make_serializable_prefers_to_dict():
    connector = VTAPIConnector(api_key="dummy")

    class Obj:
        def to_dict(self):
            return {"a": 1}

    assert connector._make_serializable(Obj()) == {"a": 1}


def test_make_serializable_uses_json_attribute():
    connector = VTAPIConnector(api_key="dummy")

    class Obj:
        _json = {"b": 2}

    assert connector._make_serializable(Obj()) == {"b": 2}


def test_make_serializable_falls_back_to_public_dict():
    connector = VTAPIConnector(api_key="dummy")

    class Obj:
        def __init__(self):
            self.a = 1
            self._secret = 2

    assert connector._make_serializable(Obj()) == {"a": 1}


def test_make_serializable_handles_lists_and_depth():
    connector = VTAPIConnector(api_key="dummy")

    assert connector._make_serializable([1, (2, 3)]) == [1, [2, 3]]
    assert connector._make_serializable("x", depth=11, max_depth=10) == "x"


def test_make_serializable_to_dict_exception():
    """Test fallthrough when to_dict() raises an exception."""
    connector = VTAPIConnector(api_key="dummy")

    class BadToDict:
        def to_dict(self):
            raise RuntimeError("boom")

        def __init__(self):
            self.x = 1
            self._private = 2

    result = connector._make_serializable(BadToDict())
    assert result == {"x": 1}


def test_make_serializable_json_attr_raises_on_use():
    """Test fallthrough when _json value itself causes an exception during serialization."""
    connector = VTAPIConnector(api_key="dummy")

    class BadJsonValue:
        _json = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))

        def __init__(self):
            self.y = 2

    # _json is a property that raises → hasattr returns False in some cases,
    # but we can test the except branch by making _json a valid attr that
    # raises when _make_serializable tries to process it
    class ObjWithBadJson:
        def __init__(self):
            self.y = 2

        @property
        def _json(self):
            raise ValueError("cannot serialize")

    # hasattr calls the property, which raises, so hasattr returns False.
    # To actually hit L98-99, we need _json to exist but fail during
    # _make_serializable(getattr(obj, "_json"), ...).
    class ObjJsonRaisesInSerialize:
        def __init__(self):
            self.y = 2

    obj = ObjJsonRaisesInSerialize()
    # Manually set _json to a value that will cause _make_serializable to raise
    # when recursively processed. We simulate with an object whose __dict__ fails.
    class Unserializable:
        @property
        def __dict__(self):
            raise RuntimeError("nope")

    obj._json = Unserializable()

    result = connector._make_serializable(obj)
    # Should fall through from _json exception and use __dict__
    assert result == {"y": 2}


def test_make_serializable_dict_items_raises():
    """Test str fallback when iterating __dict__.items() fails."""
    connector = VTAPIConnector(api_key="dummy")

    class BadDictItems:
        pass

    obj = BadDictItems()

    # Replace __dict__ with something that raises on items()
    class ExplodingDict(dict):
        def items(self):
            raise RuntimeError("cannot iterate")

    object.__setattr__(obj, "__dict__", ExplodingDict())

    result = connector._make_serializable(obj)
    assert isinstance(result, str)
