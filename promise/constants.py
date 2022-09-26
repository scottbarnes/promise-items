"""Constants"""
from typing import Final

ADD_BOOK_BY_ISBN_URL: Final = "https://openlibrary.org/isbn/%s"
API_URL_LAST_X_ITEMS: Final = "https://archive.org/advancedsearch.php?q=collection%%3Aprotodonationitems&fl[]=identifier&sort[]=addeddate+desc&sort[]=&sort[]=&rows=%s&page=1&output=json"  # noqa E501
OL_SOLR_URL: Final = "https://openlibrary.org/search.json?fields=isbn&q=isbn:(%s)"
