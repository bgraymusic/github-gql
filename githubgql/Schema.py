from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

import dill
from graphql import GraphQLSchema, build_schema

from githubgql.Config import Config


class Schema:
    """Efficiently access and manage the Github GraphQL schema

    It takes an unacceptable amount of time (0.59s on my Apple M1 laptop) to
    load and parse the GitHub GraphQL schema, so do it only once and save the
    in-memory representation to use for every query. But we can also do better
    than that. By writing it back out in binary with dill (standard pickle
    fails on the lambda functions in the graphql library), all future reads
    can get the data in less than half the time (0.21s).

    I'd prefer to prep the binary file on install, but python does not support
    arbitrary code execution at install time. So we try to load the .bin and
    fail over to parsing and writing it out async.

    For now I'm not messing around with flock stuff and trying to make sure
    some other process doesn't kick off and load right as the first one is
    writing. The second __SHOULD__ throw an exception when it gets incomplete
    dill data and trigger the text load/parse flow. Then when it goes to write,
    it'll either get a PermissionError if the first proc still has it open, or
    else open it up and re-write the same data over. Either way, we should be
    functionally correct. Optimization at this point would be premature."""

    instance: Schema = None

    @staticmethod
    def get() -> GraphQLSchema:
        """Get the GitHub GraphQL schema as an in-memory object, for easy traversal"""
        Schema.instance = Schema.instance or Schema()
        return Schema.instance.schema

    def __init__(self):
        self.writing = None
        try:
            self._load_schema_from_binary_file()
        except OSError:
            self._parse_schema_from_text_file()
            self.executor = ThreadPoolExecutor()
            self.writing = self.executor.submit(Schema._write_out_binary_schema, self.schema)

    def _load_schema_from_binary_file(self):
        with open(f"{Path(__file__).parent}/{Config.get().gh_gql_schema_bin}", "rb") as f:
            self.schema: GraphQLSchema = dill.load(f)

    def _parse_schema_from_text_file(self):
        with open(f"{Path(__file__).parent}/{Config.get().github_graphql_schema}", "r") as f:
            schema_str = f.read()
            self.schema: GraphQLSchema = build_schema(schema_str, no_location=True)

    @staticmethod
    def _write_out_binary_schema(schema: GraphQLSchema):
        try:
            with open(f"{Path(__file__).parent}/{Config.get().gh_gql_schema_bin}", "wb") as f:
                sys.setrecursionlimit(5000)
                dill.dump(schema, f)
        except PermissionError:
            print("Another process is already writing to the binary schema file", file=sys.stderr)
        except OSError:
            raise
