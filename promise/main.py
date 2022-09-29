import csv
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import requests
import typer

from rich.progress import track

from promise.constants import (
    ADD_BOOK_BY_ISBN_URL,
    API_URL_LAST_X_ITEMS,
    PROMISE_ITEM_URL_PREFIX,
    OL_SOLR_URL,
)
from promise.utils import (
    create_data_dir_if_needed,
    dedup_isbns,
    get_file_if_exists,
    get_promise_item_urls,
    make_batches,
    solr_isbn_query,
)

app = typer.Typer()


@dataclass
class PromiseItem:
    """
    Individual promise items that belong to a pallet. Each PromiseItem represents an
    a donated item in a pallet.
    """

    isbn: str
    pallet: str
    in_openlibrary: bool = False
    add_attempted: bool = False
    original_miss: bool = None  # type: ignore[assignment]

    def __lt__(self, other: "PromiseItem") -> bool:
        return self.isbn < other.isbn


@dataclass
class Pallet:
    """
    A pallet of promise items. This class allows for checking whether pallet
    items are in Open Library, recording the items that were not originally
    in Open Library, and attempting to add the missing items to Open Library.

    See https://archive.org/details/protodonationitems?sort=-addeddate generally
    and see https://archive.org/details/BWB-2022-09-22 specifically for examples
    of pallets and their contents.
    """

    url: str
    batch_size: int
    # self.items is created from a set. Shamefully, this was easier than rewriting
    # tests that rely on self.items being ordered.
    items: list[PromiseItem] = field(default_factory=list)
    solr_queried: bool = False
    add_misses_run: bool = False
    name: str = ""
    created: datetime = datetime.now()

    def __post_init__(self) -> None:
        """
        Set {self.name} to the end of the URL, as that has a human-readable
        pallet name. Additionally, populate {self.items} with all of the promise
        items contained in the pallet, as determined by ISBNs contained
        in {self.url}.
        """
        self.name = self.url.split("/")[-1]
        self.populate_items()

    def __len__(self) -> int:
        return len(self.items)

    def get_hit_count(self) -> int:
        """
        Count the promise items known to be in Open Library based on the most recent
        self.get_hits() run.
        """
        if self.solr_queried is False:
            raise ValueError("self.solr_queried is False. Run self.get_hits() first.")

        return len([item for item in self.items if item.in_openlibrary is True])

    def get_miss_count(self) -> int:
        """
        Count the promise items known NOT to be in Open Library, based on the most
        recent self.get_hits() run.
        """
        if self.solr_queried is False:
            raise ValueError("self.solr_queried is False. Run self.get_hits() first.")

        return len([item for item in self.items if item.in_openlibrary is False])

    def get_hits(self) -> list[PromiseItem]:
        """
        Get the hits (i.e. the PromiseItems) in Open Library and update the promise
        items accordingly.

        This queries Solr by ISBN in batches of {self.batch_size}. Then for each batch,
        it updates the batch's promise items to reflect whether the item is in Solr.

        NOTE: This has side effects, namely updating promise items. This may need to
        be two functions.
        """
        batches = make_batches(self.items, self.batch_size)
        # Gather the batch's ISBNs and query Solr with them.
        batch: list[PromiseItem]  # track breaks typing.
        for batch in track(batches, description="Checking hits and misses:"):
            batch_isbns = [item.isbn for item in batch]
            solr_isbns = solr_isbn_query(batch_isbns, OL_SOLR_URL)

            # Update each batch PromiseItem with its hit/miss status.
            for item in batch:
                if item.isbn in solr_isbns:
                    item.in_openlibrary = True
                else:
                    item.in_openlibrary = False

                # This sets only on the first run. So long as the state is saved
                # and read from disk, it enables comparison between original misses
                # and misses that continue even after add attempts.
                if item.original_miss is None:
                    item.original_miss = item.isbn not in solr_isbns

        if self.solr_queried is False:
            self.solr_queried = True

        return [item for item in self.items if item.in_openlibrary is True]

    def get_misses(self) -> list[PromiseItem]:
        """
        Return promise items known NOT to be in Open Library as of the last run
        of self.get_hits().
        """
        if self.solr_queried is False:
            raise ValueError("self.solr_queried is False. Run self.get_hits() first.")

        return [item for item in self.items if item.in_openlibrary is False]

    def get_original_misses(self) -> list[PromiseItem]:
        """Return the original misses so can try to discern why they are missing."""
        return [item for item in self.items if item.original_miss is True]

    def get_original_miss_count(self) -> int:
        """Return the original miss count."""
        return len(self.get_original_misses())

    def add_misses(self, delay_in_ms: int, skip_attempted: bool) -> None:
        """
        Attempt to add missed promise items via /isbn/{isbn} with a millisecond delay
        of {delay_in_ms}.
        """
        if self.solr_queried is False:
            raise ValueError("self.solr_queried is False. Run self.get_hits() first.")

        sleep_time = delay_in_ms / 1000

        for miss in track(self.get_misses(), description="Adding missing items:"):
            # The default behavior is to skip adding misses for which an add
            # has already been attempted, as many books can't be automatically
            # imported and will be perpetuala misses.
            if skip_attempted is True and miss.add_attempted is True:
                continue

            requests.get(ADD_BOOK_BY_ISBN_URL % miss.isbn)

            print(f"Add attempted: {miss}")
            miss.add_attempted = True
            time.sleep(sleep_time)

        self.add_misses_run = True

    def populate_items(self) -> None:
        """
        Populate {self.items} by reading the ISBN values from {self.url}, and
        creating promise items for each ISBN.
        """
        ids: list[str | int] = requests.get(self.url).json()["extrameta"]["isbn"]
        dedupe_ids = dedup_isbns(ids)
        self.items = sorted(
            [
                PromiseItem(isbn=item, pallet=self.name)
                for item in dedupe_ids
                if not item.startswith("BWB")
            ]
        )

    def write_misses(self) -> None:
        """
        Write a pallet's original misses to a TSV for later examination as to why
        they were not added in the first place.

        NOTE: this should only be called on an initial run, as it is meant to
        preserve a record of missed items before any adding.
        """
        create_data_dir_if_needed()

        miss_file = Path(f"./data/{self.name}_misses.tsv")
        if miss_file.is_file():
            raise FileExistsError(f"{miss_file} already exists.")

        with miss_file.open(mode="a") as fp:
            writer = csv.writer(fp, delimiter="\t")
            original_misses = self.get_original_misses()
            for miss in original_misses:
                now = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
                writer.writerow([now, miss.pallet, miss.isbn])

    def get_item_by_isbn(self, isbn: str) -> PromiseItem | None:
        """Get a PromiseItem from the pallet by ISBN."""
        item = next((item for item in self.items if item.isbn == isbn), None)
        if item is None:
            raise KeyError(f"ISBN not in pallet: {isbn}")

        return item


