from collections.abc import Iterator
from pathlib import Path
from typing import TypeVar

import requests

from promise.constants import OL_SOLR_URL

QueryType = dict[str, int | list[str] | str]
T = TypeVar("T")


def make_batches(items: list[T], size: int) -> list[list[T]]:
    """
    Slice {items} into batches of {size}. Return lists of {size} holding the
    contents of each batch's items.
    """
    return [items[i : i + size] for i in range(0, len(items), size)]


def get_query_isbns(query_result: QueryType) -> set[str]:
    """
    Take a Solr {query_result} and return a set of the ISBNs contained therein.

    {query_result} looks like:
        {'numFound': 2,
        'start': 0,
        'numFoundExact': True,
        'docs': [{'isbn': ['9781405892469', '1405892463']},
         {'isbn': ['9788189999520', '8189999524']}],
        'num_found': 2,
        'q': 'isbn:(9788189999520 OR 9781405892469 OR 9782723496117)',
        'offset': None}

    get_isbns(result)
    >>> {'1405892463', '8189999524', '9781405892469', '9788189999520'}
    """
    isbns: set[str] = set()
    docs = query_result.get("docs")
    # Go through the docs and add the ISBNS to {isbns}
    if docs and isinstance(docs, list):
        for doc in docs:
            if isinstance(doc, dict) and (i := doc.get("isbn")):
                isbns.update(i)

    return isbns


def solr_isbn_query(isbns: list[str]) -> set[str]:
    """
    Process {self.promise_items} by turning their ISBNs into a Solr query. After
    query Solr, use get_query_isbns() grab all the ISBNs from the Solr response,
    and then update all the values in {batch} accordingly.

    Returns a set of every ISBN in the Solr response.
    """
    query = " OR ".join(isbns)
    query_result: QueryType = requests.get(OL_SOLR_URL % query).json()
    return get_query_isbns(query_result)


def get_promise_item_urls(API_URL_LAST_X_ITEMS: str) -> list[str]:
    """
    Get the last X promise item urls. E.g., if the URL was created with 5.
    >>> ['https://archive.org/metadata/bwb_daily_pallets_2022-09-23',
         'https://archive.org/metadata/BWB-2022-09-23',
         'https://archive.org/metadata/bwb_daily_pallets_2022-09-21',
         'https://archive.org/metadata/BWB-2022-09-22',
         'https://archive.org/metadata/bwb_daily_pallets_2022-09-20']
    """
    url_prefix = "https://archive.org/metadata/"
    promise_item_tags: list[dict[str, str]] = requests.get(API_URL_LAST_X_ITEMS).json()[
        "response"
    ]["docs"]
    return [f"{url_prefix}" + item["identifier"] for item in promise_item_tags]


def get_promise_item_isbns(url: str) -> Iterator[str]:
    """Return ISBNs from a promise item metadata url as an iterator of ISBNs"""
    identifiers: list[str] = requests.get(url).json()["extrameta"]["isbn"]
    deduplicated_identifiers = set(identifiers)
    return (
        str(item)
        for item in deduplicated_identifiers
        if not str(item).startswith("BWB")
    )


def get_all_original_misses() -> None:
    """
    For all runs that have been done for which there is a .pickle file in ./data,
    write the ISBNs that were originally missing to a CSV.
    """
    pass


def create_data_dir_if_needed() -> None:
    """Create the data directory if needed."""
    p = Path("./data")
    if not p.is_dir():
        p.mkdir()


def get_file_if_exists(filepath: str) -> bytes | None:
    """
    Check if a filename exists, and if it does, return it in bytes.

    This is intended to be used in conjunction with pickled data, and it is up to the
    caller to know what these bytes are.
    """
    p = Path(filepath)
    if not p.is_file():
        return None

    with p.open(mode="rb") as fp:
        return fp.read()
