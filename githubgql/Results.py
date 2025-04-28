from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, TypeAlias

from .PathKey import PathKey


class Results:

    @dataclass
    class CursorInfo:
        cursor: str
        count: int
        done: bool
        def to_dict(self):
            return asdict(self)

    ResultNode: TypeAlias = dict[str, Any] | list[dict[str, Any]]
    UpdateMapping: TypeAlias = dict[PathKey, list[CursorInfo]]

    def __init__(self, result: ResultNode):
        self._result_data = result
        self._updates: Results.UpdateMapping = {}
        self._has_more_pages = self._build_pagination_updates(result, PathKey())
        self._clean_up_pagination(result)
        self._collapse_edges_and_nodes(result)

    def to_dict(self):
        return self._result_data

    def has_more_pages(self) -> bool:
        return self._has_more_pages

    def get_updates(self) -> UpdateMapping:
        return self._updates

    def _build_pagination_updates(self, node: ResultNode, path: PathKey) -> bool:
        ignore_sub_path = isinstance(node, list)
        if isinstance(node, list):
            node = {k: v for k, v in enumerate(node)}

        for k, v in ((k, v) for k, v in node.items() if isinstance(v, dict) or isinstance(v, list)):
            sub_path = path.copy()
            ignore_sub_path or sub_path.append(k)
            self._build_pagination_updates(v, sub_path)

        if 'pageInfo' in node:
            cursor = next((v for k, v in node['pageInfo'].items() if k in ['endCursor', 'startCursor']))
            count = len(next((v for k, v in node.items() if k in ['edges', 'nodes'])))
            done = not next((v for k, v in node['pageInfo'].items() if k in ['hasNextPage', 'hasPreviousPage']))
            self._updates[path] = self._updates[path] if path in self._updates else []
            self._updates[path].append(Results.CursorInfo(cursor=cursor, count=count, done=done))
        else:
            return False

    def _clean_up_pagination(self, node: ResultNode) -> None:
        if isinstance(node, list):
            node = {k: v for k, v in enumerate(node)}

        for v in [v for k, v in node.items() if isinstance(v, dict) or isinstance(v, list)]:
            self._clean_up_pagination(v)

        if 'pageInfo' in node:
            del node['pageInfo']

    def _collapse_edges_and_nodes(self, node: ResultNode) -> None:
        if isinstance(node, list):
            node = {k: v for k, v in enumerate(node)}
        for k, v in node.items():
            if isinstance(v, dict) or isinstance(v, list):
                self._collapse_edges_and_nodes(v)
                if "edges" in v:
                    node[k] = [x["node"] for x in v["edges"]]
