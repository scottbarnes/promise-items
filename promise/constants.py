"""Constants"""
from typing import Final

ADD_BOOK_BY_ISBN_URL: Final = "https://openlibrary.org/isbn/%s"
API_URL_LAST_X_ITEMS: Final = "https://archive.org/advancedsearch.php?q=collection:protodonationitems&fl[]=identifier&sort[]=addeddate+desc&sort[]=&sort[]=&rows=%s&page=1&output=json"  # noqa E501
OL_SOLR_URL: Final = (
    "https://openlibrary.org/search.json?fields=isbn&limit=1000&q=isbn:(%s)"
)
OL_SOLR_URL_LIMIT_1: Final = (
    "https://openlibrary.org/search.json?fields=isbn&limit=1&q=isbn:(%s)"
)
PROMISE_ITEM_URL_PREFIX: Final = "https://archive.org/metadata/"