@app.command()
def check(count: int = 1, direct_url: str = "") -> None:
    """
    Check hits and misses for the last {count} promise items. Also writes the
    original misses to disk as a TSV in ./data if they're not saved.
    """
    create_data_dir_if_needed()

    # If the user passes a URL, create a URL list of only the passed item. Otherwise
    # parse the API output to create the relevant URLs to hit for the ISBNs.
    if direct_url != "":
        name = direct_url.split("/")[-1]
        print(f"Checking promise item: {name}")
        urls = [PROMISE_ITEM_URL_PREFIX + name]
    else:
        print(f"Checking latest {count} items:\n")
        urls = get_promise_item_urls(API_URL_LAST_X_ITEMS % count)

    for url in urls:
        # Load data from a prior run if it exists, to preserve original_miss count.
        name = url.split("/")[-1]
        data_from_previous_run = get_file_if_exists(f"./data/{name}.pickle")
        if data_from_previous_run:
            print(f"Loading data from previous run: {name}")
            pallet: Pallet = pickle.loads(data_from_previous_run)
        else:
            pallet = Pallet(url=url, batch_size=100)

        pallet.get_hits()

        print(f"Details for {pallet.name}:")
        print(f"Total items: {len(pallet)}")
        print(f"Hits: {pallet.get_hit_count()}")
        print(f"Misses: {pallet.get_miss_count()}")
        print(f"Original miss count: {pallet.get_original_miss_count()}\n")

        # Store state for use by add-missing.
        file = Path(f"./data/{pallet.name}.pickle")
        with file.open(mode="wb") as fp:
            fp.write(pickle.dumps(pallet))

        # Write out the original misses as a TSV, if not already recorded.
        miss_file = Path(f"./data/{pallet.name}_misses.tsv")
        if not miss_file.is_file():
            pallet.write_misses()


@app.command()
def add_missing(
    count: int = 1, direct_url: str = "", skip_attempted: bool = True
) -> None:
    """Add misses from the last {count} promise items."""
    # If a new promise item is added between when the check is run, and this is run,
    # then the serialized data on disk won't match and this will error out because
    # it won't find the file(s) added. In that case, check will need to be
    # re-run.

    # If the user passes a URL, create a URL list of only the passed item. Otherwise
    # parse the API output to create the relevant URLs to hit for the ISBNs.
    if direct_url != "":
        name = direct_url.split("/")[-1]
        print(f"Checking promise item: {name}")
        urls = [PROMISE_ITEM_URL_PREFIX + name]
    else:
        print(f"Checking latest {count} items:\n")
        urls = get_promise_item_urls(API_URL_LAST_X_ITEMS % count)

    for url in urls:

        name = url.split("/")[-1]
        file = Path(f"./data/{name}.pickle")
        data_from_previous_run = get_file_if_exists(str(file))

        if data_from_previous_run:
            pallet: Pallet = pickle.loads(data_from_previous_run)
            print(f"Adding items for {name}")
            pallet.add_misses(delay_in_ms=500, skip_attempted=skip_attempted)

            # Store state to record any attribute updates (hits, attempt_added).
            with file.open(mode="wb") as fp:
                fp.write(pickle.dumps(pallet))
        else:
            print(f"Can't find {file}. Try running check first.")


if __name__ == "__main__":
    app()
