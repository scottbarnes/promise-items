"""
All the tests for for the promise items script. Requests calls are mocked, with data
based on the fictional super_pallet_2020-09-21.
"""
import pickle
from json import JSONEncoder
from pathlib import Path
from typing import Final

import pytest
import requests_mock

from promise import __version__
from promise.constants import API_URL_LAST_X_ITEMS
from promise.main import Pallet, PromiseItem, check_latest
from promise.utils import (
    dedup_isbns,
    get_file_if_exists,
    get_promise_item_urls,
    get_query_isbns,
    make_batches,
)
from tests.mock_responses import (
    response_get_promise_item_isbns,
    response_initial_query,
    response_last_five_promise_items,
    response_latest_promise_item,
)


def test_version():
    assert __version__ == "0.1.0"


# Sample ISBNs as they would be extracted from ["extrameta"["isbn"]
isbns = [
    9788189999520,
    9781405892469,
    1405892463,
    9782723496117,
    "BWBM52088056",
    9783522182676,
    9782880462703,
]


@pytest.fixture
def pallet():
    """Get a pallet to work with for the tests."""
    # __post_init__ calls request.get to populate items, so this must be mocked.
    with requests_mock.Mocker(json_encoder=JSONEncoder) as m:
        m.get(
            "https://archive.org/metadata/super_pallet_2020-09-21",
            json=response_get_promise_item_isbns,
        )

        p = Pallet(
            url="https://archive.org/metadata/super_pallet_2020-09-21",
            batch_size=2,
        )

        yield p


@pytest.fixture
def pallet_with_get_hits_run():
    """Get a pallet to work with for the tests, but with self.get_hits() run."""
    # __post_init__ calls request.get to populate items, so this must be mocked.
    with requests_mock.Mocker(json_encoder=JSONEncoder) as m:
        m.get(
            "https://archive.org/metadata/super_pallet_2020-09-21",
            json=response_get_promise_item_isbns,
        )

        p = Pallet(
            url="https://archive.org/metadata/super_pallet_2020-09-21",
            batch_size=2,
        )

    with requests_mock.Mocker(json_encoder=JSONEncoder) as m:
        m.get(requests_mock.ANY, json=response_initial_query)
        p.get_hits()

        yield p


@pytest.fixture
def pallet_with_add_misses_run():
    """Get a pallet to work with for the tests, but with self.add_misses() run."""
    # __post_init__ calls request.get to populate items, so this must be mocked.
    with requests_mock.Mocker(json_encoder=JSONEncoder) as m:
        m.get(
            "https://archive.org/metadata/super_pallet_2020-09-21",
            json=response_get_promise_item_isbns,
        )

        p = Pallet(
            url="https://archive.org/metadata/super_pallet_2020-09-21",
            batch_size=2,
        )

    with requests_mock.Mocker(json_encoder=JSONEncoder) as m:
        m.get(requests_mock.ANY, json=response_initial_query)
        p.get_hits()

    with requests_mock.Mocker() as m:
        m.get(requests_mock.ANY, status_code=404)
        p.add_misses(0)

        yield p


def test_make_batches(pallet: Pallet) -> None:
    """
    Ensure make_batches() consumes the entire batch, and that the batch sizes are
    correct.
    """
    batches = make_batches(pallet.items, 2)
    assert batches[1] == [
        PromiseItem(
            isbn="9782880462703",
            pallet="super_pallet_2020-09-21",
            in_openlibrary=False,
            add_attempted=False,
        ),
        PromiseItem(
            isbn="9783522182676",
            pallet="super_pallet_2020-09-21",
            in_openlibrary=False,
            add_attempted=False,
        ),
    ]
    # Ensure last iteration has remaining item(s) if <= batch size.
    assert batches[2] == [
        PromiseItem(
            isbn="9788189999520",
            pallet="super_pallet_2020-09-21",
            in_openlibrary=False,
            add_attempted=False,
        ),
    ]
    with pytest.raises(IndexError):
        assert batches[3] == "blob"


