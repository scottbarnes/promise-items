import requests
import pickle
import time
from datetime import datetime
from dataclasses import dataclass, field
from itertools import islice
from typing import Final, Literal
from collections.abc import Iterator, Iterable

API_URL: Final = "https://archive.org/advancedsearch.php?q=collection%3Aprotodonationitems&fl%5B%5D=identifier&sort%5B%5D=addeddate+desc&sort%5B%5D=&sort%5B%5D=&rows=1&page=1&output=json"  # noqa E501
OL_SOLR_URL: Final = "https://openlibrary.org/search.json?fields=isbn&q=isbn:(%s)"
ADD_BOOK_BY_ISBN_URL: Final = "https://openlibrary.org/isbn/%s"
QueryType = dict[str, int | list[str] | str]


@dataclass
class Batch:
    """
    Batch stores the batch information for a single batch of promise item ISBNs.

    NOTE: All values are based on the last run of {self.check_if_isbns_in_openlibrary()}

    {promise_item_isbns}: the set of isbns in this batch.
    {hits}: the set of ISBNs from this batch known to be in Open Library.
    {misses}: the set of ISBNs from this batch known NOT to be in Open Library.
    {total}: the total number of isbns in the batch.
    {isbns_in_ol}: the number of ISBNs from the batch that are in Open Library.
    {isbns_not_in_ol}: the number of ISBNs from the batch that are NOT in Open Library.
    """

    promise_item_isbns: set[str]
    hits: set[str] = field(default_factory=set)
    misses: set[str] = field(default_factory=set)
    total: int = 0
    in_ol_count: int = 0
    not_in_ol_count: int = 0

    def __post_init__(self) -> None:
        self.total = len(self.promise_item_isbns)

    def check_if_isbns_in_openlibrary(
        # self, items: Literal["promise_items", "misses"]
        self,
    ) -> None:
        """
        Check if either {self.promise_items} or {selfmisses} are in the Open Library
        database.

        Process either {self.promise_items} or {self.misses} by turning their ISBNs
        into a Solr query. After query Solr, use get_query_isbns() grab all the ISBNs
        from the Solr response, and then update all the values in {batch} accordingly.
        """
        # Update values based on whether we're updating {promise_items} or {misses}.
        query = " OR ".join(self.promise_item_isbns)
        query_result = requests.get(OL_SOLR_URL % query).json()
        isbns_from_query = get_query_isbns(query_result)
        self.hits = self.promise_item_isbns.intersection(isbns_from_query)
        self.misses = self.promise_item_isbns - isbns_from_query
        self.in_ol_count = len(self.hits)
        self.not_in_ol_count = len(self.misses)

        # # Update values based on whether we're updating {promise_items} or {misses}.
        # match items:
        #     case "promise_items":
        #         query = " OR ".join(self.promise_item_isbns)
        #         query_result = requests.get(OL_SOLR_URL % query).json()
        #         isbns_from_query = get_query_isbns(query_result)
        #         self.hits = self.promise_item_isbns.intersection(isbns_from_query)
        #         self.misses = self.promise_item_isbns - isbns_from_query
        #         self.in_ol_count = len(self.hits)
        #         self.not_in_ol_count = len(self.misses)
        #     case "misses":
        #         query = " OR ".join(self.misses)
        #         query_result = requests.get(OL_SOLR_URL % query).json()
        #         isbns_from_query = get_query_isbns(query_result)
        #         self.hits.update(self.promise_item_isbns.intersection(isbns_from_query))
        #         self.misses = self.misses - isbns_from_query
        #         self.in_ol_count = len(self.hits)
        #         self.not_in_ol_count = len(self.misses)

    def add_misses(self, delay_in_ms: int):
        """
        Attempt to add items from {self.misses} to Open Library via
        https://openlibrary.org/isbn/{isbn}. {delay_in_ms} specifies the dalay in
        milliseconds between add attempts.
        """
        sleep_time = delay_in_ms / 1000
        for miss in self.misses:
            r = requests.get(ADD_BOOK_BY_ISBN_URL % miss)
            if r.status_code == 200:
                self.misses.remove(miss)
            time.sleep(sleep_time)


@dataclass
class BatchStats:
    """Record the stats for the batch as a whole. Use the misses to inform new batches."""

    promise_item_isbns: set[str] = field(default_factory=set)
    hits: set[str] = field(default_factory=set)
    misses: set[str] = field(default_factory=set)
    total: int = 0
    in_ol_count: int = 0
    not_in_ol_count: int = 0
    last_run: datetime = datetime.now()

    def loader(self, batches: Batch):
        """Uses the already processed {batches} to populate the values."""
        for batch in batches:
            self.promise_item_isbns.update(batch.promise_item_isbns)
            self.hits.update(batch.hits)
            self.misses.update(batch.misses)


def get_promise_item_metadata_url(API_URL: str) -> str:
    """Return the promise item metadata URL."""
    # promise_item_id = requests.get(API_URL).json()["response"]["docs"][0]["identifier"]
    # Stay on the same day as Mek's script
    promise_item_id = "bwb_daily_pallets_2022-09-21"
    return f"https://archive.org/metadata/{promise_item_id}"


def get_promise_item_isbns(url: str) -> Iterator[str]:
    """Return ISBNs from a promise item metadata url."""
    identifiers: list[str] = requests.get(url).json()["extrameta"]["isbn"]
    deduplicated_identifiers = set(identifiers)
    return (
        str(item)
        for item in deduplicated_identifiers
        if not str(item).startswith("BWB")
    )


def make_batches(isbns: Iterator[str], size: int) -> Iterator[Batch]:
    """
    Slice {isbns} into batches of {size}. Return Batch instances to hold the
    contents of each batch's ISBNs for later processing.
    """
    while batch_isbns := set(islice(isbns, size)):
        yield Batch(promise_item_isbns=batch_isbns)


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


def main() -> None:
    """
    Get the URL for the latest promise items, acquire its ISBNs, and slice the ISBNs
    into chunks. Then place these ISBN chunks into into individual Batch instances.
    Then process each Batch instance and add up the total number of ISBNs that are in
    and not in the Open Library database.
    """

    url = get_promise_item_metadata_url(API_URL)
    isbns = get_promise_item_isbns(url)
    batches = make_batches(isbns, 100)

    # Because batch.isbns holds each batch's ISBNs, this list could take a lot of
    # memory if the promise items have a lot of ISBNs. One solution would be to
    # clear batch.isbns after batch.process_isbns(), as they're no longer needed.
    processed_batches = []
    for batch in batches:
        batch.check_if_isbns_in_openlibrary()
        processed_batches.append(batch)

    total = sum(batch.total for batch in processed_batches)
    total_in = sum(batch.in_ol_count for batch in processed_batches)
    total_out = sum(batch.not_in_ol_count for batch in processed_batches)
    print(f"Total number: {total}")
    print(f"Total in: {total_in}")
    print(f"Total out: {total_out}")


if __name__ == "__main__":
    main()
