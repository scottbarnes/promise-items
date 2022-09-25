from json import JSONEncoder
from promise import __version__
import pytest
import requests_mock

from promise.main import (
    make_batches,
    get_query_isbns,
    Batch,
    BatchStats,
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

initial_query_result = {
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

result_after_importing_one_book = {
    "numFound": 4,
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
        {"isbn": ["2723496112", "9782723496117"]},
    ],
    "num_found": 4,
    "q": "isbn:(9788189999520 OR 9781405892469 OR 9782723496117 OR 9783522182676 OR 9782880462703)",
    "offset": None,
}


@pytest.fixture
def batch():
    test_isbns = set(isbns)  # Batch.isbns expects a set.
    batch = Batch(promise_item_isbns=test_isbns)
    yield batch


def test_batch(batch):
    """Ensure the Batch class behaves as expected."""
    assert batch.promise_item_isbns == set(isbns)
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
    assert batch.promise_item_isbns == {"9783522182676", "9782723496117"}
    # Ensure last iteration has remaining item(s) if <= batch size.
    assert next(batches).promise_item_isbns == {"9782880462703"}
    with pytest.raises(StopIteration):
        next(batches)


def test_get_query_isbns():
    assert get_query_isbns(initial_query_result) == {
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


"""
Import attempt. High level. Create a new method to do GETs to /isbn. It should
keep track of any 200 responses it gets and remove them from self.misses.

Then serialize the list[Batch] and write it to disk.
Read from disk, deserialize to continue.

make batch.check_if_isbns_in_openlibrary() take an argument (Literal) for isbns or misses. May
need to rename self.isbns so it's more clear this is the list. Maybe
self.promise_item_isbns.

run check_if_isbns_in_openlibrary(misses).


serialize/deserialize.

I need to:
    iterate through batch.misses
    ensure there is a delay. Say, 1 second for now between requests.
    make a GET to http://localhost:8080/isbn/{isbn}
    check r.status_code
        if 200, remove from self.misses
        if 404, do nothing
    update self.in_ol_count and self.not_in_ol_count

create a serializer/deserializer to read/write to disk.

command line arg to run import process.
"""


def test_batch_process_promise_item_isbns(batch: Batch):
    """
    Ensure batch.process() gets the right count.
    NOTE:
        This test is not mocked and does connect to live database and will fail with
        with a different promise item or if the unknown ISBNs are later added. This
        should be mocked.
    """
    with requests_mock.Mocker(json_encoder=JSONEncoder) as m:
        m.get(requests_mock.ANY, json=initial_query_result)
        batch.check_if_isbns_in_openlibrary()
        assert batch.hits == {
            "9781405892469",
            "9782880462703",
            "9788189999520",
        }
        assert batch.misses == {"9782723496117", "9783522182676"}
        assert batch.total == 5
        assert batch.in_ol_count == 3
        assert batch.not_in_ol_count == 2


def test_batch_stats(batch: Batch):
    """Get the stats for all the batches."""
    batches = make_batches(iter(isbns), 2)

    processed_batches = []
    for batch in batches:
        batch.check_if_isbns_in_openlibrary()
        processed_batches.append(batch)

    batch_stats = BatchStats()
    batch_stats.loader(batches=processed_batches)

    assert batch_stats.promise_item_isbns == {
        "9781405892469",
        "9782880462703",
        "9788189999520",
        "9782723496117",
        "9783522182676",
    }
    assert batch_stats.hits == {
        "9781405892469",
        "9782880462703",
        "9788189999520",
    }
    assert batch_stats.misses == {"9782723496117", "9783522182676"}
    assert batch_stats.total == 5
    assert batch_stats.in_ol_count == 3
    assert batch_stats.not_in_ol_count == 2


# def test_batch_process_promise_item_isbns(batch: Batch):
#     """
#     Ensure batch.process() gets the right count.
#     NOTE:
#         This test is not mocked and does connect to live database and will fail with
#         with a different promise item or if the unknown ISBNs are later added. This
#         should be mocked.
#     """
#     with requests_mock.Mocker(json_encoder=JSONEncoder) as m:
#         m.get(requests_mock.ANY, json=initial_query_result)
#         batch.check_if_isbns_in_openlibrary("promise_items")
#         assert batch.hits == {
#             "9781405892469",
#             "9782880462703",
#             "9788189999520",
#         }
#         assert batch.misses == {"9782723496117", "9783522182676"}
#         assert batch.total == 5
#         assert batch.in_ol_count == 3
#         assert batch.not_in_ol_count == 2


# def test_batch_process_misses(batch: Batch):
#     """
#     Ensure batch.process("misses") updates the batch values to account for items added
#     by batch.add_misses.

#     NOTE: The mocked response here assumes {batch.add_misses()} has been run and was
#     able to successfully add "9782723496117" to the Open Library database.
#     """
#     # Must run with "promise_items" first because there are no misses until this is run.
#     # Start off with two misses.
#     batch.check_if_isbns_in_openlibrary("promise_items")

#     # No point in running these?
#     # with requests_mock.Mocker(json_encoder=JSONEncoder) as m:
#     #     m.get(requests_mock.ANY, json=initial_query_result)
#     #     batch.check_if_isbns_in_openlibrary("promise_items")
#     #     assert batch.hits == {
#     #         "9781405892469",
#     #         "9782880462703",
#     #         "9788189999520",
#     #     }
#     #     assert batch.misses == {"9782723496117", "9783522182676"}

#     # Pretend only one of the two misses is added by batch.add_misses()
#     with requests_mock.Mocker(json_encoder=JSONEncoder) as m:
#         m.get(requests_mock.ANY, json=result_after_importing_one_book)
#         batch.check_if_isbns_in_openlibrary("misses")
#         assert batch.hits == {
#             "9781405892469",
#             "9782723496117",
#             "9782880462703",
#             "9788189999520",
#         }
#         assert batch.misses == {"9783522182676"}
#         assert batch.total == 5
#         assert batch.in_ol_count == 4
#         assert batch.not_in_ol_count == 1
