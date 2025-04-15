############################ Copyrights and license ###########################
#                                                                             #
# Copyright 2025 Brian Gray <bgraymusic@gmail.com>                            #
#                                                                             #
# This file is part of GitHubGQL.                                             #
# https://github.com/bgraymusic/github-gql                                    #
#                                                                             #
# GitHubGQL is free software: you can redistribute it and/or modify it under  #
# the terms of the GNU Lesser General Public License as published by the Free #
# Software Foundation, either version 3 of the License, or (at your option)   #
# any later version.                                                          #
#                                                                             #
# GitHubGQL is distributed in the hope that it will be useful, but WITHOUT    #
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or       #
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License #
# for more details.                                                           #
#                                                                             #
# You should have received a copy of the GNU Lesser General Public License    #
# along with PyGithub. If not, see <http://www.gnu.org/licenses/>.            #
#                                                                             #
###############################################################################

from __future__ import annotations

from typing import Any, TypeAlias

from deepmerge.merger import Merger as DeepmergeMerger
from graphql import DocumentNode, NullValueNode, OperationType, StringValueNode, FieldNode, OperationDefinitionNode
from gql import Client as GQLClient

from githubgql.Config import Config
from githubgql.Merger import ghp_merger


class QueryIterator:
    """Handle iteration and manage paging sequences"""

    #######################################################
    # PUBLIC INTERFACE

    ResultsNode: TypeAlias = dict[str, Any] | list[dict]
    ResultsPath: TypeAlias = list[str | int]
    PaginationPath: TypeAlias = list[str]
    PaginationUpdate: TypeAlias = tuple[PaginationPath, dict]
    PaginationUpdateMapping: TypeAlias = dict[str, PaginationUpdate]
    Merger: DeepmergeMerger = ghp_merger

    def __init__(self, gql_client: GQLClient, doc: DocumentNode, vars: dict[str, str], page_size: int):
        self.gql_client = gql_client
        self.doc = doc
        self.vars = vars
        self.page_size = page_size
        self.paged_selections = Config.get().paged_selections
        self.complete = False

    def __next__(self) -> None:
        if self.complete:
            raise StopIteration
        else:
            result = self.gql_client.execute(self.doc, self.vars)
            self.complete = not self._update_pagination(result)
            return result

    #######################################################
    # UPDATE PAGINATION INSTRUMENTATION BASED ON QUERY RESULTS

    def _update_pagination(self, result_doc: dict[str, Any]) -> bool:
        updates: QueryIterator.PaginationUpdateMapping = {}
        has_more_pages = self._build_pagination_updates(result_doc, [], updates)
        self._apply_pagination_updates(updates)
        self._clean_up_result(result_doc)
        self._collapse_result(result_doc)
        return has_more_pages

    def _build_pagination_updates(
        self, node: ResultsNode, path: PaginationPath, updates: PaginationUpdateMapping
    ) -> bool:
        node_update: QueryIterator.PaginationUpdate = None
        ignore_sub_path = isinstance(node, list)
        if isinstance(node, list):
            node = {k: v for k, v in enumerate(node)}
        children_have_more_pages: bool = False
        for k, v in node.items():
            if isinstance(v, dict) or isinstance(v, list):
                sub_path = path.copy()
                if not ignore_sub_path:
                    sub_path.append(k)
                if k == "pageInfo":
                    node_update = (path, v)
                    if "complete" not in node_update[1]:
                        node_update[1]["complete"] = False
                else:
                    children_have_more_pages = (
                        self._build_pagination_updates(v, sub_path, updates) or children_have_more_pages
                    )

        if children_have_more_pages:
            return True
        elif node_update:
            if node_update[1]["complete"]:
                return False
            elif len(node["edges"]):
                node_update[1]["cursors"] = [(len(node["edges"]), node_update[1]["endCursor"])]
                idx = "/".join(node_update[0])
                updates[idx] = QueryIterator.Merger.merge(updates[idx], node_update) if idx in updates else node_update
                node_update[1]["complete"] = not node_update[1]["hasNextPage"]
                if not node_update[1]["complete"]:
                    self._reset_child_cursors(path, updates)
                return not node_update[1]["complete"]
        else:
            return False

    def _reset_child_cursors(self, path: PaginationPath, updates: PaginationUpdateMapping):
        node = self._path_to_node(path)
        if isinstance(node, FieldNode) and node.selection_set:
            for sub_node in node.selection_set.selections:
                if isinstance(sub_node, FieldNode):
                    sub_path = path.copy()
                    sub_path.append(sub_node.name.value)
                    if self._get_page_spec(sub_node):
                        updates["/".join(sub_path)] = (
                            sub_path,
                            {"cursors": [(0, None)], "hasNextPage": True, "complete": False},
                        )
                    self._reset_child_cursors(sub_path, updates)

    def _get_page_spec(self, selection: FieldNode):
        return next((x for x in self.paged_selections if x["key"] == selection.name.value), None)

    def _apply_pagination_updates(self, updates: PaginationUpdateMapping) -> bool:
        for k, v in updates.items():
            working_node: FieldNode = self._path_to_node(v[0])
            arg = next((x for x in working_node.arguments if x.name.value == "after"))
            max_val = max([x[0] for x in v[1]["cursors"]])
            cursor = next((x[1] for x in v[1]["cursors"] if x[0] == max_val))
            arg.value = StringValueNode(value=cursor) if cursor else NullValueNode()

    def _path_to_node(self, path: PaginationPath) -> FieldNode:
        node: OperationDefinitionNode = next(
            (
                x
                for x in self.doc.definitions
                if isinstance(x, OperationDefinitionNode) and x.operation == OperationType.QUERY
            ),
            None,
        )
        if not node:
            return None

        for path_step in path:
            node = next(
                (x for x in node.selection_set.selections if isinstance(x, FieldNode) and x.name.value == path_step)
            )

        return node

    def _clean_up_result(self, node: ResultsNode):
        if isinstance(node, list):
            node = {k: v for k, v in enumerate(node)}
        keys_to_delete = []
        for k, v in node.items():
            if isinstance(v, dict) or isinstance(v, list):
                if k == "pageInfo":
                    keys_to_delete.append(k)
                else:
                    self._clean_up_result(v)
            elif k in ["cursor", "totalCount"]:
                keys_to_delete.append(k)

        for k in keys_to_delete:
            del node[k]

    def _collapse_result(self, node: ResultsNode):
        if isinstance(node, list):
            node = {k: v for k, v in enumerate(node)}
        for k, v in node.items():
            if isinstance(v, dict) or isinstance(v, list):
                self._collapse_result(v)
                if "edges" in v:
                    node[k] = [x["node"] for x in v["edges"]]
