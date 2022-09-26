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
There are really just two commands: `check-latest`, and `add-missing`.
Each command takes an optional count.

To check the latest promise item for hits and misses:
- `python promise/main.py check-latest`

To check the last ten promise items for hits and misses:
- `python promise/main.py check-latest --count 10`

To add the latest promise item's misses to Open Library:
- `python promise/main.py add-missing`

To add the misses for the latest ten promise items to Open Library:
- `python promise/main.py add-missing --count 10`

## Logs
State for the various promise items is held in `./data`, so it's possible to unpickle
the data there and analyze a particular promise item.

All the original misses for each promise item are stored as tab separated value files
in `./data` after `check-latest` is run (for the first time), and they're tagged with
the promise item's name.
