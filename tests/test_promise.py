from promise import __version__
import pytest

from promise.main import (
    make_batches,
    get_query_isbns,
    Batch,
)


def test_version():
    assert __version__ == "0.1.0"


# Use a list during testing to ensure the iteration is advancing and we have stable
# batch membership for testing.
isbns = [
    "9788189999520",
    "9781405892469",
    "9782723496117",
    "9783522182676",
    "9782880462703",
]
iterator_isbns = iter(isbns)

query_result = {
    "numFound": 3,
    "start": 0,
    "numFoundExact": True,
    "docs": [
        {
            "isbn": [
                "2880460794",
                "2880462703",
                "9782880460792",
                "9780823062010",
                "9782880462703",
                "0823062015",
            ]
        },
        {"isbn": ["9781405892469", "1405892463"]},
        {"isbn": ["9788189999520", "8189999524"]},
    ],
    "num_found": 3,
    "q": "isbn:(9788189999520 OR 9781405892469 OR 9782723496117 OR 9783522182676 OR 9782880462703)",
    "offset": None,
}


@pytest.fixture
def batch():
    test_isbns = set(isbns)  # Batch.isbns expects a set.
    batch = Batch(isbns=test_isbns)
    yield batch


def test_batch(batch):
    """Ensure the Batch class behaves as expected."""
    assert batch.isbns == set(isbns)
    assert batch.total == 5


def test_make_batches():
    """
    Ensure make_batches() consumes the entire batch, and that the batch sizes are
    correct.
    """
    batches = make_batches(iterator_isbns, 2)
    # Check second iteration to ensure batcher is moving through the collection.
    next(batches)
    batch = next(batches)
    assert isinstance(batch, Batch)
    assert batch.isbns == {"9783522182676", "9782723496117"}
    # Ensure last iteration has remaining item(s) if <= batch size.
    assert next(batches).isbns == {"9782880462703"}
    with pytest.raises(StopIteration):
        next(batches)


def test_get_query_isbns():
    assert get_query_isbns(query_result) == {
        "0823062015",
        "1405892463",
        "2880460794",
        "2880462703",
        "8189999524",
        "9780823062010",
        "9781405892469",
        "9782880460792",
        "9782880462703",
        "9788189999520",
    }


def test_batch_process_isbns(batch: Batch):
    """
    Ensure batch.process() gets the right count.
    NOTE:
        This test is not mocked and does connect to live database and will fail with
        with a different promise item or if the unknown ISBNs are later added. This
        should be mocked.
    """
    batch.process_isbns()
    assert batch.total == 5
    assert batch.isbns_in_ol == 3
    assert batch.isbns_not_in_ol == 2
