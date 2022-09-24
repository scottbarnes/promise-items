import requests
from dataclasses import dataclass
from itertools import islice
from typing import Final, TypeVar
from collections.abc import Iterator

API_URL: Final = "https://archive.org/advancedsearch.php?q=collection%3Aprotodonationitems&fl%5B%5D=identifier&sort%5B%5D=addeddate+desc&sort%5B%5D=&sort%5B%5D=&rows=1&page=1&output=json"  # noqa E501
OL_SOLR_URL: Final = "https://openlibrary.org/search.json?fields=isbn&q=isbn:(%s)"
T = TypeVar("T")
QueryType = dict[str, int | list[str] | str]


@dataclass
class Batch:
    """
    Batch stores the batch information for a single batch of promise item ISBNs.

    {isbns}: the set of isbns in this batch
    {total}: the total number of isbns in the batch
    {isbns_in_ol}: the number of ISBNs from the batch that are in Open Library
    {isbns_not_in_ol}: the number of ISBNs from the batch that are NOT in Open Library
    """

    isbns: set[str]
    total: int = 0
    isbns_in_ol: int = 0
    isbns_not_in_ol: int = 0

    def __post_init__(self) -> None:
        self.total = len(self.isbns)

    def process_isbns(self) -> None:
        """
        Process {batch} by turning its ISBNs into a Solr query, querying Solr, using
        get_query_isbns() to get all the Solr ISBN results, and then updating
        {batch.isbns_in_ol} and {batch.isbns_not_in_ol}.
        """
        # Create the Solr query.
        query = " OR ".join(self.isbns)
        query_result = requests.get(OL_SOLR_URL % query).json()
        isbns_from_query = get_query_isbns(query_result)

        # Get the ISBNS already in Solr (i.e. the intersection of {batch.isbns} and
        # {isbns_from_query}) to update {batch} with what's in Open Library and what's not.
        intersection = self.isbns.intersection(isbns_from_query)
        self.isbns_in_ol = len(intersection)
        self.isbns_not_in_ol = self.total - self.isbns_in_ol


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
        yield Batch(isbns=batch_isbns)


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
        batch.process_isbns()
        processed_batches.append(batch)

    total = sum(batch.total for batch in processed_batches)
    total_in = sum(batch.isbns_in_ol for batch in processed_batches)
    total_out = sum(batch.isbns_not_in_ol for batch in processed_batches)
    print(f"Total number: {total}")
    print(f"Total in: {total_in}")
    print(f"Total out: {total_out}")


if __name__ == "__main__":
    main()
