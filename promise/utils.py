from collections.abc import Iterator, Iterable
import textwrap
from urllib.parse import parse_qs
from isbnlib import to_isbn13
from pathlib import Path
from typing import TypeVar, Final

import requests

from promise.constants import PROMISE_ITEM_URL_PREFIX

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


def solr_isbn_query(isbns: list[str], OL_SOLR_URL: str) -> set[str]:
    """
    Process ISBNS (taken from self.promise_items.isbn) by turning their ISBNs into a
    Solr query. After querying Solr, use get_query_isbns() grab all the ISBNs from the
    Solr response, before returning them.

    The query ends up being of the form:
    https://openlibrary.org/search.json?fields=isbn&q=isbn:(ISBN1 OR ISBN2 OR ISBN3)

    Returns a set of every ISBN in the Solr response.
    """
    QUERY: Final = " OR ".join(isbns)
    query_result = requests.get(OL_SOLR_URL % QUERY)
    query_result_json = query_result.json()

    # The limit must be greater than than numFound or we won't see the full list of
    # matches.
    tentative_limit = parse_qs(OL_SOLR_URL).get("limit")
    assert isinstance(
        tentative_limit, list
    ), "OL_SOLR_URL must include a limit. E.g. limit=1000"
    limit = int(tentative_limit[0])

    if query_result_json.get("numFound") > limit:
        raise ValueError(
            textwrap.fill(
                textwrap.dedent(
                    """
            'num_found' exceeds 'limit'. The 'limit' value in the API request must
            exceed 'num_found' in the query response. Try increasing the limit
            value in OL_SOLR_URL.
            """
                )
            )
        )

    if query_result.status_code != 200:
        raise ValueError(f"Error while querying Solr: {query_result.status_code}")

    return get_query_isbns(query_result_json)


def get_promise_item_urls(API_URL_LAST_X_ITEMS: str) -> list[str]:
    """
    Get the last X promise item urls from the search query URL that lists
    primise item identifiers.
    E.g., passing the following URL, which lists the 5 most recent promise items:
    https://archive.org/advancedsearch.php?q=collection%3Aprotodonationitems&fl[]=identifier&sort[]=addeddate+desc&sort[]=&sort[]=&rows=5&page=1&output=json  # noqa E501

    would return:
    >>> ['https://archive.org/metadata/bwb_daily_pallets_2022-09-23',
         'https://archive.org/metadata/BWB-2022-09-23',
         'https://archive.org/metadata/bwb_daily_pallets_2022-09-21',
         'https://archive.org/metadata/BWB-2022-09-22',
         'https://archive.org/metadata/bwb_daily_pallets_2022-09-20']
    """
    promise_item_tags: list[dict[str, str]] = requests.get(API_URL_LAST_X_ITEMS).json()[
        "response"
    ]["docs"]
    return [PROMISE_ITEM_URL_PREFIX + item["identifier"] for item in promise_item_tags]


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


def dedup_isbns(isbns: Iterable[str | int]) -> set[str]:
    """
    Take an iterable of ISBNs, attempt to convert them to ISBN 13s using isbnlib.

    NOTE: this will NOT filter out 'bad' ISBNs. If isbnlib cannot convert the "ISBN"
    to ISBN 13, that "bad" ISBN will be included in the output. This means obviously
    bad ISBNs such as "BWB123" will remain. They can be dealt with elsewhere. This
    only deduplicates ISBN 10 and 13 when they're the same.
    """
    output_isbns: set[str] = set()
    for isbn in isbns:
        converted_isbn = to_isbn13(str(isbn))
        # isbnlib converts bad ISBNs to an empty string. Preserve them.
        if converted_isbn == "":
            output_isbns.add(str(isbn))  # isbnlib converts to str, so keep consistent.
        else:
            output_isbns.add(converted_isbn)

    return output_isbns
