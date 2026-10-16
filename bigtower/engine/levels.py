"""Campaign definitions: maps, starting economy and wave compositions.

A wave is a list of (enemy_key, count, interval_seconds) groups; groups spawn
in parallel, each on its own timer.
"""

def _w(*groups):
    return list(groups)


LEVELS = [
    {
        "number": 1,
        "name": "Greenfield Road",
        "map": "level1.txt",
        "gold": 220,
        "lives": 20,
        "waves": [
            _w(("grunt", 6, 1.3)),
            _w(("grunt", 9, 1.0)),
            _w(("grunt", 6, 1.0), ("runner", 4, 1.4)),
            _w(("armored", 5, 2.0)),
            _w(("runner", 10, 0.8)),
            _w(("grunt", 8, 0.8), ("armored", 4, 2.2)),
            _w(("jet", 8, 1.1)),
            _w(("armored", 8, 1.6)),
            _w(("tank", 1, 0), ("runner", 8, 0.9)),
            _w(("tank", 2, 6.0), ("armored", 6, 1.6), ("jet", 6, 1.2)),
        ],
    },
    {
        "number": 2,
        "name": "Twin Brooks",
        "map": "level2.txt",
        "gold": 250,
        "lives": 20,
        "waves": [
            _w(("grunt", 8, 1.1)),
            _w(("runner", 8, 1.0)),
            _w(("armored", 5, 1.9), ("grunt", 6, 1.0)),
            _w(("jet", 7, 1.2)),
            _w(("runner", 12, 0.7)),
            _w(("armored", 8, 1.5)),
            _w(("jet", 10, 0.9), ("grunt", 8, 0.9)),
            _w(("tank", 1, 0), ("armored", 6, 1.7)),
            _w(("runner", 14, 0.6), ("jet", 6, 1.3)),
            _w(("armored", 10, 1.3)),
            _w(("tank", 2, 5.0), ("runner", 10, 0.7)),
            _w(("tank", 2, 5.0), ("armored", 8, 1.4), ("jet", 8, 1.0)),
        ],
    },
    {
        "number": 3,
        "name": "Serpent's Coil",
        "map": "level3.txt",
        "gold": 280,
        "lives": 15,
        "waves": [
            _w(("grunt", 8, 1.0), ("runner", 4, 1.2)),
            _w(("armored", 6, 1.7)),
            _w(("runner", 12, 0.7)),
            _w(("jet", 9, 1.0)),
            _w(("armored", 8, 1.4), ("grunt", 8, 0.8)),
            _w(("tank", 1, 0), ("runner", 10, 0.8)),
            _w(("jet", 12, 0.8)),
            _w(("armored", 10, 1.2), ("runner", 8, 0.9)),
            _w(("tank", 2, 4.0), ("grunt", 10, 0.7)),
            _w(("jet", 12, 0.7), ("runner", 8, 0.8)),
            _w(("armored", 12, 1.1)),
            _w(("tank", 2, 4.0), ("jet", 8, 1.0), ("runner", 10, 0.6)),
            _w(("armored", 12, 1.0), ("grunt", 12, 0.6)),
            _w(("tank", 3, 3.5), ("armored", 8, 1.3)),
            _w(("tank", 4, 3.0), ("jet", 10, 0.8), ("runner", 12, 0.5)),
        ],
    },
]
