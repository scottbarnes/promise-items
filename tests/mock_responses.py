"""Mock responses the various tests. """

response_get_promise_item_isbns = {
    "created": 1664134349,
    "d1": "ia601502.us.archive.org",
    "d2": "ia801502.us.archive.org",
    "dir": "/7/items/super_pallet_2022-09-21",
    "extrameta": {
        "isbn": [
            9788189999520,
            9781405892469,
            1405892463,
            9782723496117,
            "BWBM52088056",
            9783522182676,
            9782880462703,
        ]
    },
}

response_initial_query = {
    "numFound": 3,
    "start": 0,
    "numFoundExact": True,
    "docs": [
        {
            "isbn": [
                "2880460794",
                "2880462703",
                "9782880460792",
                "9780823062010",
                "9782880462703",
                "0823062015",
            ]
        },
        {"isbn": ["9781405892469", "1405892463"]},
        {"isbn": ["9788189999520", "8189999524"]},
    ],
    "num_found": 3,
    "q": "isbn:(9788189999520 OR 9781405892469 OR 9782723496117 OR 9783522182676 OR 9782880462703)",  # noqa E501
    "offset": None,
}

response_after_importing_one_book = {
    "numFound": 4,
    "start": 0,
    "numFoundExact": True,
    "docs": [
        {
            "isbn": [
                "2880460794",
                "2880462703",
                "9782880460792",
                "9780823062010",
                "9782880462703",
                "0823062015",
            ]
        },
        {"isbn": ["9781405892469", "1405892463"]},
        {"isbn": ["9788189999520", "8189999524"]},
        {"isbn": ["2723496112", "9782723496117"]},
    ],
    "num_found": 4,
    "q": "isbn:(9788189999520 OR 9781405892469 OR 9782723496117 OR 9783522182676 OR 9782880462703)",  # noqa E501
    "offset": None,
}

response_latest_promise_item = {
    "responseHeader": {
        "status": 0,
        "QTime": 36,
        "params": {
            "query": "( collection:protodonationitems )",
            "qin": "collection:protodonationitems",
            "fields": "identifier",
            "wt": "json",
            "sort": "addeddate desc",
            "rows": "5",
            "start": 0,
        },
    },
    "response": {
        "numFound": 1487,
        "start": 0,
        "docs": [
            {"identifier": "super_pallet_2020-09-21"},
        ],
    },
}

response_last_five_promise_items = {
    "responseHeader": {
        "status": 0,
        "QTime": 36,
        "params": {
            "query": "( collection:protodonationitems )",
            "qin": "collection:protodonationitems",
            "fields": "identifier",
            "wt": "json",
            "sort": "addeddate desc",
            "rows": "5",
            "start": 0,
        },
    },
    "response": {
        "numFound": 1487,
        "start": 0,
        "docs": [
            {"identifier": "bwb_daily_pallets_2022-09-23"},
            {"identifier": "BWB-2022-09-23"},
            {"identifier": "super_pallet_2020-09-21"},
            {"identifier": "BWB-2022-09-22"},
            {"identifier": "bwb_daily_pallets_2022-09-20"},
        ],
    },
}
