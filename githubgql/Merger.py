"""A merger designed to work properly with results from the GitHub GraphQL API"""

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

from typing import Any, TypeVar

from deepmerge.extended_set import ExtendedSet
from deepmerge.merger import Merger
from deepmerge.strategy.core import STRATEGY_END


T = TypeVar("T")


def strategy_merge_paged_selections(config: Merger, path: list, base: list, nxt: list) -> list:
    """
    Merge lists of dicts, matched by 'id' property instead of list position
    """
    if nxt:
        non_nodes: list = []
        for k, v in enumerate(nxt):
            if _is_edge(v):
                base_edge = next((x for x in base if _is_edge(x) and x["node"]["id"] == v["node"]["id"]), False)
                if base_edge:
                    base_edge = config.value_strategy(path + [k], base_edge, v)
                else:
                    non_nodes.append(v)
            elif _has_id(v):
                base_edge = next((x for x in base if _has_id(x) and x["id"] == v["id"]), False)
                if base_edge:
                    base_edge = config.value_strategy(path + [k], base_edge, v)
                else:
                    non_nodes.append(v)
            else:
                non_nodes.append(v)

        base_as_set = ExtendedSet(base)
        base = base + [x for x in non_nodes if x not in base_as_set]

    return base


def _is_edge(node: dict):
    """Return whether or not this node is an `edges` node."""
    return isinstance(node, dict) and "node" in node and "id" in node["node"]


def _has_id(node: dict):
    """Return whether or not this node has an `id` key."""
    return isinstance(node, dict) and "id" in node


def strategy_override_if_not_empty(config: Merger, path: list, base: T, nxt: Any) -> T:
    """Override the base object only if the new object is not empty or null."""
    return nxt if nxt or isinstance(nxt, bool) or isinstance(nxt, int) else base


GITHUB_GRAPHQL_TYPE_SPECIFIC_MERGE_STRATEGIES: list[tuple[type, str]] = [
    (list, strategy_merge_paged_selections),
    (list, "append_unique"),
    (dict, "merge"),
    (set, "union"),
]

ghp_merger: Merger = Merger(
    GITHUB_GRAPHQL_TYPE_SPECIFIC_MERGE_STRATEGIES,
    fallback_strategies=[strategy_override_if_not_empty],
    type_conflict_strategies=["override_if_not_empty"],
)
