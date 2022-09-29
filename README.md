# Promise Item Checker
### A tool to parse promise items from https://archive.org/details/protodonationitems?sort=-addeddate, check if they are in Open Library, and optionally add them to Open Library.

## Requirements
- [Python >= 3.10](https://www.python.org/downloads/release/python-3100/)
- [Poetry](https://github.com/python-poetry/poetry) ([Installation](https://github.com/python-poetry/poetry#installation))

## Get the source
`git clone git@github.com:scottbarnes/promise-items.git`

## Using Poetry
- `cd /path/to/cloned/promise`
- `poetry install`
- `poetry run python promise/main.py --help`


Optionally, to open a shell within the Poetry virtual environment, where commands can be
invoked directly:
- `poetry shell`
- `python promise/main.py --help`

## Run the program
There are really just two commands: `check`, and `add-missing`.
Each command takes an optional count or a URL directly to a promise item.

To check the latest promise item for hits and misses:
- `poetry run python promise/main.py check`

To check the last ten promise items for hits and misses:
- `poetry run python promise/main.py check --count 10`

To check the hits and misses for a specific promise item, visit https://archive.org/details/protodonationitems?&sort=-addeddate
Then from there, copy the URL of the item you want, such as https://archive.org/details/bwb_daily_pallets_2022-09-21 for the item "Pallets from BWB for 2022-09-21"
- `poetry run python promise/main.py check --direct-url=https://archive.org/details/bwb_daily_pallets_2022-09-21`

To add the latest promise item's misses to Open Library:
- `poetry run python promise/main.py add-missing`

To add the misses for the latest ten promise items to Open Library:
- `poetry run python promise/main.py add-missing --count 10`

To add the misses for a specific promise item, follow the directions above under
`check`, then do something similar to:
- `poetry run python promise/main.py add-missing --direct-url=https://archive.org/details/bwb_daily_pallets_2022-09-21`

Finally, by default `add-missing` will skip ISBNs for which an add was already attempted.
To overwrite this default behavior, supply `--no-skip-attempted` to `add-missing`:
- `poetry run python promise/main.py add-missing --count 5 --no-skip-attempted`


## Logs
State for the various promise items is held in `./data`, so it's possible to unpickle
the data there and analyze a particular promise item.

All the original misses for each promise item are stored as tab separated value files
in `./data` after `check` is run (for the first time), and they're tagged with
the promise item's name.