def test_get_query_isbns():
    assert get_query_isbns(response_initial_query) == {
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


class TestPallet:
    def test_name_attribute_set(self, pallet: Pallet) -> None:
        """Ensure a Pallet populates self.name properly on creation."""
        assert pallet.name == "super_pallet_2020-09-21"

    def test_items_populate(self, pallet: Pallet) -> None:
        """Ensure a Pallet populates self.items properly on creation."""
        assert pallet.items == [
            PromiseItem(
                isbn="9781405892469",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=False,
                add_attempted=False,
            ),
            PromiseItem(
                isbn="9782723496117",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=False,
                add_attempted=False,
            ),
            PromiseItem(
                isbn="9782880462703",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=False,
                add_attempted=False,
            ),
            PromiseItem(
                isbn="9783522182676",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=False,
                add_attempted=False,
            ),
            PromiseItem(
                isbn="9788189999520",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=False,
                add_attempted=False,
            ),
        ]

    def test_length_set_properly(self, pallet: Pallet) -> None:
        """Ensure a pallet's len() is correct."""
        assert len(pallet) == 5

    def test_get_hits(self, pallet_with_get_hits_run: Pallet) -> None:
        """
        Ensure pallet.get_hits() only returns promise items already in Open Library.
        """
        pallet = pallet_with_get_hits_run
        assert pallet.get_hits() == [
            PromiseItem(
                isbn="9781405892469",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=True,
                add_attempted=False,
                original_miss=False,
            ),
            PromiseItem(
                isbn="9782880462703",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=True,
                add_attempted=False,
                original_miss=False,
            ),
            PromiseItem(
                isbn="9788189999520",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=True,
                add_attempted=False,
                original_miss=False,
            ),
        ]
        assert pallet.solr_queried is True

    def test_count_hits_requires_get_hits_to_run_first(self, pallet: Pallet) -> None:
        """pallet.count_hits() relies on pallet.get_hits() generate its numbers."""
        with pytest.raises(ValueError):
            assert pallet.get_hit_count() == 3

    def test_count_hits_reports_hits_correctly(
        self, pallet_with_get_hits_run: Pallet
    ) -> None:
        pallet = pallet_with_get_hits_run
        assert pallet.get_hit_count() == 3

    def test_get_misses(self, pallet_with_get_hits_run: Pallet) -> None:
        """
        Ensure pallet.get_misses() only returns promise items known NOT to be in
        Open Library
        """
        pallet = pallet_with_get_hits_run

        assert pallet.solr_queried is True
        assert pallet.get_misses() == [
            PromiseItem(
                isbn="9782723496117",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=False,
                add_attempted=False,
                original_miss=True,
            ),
            PromiseItem(
                isbn="9783522182676",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=False,
                add_attempted=False,
                original_miss=True,
            ),
        ]

    def test_get_miss_count(self, pallet_with_get_hits_run: Pallet) -> None:
        """Ensure the miss count is correct."""
        pallet = pallet_with_get_hits_run
        assert pallet.solr_queried is True
        assert pallet.get_miss_count() == 2

    #######
    # There doesn't seem to be a good way to test whether pallet.add_items() actually
    # adds items, as mocking the Solr reply after add_items() is run just re-tests
    # pallet.get_hits().
    #######

    def test_add_misses_adds_miss_only_if_response_code_is_404(
        self, pallet_with_get_hits_run: Pallet
    ) -> None:
        """
        Ensure pallet.add_misses() only runs on items that are both misses AND, when
        the add is attempted, response.status_code is 404.
        """
        pallet = pallet_with_get_hits_run
        with requests_mock.Mocker() as m:
            m.get(
                "https://openlibrary.org/isbn/9782723496117",
                status_code=200,
                text="add not attempted",
            )
            m.get(
                "https://openlibrary.org/isbn/9783522182676",
                status_code=404,
                text="add attempted",
            )

            pallet.add_misses(0)
            added_misses = [item for item in pallet.items if item.add_attempted is True]
            assert added_misses == [
                PromiseItem(
                    isbn="9783522182676",
                    pallet="super_pallet_2020-09-21",
                    in_openlibrary=False,
                    add_attempted=True,
                    original_miss=True,
                ),
            ]

    def test_add_misses_updates_promise_item_status_for_status_code_200(
        self, pallet_with_get_hits_run: Pallet
    ) -> None:
        """
        When pallet.add_items() runs, if response.status_code == 200, then
        the pallet item should be updated to reflect in_library = True.
        An add should not be attempted.
        """
        pallet = pallet_with_get_hits_run
        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, status_code=200)

            pallet.add_misses(0)
            item = next(item for item in pallet.items if item.isbn == "9783522182676")
            assert item == PromiseItem(
                isbn="9783522182676",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=True,
                add_attempted=False,
                original_miss=True,
            )

    def test_add_misses_updates_pallet_attributes(
        self, pallet_with_get_hits_run: Pallet
    ) -> None:
        """
        Ensure running pallet.add_misses() updates {self.add_misses_run}.
        """
        # We just need a 404 from requests so that add_misses() runs.
        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, status_code=404)

            pallet = pallet_with_get_hits_run
            assert pallet.add_misses_run is False
            pallet.add_misses(0)
            assert pallet.add_misses_run is True

    def test_add_misses_updates_promise_items(
        self, pallet_with_get_hits_run: Pallet
    ) -> None:
        """
        Ensure that pallet.add_misses() updates {add_attempted} for the two missing
        promise items.
        """
        # We just need a 404 from requests so that add_misses() runs.
        with requests_mock.Mocker() as m:
            m.get(requests_mock.ANY, status_code=404)

            pallet = pallet_with_get_hits_run
            initial_added_misses = [
                item for item in pallet.items if item.add_attempted is True
            ]
            assert initial_added_misses == []

            pallet.add_misses(0)

            # Look for any promise items where add_attempted is True to reflect an
            # add attempt.
            second_added_misses = [
                item for item in pallet.items if item.add_attempted is True
            ]
            assert second_added_misses == [
                PromiseItem(
                    isbn="9782723496117",
                    pallet="super_pallet_2020-09-21",
                    in_openlibrary=False,
                    add_attempted=True,
                    original_miss=True,
                ),
                PromiseItem(
                    isbn="9783522182676",
                    pallet="super_pallet_2020-09-21",
                    in_openlibrary=False,
                    add_attempted=True,
                    original_miss=True,
                ),
            ]

    def test_get_original_misses(self, pallet_with_add_misses_run) -> None:
        """Ensure we can always get the original misses."""
        pallet = pallet_with_add_misses_run

        original_misses = [item for item in pallet.items if item.add_attempted is True]
        assert original_misses == [
            PromiseItem(
                isbn="9782723496117",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=False,
                add_attempted=True,
                original_miss=True,
            ),
            PromiseItem(
                isbn="9783522182676",
                pallet="super_pallet_2020-09-21",
                in_openlibrary=False,
                add_attempted=True,
                original_miss=True,
            ),
        ]


