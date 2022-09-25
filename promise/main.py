import requests
import pickle
import time
import typer
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from itertools import islice
from typing import Final
from collections.abc import Iterator

API_URL: Final = "https://archive.org/advancedsearch.php?q=collection%3Aprotodonationitems&fl%5B%5D=identifier&sort%5B%5D=addeddate+desc&sort%5B%5D=&sort%5B%5D=&rows=1&page=1&output=json"  # noqa E501
OL_SOLR_URL: Final = "https://openlibrary.org/search.json?fields=isbn&q=isbn:(%s)"
ADD_BOOK_BY_ISBN_URL: Final = "https://openlibrary.org/isbn/%s"
QueryType = dict[str, int | list[str] | str]


@dataclass
class Batch:
    """
    Batch stores the batch information for a single batch of promise item ISBNs.

    NOTE: All values are based on the last run of {self.check_if_isbns_in_openlibrary()}

    {promise_item_isbns}: the set of isbns in this batch, which come from either a
        previous run or from a query of the latest promise item.
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

    def check_if_isbns_in_openlibrary(self) -> None:
        """
        Process {self.promise_items} by turning their ISBNs into a Solr query. After
        query Solr, use get_query_isbns() grab all the ISBNs from the Solr response,
        and then update all the values in {batch} accordingly.
        """
        query = " OR ".join(self.promise_item_isbns)
        query_result = requests.get(OL_SOLR_URL % query).json()
        isbns_from_query = get_query_isbns(query_result)
        self.hits = self.promise_item_isbns.intersection(isbns_from_query)
        self.misses = self.promise_item_isbns - isbns_from_query
        self.in_ol_count = len(self.hits)
        self.not_in_ol_count = len(self.misses)


@dataclass
class BatchStats:
    """
    Record the stats for the batch as a whole. This is written to disk so the the
    current and immediately-past run can be compared.

    This also contains misses which can be added for using with --add-misses.
    """

    promise_item_isbns: set[str] = field(default_factory=set)
    hits: set[str] = field(default_factory=set)
    misses: set[str] = field(default_factory=set)
    total: int = 0
    in_ol_count: int = 0
    not_in_ol_count: int = 0
    last_run: datetime = datetime.now()

    def loader(self, batches: list[Batch]) -> None:
        """Uses the already processed {batches} to populate the values."""
        for batch in batches:
            self.promise_item_isbns.update(batch.promise_item_isbns)
            self.hits.update(batch.hits)
            self.misses.update(batch.misses)
            self.total += batch.total
            self.in_ol_count += batch.in_ol_count
            self.not_in_ol_count += batch.not_in_ol_count

        self.last_run = datetime.now()

    def add_misses(self, delay_in_ms: int) -> None:
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
            print(f"Added: {miss}")
            time.sleep(sleep_time)


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


def main(add_misses: bool = False, query_misses: bool = False) -> None:
    """
    The entrypoint for the script.

    if add_misses is True (i.e. the script was run with --add-misses):
        This will load the data from the prior run and use them to try to add misses
        via https://openlibrary.org/isbn/{missed_isbn}

    if query_misses is True (i.e. the script was run with --query-misses):
        This is to be run *after* --add-misses.

        The only way this is different from an initial run is that it loads data from
        the last run, prints it to the screen, and uses the ISBNs from the last run
        so it's possible to see what using --add-misses did, if anything.

    If neither --add-misses nor --query-misses is added on the command line, then:
        Get the URL for the latest promise items, acquire its ISBNs, and slice the ISBNs
        into chunks. Then place these ISBN chunks into into individual Batch instances.
        Then process each Batch instance and add up the total number of ISBNs that are
        in and not in the Open Library database. Finally, save the data to disk for
        potential later use with --add-misses or --query-misses.
    """
    p = Path("./batch_stats.pickle")
    url = get_promise_item_metadata_url(API_URL)

    # For --add-misses, just load the previous run data, print it, and add misses.
    if add_misses:
        with p.open("rb") as fp:
            previous_batch: BatchStats = pickle.loads(fp.read())
            # previous_batch.add_misses(1000)
            print("Currently disabled, but here are the misses I would add")
            print(f"{previous_batch.misses}")
            return

    # For --query-misses, just print data from the last run, load ISBNs from the last
    # run, and continue as normal.
    elif query_misses:
        with p.open("rb") as fp:
            previous_batch: BatchStats = pickle.loads(fp.read())  # type: ignore[no-redef]
            isbns = iter(previous_batch.promise_item_isbns)
            print(f"Stats from the last run ({previous_batch.last_run.ctime()})")
            print(f"Total number: {previous_batch.total}")
            print(f"Total in: {previous_batch.in_ol_count}")
            print(f"total out: {previous_batch.not_in_ol_count}")
            print("\n")

    # If not loading ISBNs from the last run (see query_misses), then load from the
    # web.
    else:
        isbns = get_promise_item_isbns(url)

    batches = make_batches(isbns, 100)

    # Go through each batch item, check its ISBNs, update the values within the batch,
    # and save the batch itself to processed_batches for use with BatchStats().
    processed_batches = []
    for batch in batches:
        batch.check_if_isbns_in_openlibrary()
        processed_batches.append(batch)

    # Load all the data from each batch object into a single BatchStats() instance
    # which is saved for later using with --add-misses and --query-misses.
    batch_stats = BatchStats()
    batch_stats.loader(batches=processed_batches)

    print(f"Stats for this run ({batch_stats.last_run.ctime()})")
    print(f"Total number: {batch_stats.total}")
    print(f"Total in: {batch_stats.in_ol_count}")
    print(f"total out: {batch_stats.not_in_ol_count}")

    # Finally, save the data from this run for possible future use.
    with p.open(mode="wb") as fp:
        seralized_stats = pickle.dumps(batch_stats)
        fp.write(seralized_stats)


if __name__ == "__main__":
    typer.run(main)
