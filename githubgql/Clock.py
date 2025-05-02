from __future__ import annotations
import sys
from time import time

from githubgql.Config import Config


class Clock:
    """A simple class to time blocks of code via `with` statements

    * Turn on/off via the clock_on key in config.yml
    * The time value on the left is the total time since first use of Clock (it may be useful to trigger at application start to initialize the start time).
    * The time value on the right is the specific time for this step.

    Usage::

        with Clock("Doing a thing I want to optimize"):
            do_the_thing()

    Output::

        (0.000s) >> Doing a thing I want to optimize… done (0.147s)
    """

    root_time = None

    def __init__(self, msg: str):
        self.enter_time = None
        self.msg = msg
        Clock.root_time = Clock.root_time or time()

    def __enter__(self):
        if Config.get().clock_on:
            self.enter_time = time()
            print(f"({(time() - Clock.root_time):.3f}s) >> {self.msg}", end="… ", file=sys.stderr)

    def __exit__(self, exc_type, exc_value, traceback):
        if Config.get().clock_on:
            print(f"done ({(time() - self.enter_time):.3f}s)", sys.stderr)