def test_write_misses(pallet_with_get_hits_run: Pallet):
    """Ensure write_misses() writes to disk."""
    pallet = pallet_with_get_hits_run
    p = Path("./data/super_pallet_2020-09-21_misses.tsv")
    if p.is_file():
        p.unlink()  # write_misses() will recreate this.
    pallet.write_misses()
    assert "9782723496117" in p.read_text()
    p.unlink()


def test_write_misses_will_not_write_if_file_exists(pallet_with_get_hits_run: Pallet):
    pallet = pallet_with_get_hits_run
    with pytest.raises(FileExistsError):
        pallet.write_misses()
        pallet.write_misses()


##########
# utils.py
##########


def test_get_last_five_promise_item_urls() -> None:
    with requests_mock.Mocker(json_encoder=JSONEncoder) as m:
        m.get(
            API_URL_LAST_X_ITEMS % 5,
            json=response_last_five_promise_items,
        )

        assert get_promise_item_urls(API_URL_LAST_X_ITEMS % 5) == [
            "https://archive.org/metadata/bwb_daily_pallets_2022-09-23",
            "https://archive.org/metadata/BWB-2022-09-23",
            "https://archive.org/metadata/super_pallet_2020-09-21",
            "https://archive.org/metadata/BWB-2022-09-22",
            "https://archive.org/metadata/bwb_daily_pallets_2022-09-20",
        ]


