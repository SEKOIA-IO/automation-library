# coding: utf-8
# natives
import json
import uuid
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

# third parties
import pytest

# internals
from utils.action_fileutils_readxmlfile import FileUtilsReadXMLFile


@pytest.fixture(autouse=True, scope="session")
def symphony_storage():
    new_storage = Path(mkdtemp())

    yield new_storage

    rmtree(new_storage.as_posix())


def test_readhtmlfile_without_xpath(symphony_storage):
    sample_object = """<html>
    <body><h1>does not matter</h1>
    </body>
</html>"""

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        fd.write(sample_object)

    action = FileUtilsReadXMLFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath})

    assert results == {"output": sample_object}


def test_readhtmlfile_with_xpath_one_match(symphony_storage):
    sample_object = """<html>
    <head>
        <title>Example page</title>
    </head>
    <body>
        <p>Moved to <a href="http://example.org/">example.org</a>.</p>
    </body>
</html>"""

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        fd.write(sample_object)

    action = FileUtilsReadXMLFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath, "xpath": "./body//a/@href"})

    assert results == {"output": "http://example.org/"}


def test_readhtmlfile_with_xpath_one_match_return_list(symphony_storage):
    sample_object = """<html>
    <head>
        <title>Example page</title>
    </head>
    <body>
        <p>Moved to <a href="http://example.org/">example.org</a>.</p>
    </body>
</html>"""

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        fd.write(sample_object)

    action = FileUtilsReadXMLFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath, "return_list": True, "xpath": "./body//a/@href"})

    assert results == {"output": ["http://example.org/"]}


def test_readhtml5file_with_xpath_one_match(symphony_storage):
    sample_object = """<html>
  <head>
    <title>Img Src Attribute Example</title>
  </head>
  <body>
    <img src="http://dev.localhost/u/blabla?v=1.0.2" />
  </body>
</html>"""

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        fd.write(sample_object)

    action = FileUtilsReadXMLFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath, "return_list": True, "xpath": "./body//img/@src"})

    assert results == {"output": ["http://dev.localhost/u/blabla?v=1.0.2"]}


def test_readxmlfile_with_xpath_one_match(symphony_storage):
    sample_object = """<?xml version="1.0"?>
<data>
    <country name="Liechtenstein">
        <rank updated="yes">2</rank>
        <year>2008</year>
        <gdppc>141100</gdppc>
        <neighbor name="Austria" direction="E"/>
        <neighbor name="Switzerland" direction="W"/>
    </country>
    <country name="Singapore">
        <rank updated="yes">5</rank>
        <year>2011</year>
        <gdppc>59900</gdppc>
        <neighbor name="Malaysia" direction="N"/>
    </country>
    <country name="Panama">
        <rank updated="yes">69</rank>
        <year>2011</year>
        <gdppc>13600</gdppc>
        <neighbor name="Costa Rica" direction="W"/>
        <neighbor name="Colombia" direction="E"/>
    </country>
</data>"""

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        fd.write(sample_object)

    action = FileUtilsReadXMLFile(data_path=symphony_storage)
    results = action.run(
        {
            "file_path": filepath,
            "source_type": "xml",
            "xpath": "./country[@name='Singapore']/neighbor/@name",
        }
    )

    assert results == {"output": "Malaysia"}


def test_readxmlfile_with_xpath_one_match_return_list(symphony_storage):
    sample_object = """<?xml version="1.0"?>
<data>
    <country name="Liechtenstein">
        <rank updated="yes">2</rank>
        <year>2008</year>
        <gdppc>141100</gdppc>
        <neighbor name="Austria" direction="E"/>
        <neighbor name="Switzerland" direction="W"/>
    </country>
    <country name="Singapore">
        <rank updated="yes">5</rank>
        <year>2011</year>
        <gdppc>59900</gdppc>
        <neighbor name="Malaysia" direction="N"/>
    </country>
    <country name="Panama">
        <rank updated="yes">69</rank>
        <year>2011</year>
        <gdppc>13600</gdppc>
        <neighbor name="Costa Rica" direction="W"/>
        <neighbor name="Colombia" direction="E"/>
    </country>
</data>"""

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        fd.write(sample_object)

    action = FileUtilsReadXMLFile(data_path=symphony_storage)
    results = action.run(
        {
            "file_path": filepath,
            "source_type": "xml",
            "return_list": True,
            "xpath": "./country[@name='Singapore']/neighbor/@name",
        }
    )

    assert results == {"output": ["Malaysia"]}


def test_readhtmlfile_with_xpath_multiple_match(symphony_storage):
    sample_object = """<html>
    <head>
        <title>Example page</title>
    </head>
    <body>
        <h1>No body care about title</h1>
        <p>first paragraphe</p>
        <p>second one</p>
    </body>
</html>"""

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        fd.write(sample_object)

    action = FileUtilsReadXMLFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath, "xpath": "./body/p/text()"})

    assert results == {"output": ["first paragraphe", "second one"]}


