"""
LazyHDF5ArrayAdapter follows HDF5 references only into readable storage,
like the stock HDF5 adapters (see test_hdf5_references.py).
"""

import h5py
import numpy
import pytest
from starlette.status import HTTP_200_OK, HTTP_410_GONE

from tiled.adapters.lazy_hdf5 import LazyHDF5ArrayAdapter
from tiled.catalog import from_uri
from tiled.client import Context, from_context
from tiled.server.app import build_app
from tiled.structures.array import ArrayStructure
from tiled.structures.core import StructureFamily
from tiled.structures.data_source import Asset, DataSource, Management
from tiled.utils import path_from_uri

from .test_hdf5_references import INSIDE, SECRET, build, layout  # noqa: F401

BROKER_MIMETYPE = "application/x-hdf5-broker"
KEY = "lazy"

ALLOWED = ["plain", "link-inside", "virtual-inside"]
REFUSED = [
    "external-storage-outside",
    "link-outside",
    "virtual-outside",
    "virtual-of-relay-external-storage",
]


@pytest.fixture
def client(layout):  # noqa: F811
    catalog = from_uri(
        f"sqlite:///{layout / 'catalog.db'}",
        readable_storage=[layout / "readable"],
        adapters_by_mimetype={BROKER_MIMETYPE: LazyHDF5ArrayAdapter},
        init_if_not_exists=True,
    )
    with Context.from_app(build_app(catalog)) as context:
        yield from_context(context)


def register(client, uri):
    "Register dataset x of the file, with its on-disk shape and dtype."
    with h5py.File(path_from_uri(uri), "r") as file:
        dataset = file["x"]
        structure = ArrayStructure.from_array(numpy.empty(dataset.shape, dataset.dtype))
    client.new(
        key=KEY,
        structure_family=StructureFamily.array,
        metadata={},
        data_sources=[
            DataSource(
                structure_family=StructureFamily.array,
                mimetype=BROKER_MIMETYPE,
                structure=structure,
                parameters={"dataset": "x"},
                management=Management.external,
                assets=[Asset(data_uri=uri, is_directory=False, parameter="data_uris")],
            )
        ],
    )


def get_full(client):
    return client.context.http_client.get(
        f"/api/v1/array/full/{KEY}",
        headers={"Accept": "application/octet-stream"},
    )


@pytest.mark.parametrize("name", ALLOWED)
def test_follows_reference_into_readable_storage(layout, client, name):  # noqa: F811
    register(client, build(layout, name))

    response = get_full(client)

    assert response.status_code == HTTP_200_OK
    assert (client[KEY].read() == INSIDE).all()


@pytest.mark.parametrize("name", REFUSED)
def test_refuses_reference_out_of_readable_storage(layout, client, name):  # noqa: F811
    register(client, build(layout, name))

    response = get_full(client)

    assert response.status_code == HTTP_410_GONE
    assert SECRET not in response.content