def test_get_file_if_exists(tmp_path):
    """Write some pickled data to disk, and unpickle and return it if it exists."""
    d: Path = tmp_path / "data"
    d.mkdir()
    serialized_data = pickle.dumps(iter(range(1)))
    p = d / "test_serialized_data.pickle"
    with p.open(mode="wb") as fp:
        fp.write(serialized_data)

    unserialized_data = get_file_if_exists(str(p.resolve()))
    if unserialized_data:
        assert next(pickle.loads(unserialized_data)) == 0


def test_get_file_if_exists_returns_none_if_file_does_not_exist():
    assert get_file_if_exists("blob") is None


def test_dedup_isbns() -> None:
    """
    Ensure dedup_isbns properly detects ISBN 10s that are ISBN 13s and
    removes the ISBN 10s.
    """
    assert dedup_isbns(isbns) == {
        "9788189999520",
        "9781405892469",
        "9782723496117",
        "BWBM52088056",
        "9783522182676",
        "9782880462703",
    }


##########
# @app.command tests.
##########


def test_check_latest() -> None:
    """Verify that check_latest properly marks items as hits and misses."""
    FIRST_BATCH: Final = "https://openlibrary.org/search.json?fields=isbn&q=isbn:(9788189999520%20OR%209782880462703)"  # noqa E501
    SECOND_BATCH: Final = "https://openlibrary.org/search.json?fields=isbn&q=isbn:(9783522182676%20OR%209781405892469)"  # noqa E501
    THIRD_BATCH: Final = "https://openlibrary.org/search.json?fields=isbn&q=isbn:(9782723496117)"  # noqa E501
    ONE_BIG_BATCH: Final = "https://openlibrary.org/search.json?fields=isbn&q=isbn:(9781405892469%20OR%209782723496117%20OR%209782880462703%20OR%209783522182676%20OR%209788189999520)"  # noqa E501
    with requests_mock.Mocker(json_encoder=JSONEncoder) as m:
        m.get(API_URL_LAST_X_ITEMS % 1, json=response_latest_promise_item)
        m.get(
            "https://archive.org/metadata/super_pallet_2020-09-21",
            json=response_get_promise_item_isbns,
        )
        m.get(API_URL_LAST_X_ITEMS % 1, json=response_latest_promise_item)
        m.get(FIRST_BATCH, json=response_initial_query)
        m.get(SECOND_BATCH, json=response_initial_query)
        m.get(THIRD_BATCH, json=response_initial_query)
        m.get(ONE_BIG_BATCH, json=response_initial_query)
        check_latest()

    p = Path("./data/super_pallet_2020-09-21.pickle")
    with p.open(mode="rb") as fp:
        pallet = pickle.loads(fp.read())

        print(pallet)

        assert next(
            item
            for item in pallet.items
            if (item.isbn == "9788189999520" and item.in_openlibrary is True)
        )
        assert next(
            item
            for item in pallet.items
            if (item.isbn == "9782723496117" and item.in_openlibrary is False)
        )

    p = Path("./data/super_pallet_2020-09-21_misses.tsv")
    p.unlink()