def test_readhtmlfile_with_xpath_no_match(symphony_storage):
    sample_object = """<html>
    <head>
        <title>Example page</title>
    </head>
    <body>
        <h1>No body care about title</h1>
        <p>first paragraphe</p>
        <p>second one</p>
    </body>
</html>"""

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        fd.write(sample_object)

    action = FileUtilsReadXMLFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath, "xpath": "./body//a/@href"})

    assert results == {"output": None}


def test_readhtmlfile_with_xpath_one_match_to_file(symphony_storage):
    sample_object = """<html>
    <head>
        <title>Example page</title>
    </head>
    <body>
        <p>Moved to <a href="http://example.org/">example.org</a>.</p>
    </body>
</html>"""

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        fd.write(sample_object)

    action = FileUtilsReadXMLFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath, "xpath": "./body//a/@href", "to_file": True})

    output_path = symphony_storage / results["output_path"]
    with output_path.open() as fp:
        assert fp.read() == "http://example.org/"


def test_read_xml_file_string_match_to_file(symphony_storage):
    sample_object = """<?xml version="1.0"?>
<data>
    <country name="Liechtenstein">
        <rank updated="yes">2</rank>
        <year>2008</year>
        <gdppc>141100</gdppc>
        <neighbor name="Austria" direction="E"/>
        <neighbor name="Switzerland" direction="W"/>
    </country>
    <country name="Singapore">
        <rank updated="yes">5</rank>
        <year>2011</year>
        <gdppc>59900</gdppc>
        <neighbor name="Malaysia" direction="N"/>
    </country>
    <country name="Panama">
        <rank updated="yes">69</rank>
        <year>2011</year>
        <gdppc>13600</gdppc>
        <neighbor name="Costa Rica" direction="W"/>
        <neighbor name="Colombia" direction="E"/>
    </country>
</data>"""

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        fd.write(sample_object)

    action = FileUtilsReadXMLFile(data_path=symphony_storage)
    results = action.run(
        {
            "file_path": filepath,
            "xpath": "./country/@name",
            "source_type": "xml",
            "to_file": True,
        }
    )

    output_path = symphony_storage / results["output_path"]
    with output_path.open() as fp:
        assert json.load(fp) == ["Liechtenstein", "Singapore", "Panama"]


def test_read_xml_file_one_match_to_file(symphony_storage):
    sample_object = """<?xml version="1.0"?>
<data>
    <country name="Liechtenstein">
        <rank updated="yes">2</rank>
        <year>2008</year>
        <gdppc>141100</gdppc>
        <neighbor name="Austria" direction="E"/>
    </country>
    <country name="Singapore">
        <rank updated="yes">5</rank>
        <year>2011</year>
        <gdppc>59900</gdppc>
        <neighbor name="Malaysia" direction="N"/>
    </country>
    <country name="Panama">
        <rank updated="yes">69</rank>
        <year>2011</year>
        <gdppc>13600</gdppc>
        <neighbor name="Costa Rica" direction="W"/>
        <neighbor name="Colombia" direction="E"/>
    </country>
</data>"""

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        fd.write(sample_object)

    action = FileUtilsReadXMLFile(data_path=symphony_storage)
    results = action.run(
        {
            "file_path": filepath,
            "xpath": "./country[year<2009]/neighbor/@name",
            "source_type": "xml",
            "to_file": True,
        }
    )

    output_path = symphony_storage / results["output_path"]
    with output_path.open() as fp:
        assert fp.read() == "Austria"


def test_read_xml_file_one_match_to_file_return_list(symphony_storage):
    sample_object = """<?xml version="1.0"?>
<data>
    <country name="Liechtenstein">
        <rank updated="yes">2</rank>
        <year>2008</year>
        <gdppc>141100</gdppc>
        <neighbor name="Austria" direction="E"/>
    </country>
    <country name="Singapore">
        <rank updated="yes">5</rank>
        <year>2011</year>
        <gdppc>59900</gdppc>
        <neighbor name="Malaysia" direction="N"/>
    </country>
    <country name="Panama">
        <rank updated="yes">69</rank>
        <year>2011</year>
        <gdppc>13600</gdppc>
        <neighbor name="Costa Rica" direction="W"/>
        <neighbor name="Colombia" direction="E"/>
    </country>
</data>"""

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        fd.write(sample_object)

    action = FileUtilsReadXMLFile(data_path=symphony_storage)
    results = action.run(
        {
            "file_path": filepath,
            "xpath": "./country[year<2009]/neighbor/@name",
            "source_type": "xml",
            "return_list": True,
            "to_file": True,
        }
    )

    output_path = symphony_storage / results["output_path"]
    with output_path.open() as fp:
        assert json.load(fp) == ["Austria"]
