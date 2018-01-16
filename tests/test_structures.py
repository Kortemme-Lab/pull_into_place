#!/usr/bin/env python3

import numpy as np, pandas as pd
from pull_into_place import structures
from pprint import pprint

def test_find_pareto_front():
    # Create a grid of points for us to check the Pareto front on.  Include one 
    # column where smaller is better (x) and another where bigger is better 
    # (y).  Also include a column that doesn't participate in the Pareto front 
    # search.
    data = [
        {'x': x, 'y': y, 'z': 0}
        for x in [1,2,4]
        for y in [1,3,4]
    ]
    cols = 'x', 'y'
    df = pd.DataFrame(data)
    meta = {
            'x': structures.ScoreMetadata('x'),
            'y': structures.ScoreMetadata('y', dir='+'),
    }
    print(df)

    front = structures.find_pareto_front(df, meta, cols)
    assert set(front.index) == {2}

    front = structures.find_pareto_front(df, meta, cols, depth=2)
    assert set(front.index) == {2, 1, 5}

    front = structures.find_pareto_front(df, meta, cols, depth=3)
    assert set(front.index) == {2, 1, 5, 0, 4, 8}

    # I chose epsilon=60 to divide the more clustered points in the top-left 
    # from the more individual points in the bottom-right.
    front = structures.find_pareto_front(df, meta, cols, depth=1, epsilon=60)
    assert set(front.index) == {2}

    front = structures.find_pareto_front(df, meta, cols, depth=2, epsilon=60)
    assert set(front.index) == {2, 0, 8}

    front = structures.find_pareto_front(df, meta, cols, depth=3, epsilon=60)
    assert set(front.index) == {2, 0, 8, 6}




