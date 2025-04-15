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

from deepmerge.merger import Merger as DeepmergeMerger
from graphql import (
    ArgumentNode,
    IntValueNode,
    NameNode,
    NullValueNode,
    OperationType,
    SelectionSetNode,
    StringValueNode,
    parse,
    FieldNode,
    OperationDefinitionNode,
)
from gql import Client as GQLClient

from githubgql.Config import Config
from githubgql.Merger import ghp_merger
from githubgql.Iterator import QueryIterator


class QueryPaginator:
    """Setup auto-pagination of complex, nested queries"""

    Merger: DeepmergeMerger = ghp_merger

    #######################################################
    # PUBLIC INTERFACE

    def __init__(self, gql_client: GQLClient, query_str: str, vars: dict[str, str], page_size):
        """Construct a paginator for the query provided"""
        self.gql_client = gql_client
        self.vars = vars
        self.page_size = page_size
        self._complete = False

        self.doc = parse(query_str, no_location=True)
        self._prepare_document()
        self.gql_client.validate(self.doc)

    def __iter__(self):
        """Return an iterator that can deliver result pages"""
        return QueryIterator(self.gql_client, self.doc, self.vars, self.page_size)

    #######################################################
    # PREPARE QUERY DOC FOR PAGINATION

    def _prepare_document(self):
        selections: dict[FieldNode, dict[int, str]] = {}
        for definition in self.doc.definitions:
            if isinstance(definition, OperationDefinitionNode) and definition.operation == OperationType.QUERY:
                QueryPaginator.Merger.merge(selections, self._prepare_definition(definition))
        self._init_document_pagination(selections)

    def _prepare_definition(self, definition: OperationDefinitionNode) -> dict[FieldNode, dict[int, str]]:
        selections: dict[FieldNode, dict[int, str]] = {}
        if not definition.selection_set:
            return selections

        selection: FieldNode = None
        for selection in definition.selection_set.selections:
            if isinstance(selection, FieldNode):
                QueryPaginator.Merger.merge(selections, self._prepare_selection(selection))
        return selections

    def _prepare_selection(self, selection: FieldNode) -> dict[FieldNode, dict[int, str]]:
        selections: dict[FieldNode, dict[int, str]] = {}
        if self._get_page_spec(selection):
            self._expand_paged_selection(selection)
            selections[selection] = {"first": self.page_size, "after": None}
        else:
            self._expand_unpaged_selection(selection)

        try:
            sub_selection: FieldNode = None
            for sub_selection in selection.selection_set.selections:
                QueryPaginator.Merger.merge(selections, self._prepare_selection(sub_selection))
        except AttributeError:
            pass  # Node type with no selection_set

        return selections

    def _get_page_spec(self, selection: FieldNode):
        return next((x for x in Config.get().paged_selections if x["key"] == selection.name.value), None)

    def _expand_paged_selection(self, selection: FieldNode):
        config_data = next((x for x in Config.get().paged_selections if x["key"] == selection.name.value))
        if not selection.selection_set:
            selection.selection_set = SelectionSetNode(selections=())
        for id_field in config_data["id_fields"]:
            if not next((x for x in selection.selection_set.selections if x.name.value == id_field), False):
                selection.selection_set.selections = selection.selection_set.selections + (
                    FieldNode(name=NameNode(value=id_field), directives=[], arguments=[]),
                )
        if not next(
            (
                True
                for x in selection.selection_set.selections
                if isinstance(x, FieldNode) and x.name.value in ["nodes", "edges"]
            ),
            False,
        ):
            node = FieldNode(
                name=NameNode(value="node"), directives=[], arguments=[], selection_set=selection.selection_set
            )
            cursor = FieldNode(name=NameNode(value="cursor"), directives=[], arguments=[])
            edges = FieldNode(
                name=NameNode(value="edges"),
                directives=[],
                arguments=[],
                selection_set=SelectionSetNode(selections=(node, cursor)),
            )
            selection.selection_set = SelectionSetNode(selections=(edges,))

    def _expand_unpaged_selection(self, selection: FieldNode):
        config_data = next(
            (x for x in Config.get().unpaged_selections if x["key"] == selection.name.value), False
        )
        if config_data:
            if not selection.selection_set:
                selection.selection_set = SelectionSetNode(selections=())
            for id_field in config_data["id_fields"]:
                if not next((x for x in selection.selection_set.selections if x.name.value == id_field), False):
                    selection.selection_set.selections = selection.selection_set.selections + (
                        FieldNode(name=NameNode(value=id_field), directives=[], arguments=[]),
                    )

    def _init_document_pagination(self, selections: dict[FieldNode, dict[int, str]]) -> None:
        for node, args in selections.items():
            cursor_value = StringValueNode(value=args["after"]) if args["after"] else NullValueNode()
            node.arguments = node.arguments + (
                ArgumentNode(name=NameNode(value="first"), value=IntValueNode(value=args["first"])),
                ArgumentNode(name=NameNode(value="after"), value=cursor_value),
            )
            node.selection_set.selections = node.selection_set.selections + self._get_pagination_fields()

    def _get_pagination_fields(self) -> tuple[FieldNode]:
        selections = [
            FieldNode(name=NameNode(value=x), directives=[], arguments=[]) for x in ["endCursor", "hasNextPage"]
        ]
        return (
            FieldNode(
                name=NameNode(value="pageInfo"),
                directives=[],
                arguments=[],
                selection_set=SelectionSetNode(selections=selections),
            ),
            FieldNode(name=NameNode(value="totalCount"), directives=[], arguments=[]),
        )
