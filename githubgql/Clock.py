from __future__ import annotations
from time import time


class Clock:
    """A simple class to time blocks of code via `with` statements
    
    Usage:
        with Clock("Doing a thing I want to optimize"):
            do_the_thing()
    
    Output:
        (0.00s) >> Doing a thing I want to optimize… done (0.17s)
    """

    root_time = None

    def __init__(self, msg: str):
        self.enter_time = None
        self.msg = msg
        Clock.root_time = Clock.root_time or time()

    def __enter__(self):
        self.enter_time = time()
        print(f'({(time() - Clock.root_time):.2f}s) >> {self.msg}', end='… ')

    def __exit__(self, exc_type, exc_value, traceback):
        print(f'done ({(time() - self.enter_time):.2f}s)')
