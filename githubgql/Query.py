from dataclasses import asdict, dataclass
from enum import Enum
import locale
import re
import sys
from typing import Any

from graphql import (
    parse,
    ArgumentNode,
    DocumentNode,
    FieldNode,
    GraphQLField,
    GraphQLFieldMap,
    GraphQLInterfaceType,
    GraphQLObjectType,
    GraphQLScalarType,
    IntValueNode,
    NameNode,
    NullValueNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
    StringValueNode,
)

from githubgql.Clock import Clock

from .Config import Config
from .PathKey import PathKey
from .Schema import Schema


class Query:
    """The magic that allows a simple query to represent a full, complex GQL query

    Options to simplify your query definition:

    1. Remove the pagination arguments, unless you wish to control the page size and/or direction of paging (use `first/last: n` for size, `after/before: null` for direction, or both).
    2. Remove `edges/node` and `nodes` levels, unless you need to specify info at those levels. The Query class will inject them for you.
    3. Omit common `id` fields and let Query inject them for you.
    4. Cleanup common authoring errors, such as empty bracket scopes.

    Useful case for this class by itself:

    Check the traditional query that your simplified query would be equivalent
    to::

        from githubgql.Query import Query
        from graphql import print_ast
        query = \"\"\"
        query myQuerySpec {
            # your query spec here
        }
        \"\"\"
        ast = Query(query).get_doc()
        print_ast(ast)
    """

    EMPTY_BRACKETS_PATTERN = re.compile(r"{[\s]*}")
    HARD_NODE_LIMIT = 500000  # GitHub maximum potential nodes per request

    class Direction(Enum):
        FORWARD = 1
        BACKWARD = 2

    @dataclass
    class PagedNodeInfo:
        cursor_arg: ArgumentNode
        page_size_arg: ArgumentNode

        def to_dict(self):
            return asdict(self)

    def __init__(
        self,
        query: str,
        *,
        default_page_size: int = 100,
        auto_fit_quotas=True,
        inject_default_fields=True,
        cleanup_query=True,
    ):
        self.default_page_size = default_page_size
        self.inject_default_fields = inject_default_fields
        self.paged_nodes: dict[PathKey, Query.PagedNodeInfo] = {}
        self.interfaces_lookup = Config.get().interfaces
        locale.setlocale(locale.LC_ALL, "")

        with open(f"{Config.get().dir}/{Config.get().github_graphql_schema}") as f:
            if cleanup_query:
                query = self._cleanup_query(query)
            self.doc = self._build_ast(query)
            self._validate_quotas(auto_fit_quotas)

    def get_doc(self) -> DocumentNode:
        return self.doc

    def get_paged_node(self, path: PathKey) -> PagedNodeInfo:
        return self.paged_nodes[path]

    def get_paged_nodes(self) -> dict[PathKey, PagedNodeInfo]:
        return self.paged_nodes

    def update_paged_node_cursor(self, path: PathKey, cursor: str):
        self.paged_nodes[path].cursor_arg.value = StringValueNode(value=cursor) if cursor else NullValueNode()

    def _cleanup_query(self, query: str) -> str:
        with Clock("Cleaning up query"):
            # Error 1) Empty brackets instead of nothing when a leaf node will be given default fields
            query = re.sub(Query.EMPTY_BRACKETS_PATTERN, "", query)
        return query

    def _validate_quotas(self, adjust: bool):
        with Clock("Validating quotas"):
            query_size = self._get_query_size()
            if query_size > Query.HARD_NODE_LIMIT:
                print(
                    f"Aggregate query size over quota ({query_size:n} > {Query.HARD_NODE_LIMIT:n}). {'Adjusting...' if adjust else ''}",
                    file=sys.stderr,
                )
                if adjust:
                    while query_size > Query.HARD_NODE_LIMIT:
                        self._nudge_down_page_sizes()
                        query_size = self._get_query_size()
                    page_sizes = {}
                    for path, info in self.paged_nodes.items():
                        page_sizes["/".join(path)] = info.page_size_arg.value.value
                    print(f"New page sizes by path ({query_size} total):", file=sys.stderr)
                    for k, v in page_sizes.items():
                        print(f"\t{k}: {v}", file=sys.stderr)
                else:
                    exit(-1)

    def _get_query_size(self):
        total_size = 0
        for path, info in self.paged_nodes.items():
            total_size += self._get_node_page_size(info, path)
        return total_size

    def _get_node_page_size(self, info: PagedNodeInfo, path: PathKey) -> int:
        if not info:
            return 1
        parent_node_info, parent_key = self._find_parent(path)
        return info.page_size_arg.value.value * self._get_node_page_size(parent_node_info, parent_key)

    def _find_parent(self, path: PathKey) -> tuple[PagedNodeInfo, PathKey]:
        candidates = [x for x in self.paged_nodes.keys() if len(x) < len(path)]
        ancestors = [x for x in candidates if path[: len(x)] == x]
        parent = next((x for x in ancestors if len(x) == max([len(x) for x in ancestors])), None)
        return (self.paged_nodes[parent], parent) if parent in self.paged_nodes else (None, None)

    def _nudge_down_page_sizes(self):
        for path, info in self.paged_nodes.items():
            info.page_size_arg.value.value = max(int(info.page_size_arg.value.value * 0.95), 1)

    def _build_ast(self, query: str) -> DocumentNode:
        with Clock("Building AST"):
            doc = parse(query, no_location=True)
            path = PathKey()
            for definition in doc.definitions:
                if isinstance(definition, OperationDefinitionNode) and definition.operation == OperationType.QUERY:
                    self._build_query(definition, Schema.get().query_type, path.copy())
        return doc

    def _build_query(self, query_node: OperationDefinitionNode, schema_node: GraphQLObjectType, path: PathKey):
        for node in query_node.selection_set.selections:
            if isinstance(node, FieldNode) and node.selection_set:
                sub_path = path.copy()
                sub_path.append(node.name.value)
                self._build_node(node, schema_node.fields[node.name.value], sub_path)

    def _build_node(self, query_node: FieldNode, schema_node: GraphQLField, path: PathKey) -> None:
        if self.inject_default_fields:
            self._fill_out_default_sub_fields(query_node, schema_node)

        if self._is_paged_node(schema_node):
            dir = self._fill_out_pagination_args(query_node)
            page_size_arg = next((x for x in query_node.arguments if x.name.value in ["first", "last"]))
            cursor_arg = next((x for x in query_node.arguments if x.name.value in ["after", "before"]))
            self.paged_nodes[path] = Query.PagedNodeInfo(cursor_arg=cursor_arg, page_size_arg=page_size_arg)
            if self._edges_or_nodes_not_provided(query_node):
                self._sub_in_edges_and_node(query_node)
            self._fill_out_page_info(query_node, dir)

        if hasattr(query_node, "selection_set") and query_node.selection_set:
            fields = self._get_schema_node_fields(schema_node)
            for query_sub_node in query_node.selection_set.selections:
                if isinstance(query_sub_node, FieldNode):
                    sub_path = path.copy()
                    sub_path.append(query_sub_node.name.value.strip())
                    self._build_node(query_sub_node, fields[query_sub_node.name.value], sub_path)

    def _fill_out_default_sub_fields(self, query_node: FieldNode, schema_node: GraphQLField) -> None:
        interfaces = self._get_schema_node_interfaces(schema_node)
        if not interfaces:
            return

        current_fields = [x.name.value for x in query_node.selection_set.selections] if query_node.selection_set else []
        schema_node_type = self._get_schema_node_type(schema_node)
        merge_field = next((x for x in Config.get().merge_match_keys if x in schema_node_type.fields), False)
        default_fields = [merge_field] if merge_field else []
        for interface in [x.name for x in interfaces]:
            default_fields += self.interfaces_lookup[interface] if interface in self.interfaces_lookup else []
        to_be_added = tuple(
            FieldNode(name=NameNode(value=x), directives=[], arguments=[])
            for x in sorted(set(default_fields))
            if x not in current_fields
        )

        if len(to_be_added) and not query_node.selection_set:
            query_node.selection_set = SelectionSetNode(selections=())

        query_node.selection_set.selections = to_be_added + query_node.selection_set.selections

    def _is_paged_node(self, schema_node: GraphQLField) -> bool:
        if self._is_scalar_type(schema_node):
            return False

        args = [x for x in schema_node.args if x in ["first", "last", "after", "before"]]
        fields = [
            x for x in self._get_schema_node_fields(schema_node) if x in ["edges", "nodes", "pageInfo", "totalCount"]
        ]
        evidence_count = len(args) + len(fields)
        if evidence_count == 8:
            return True
        elif evidence_count == 0:
            return False
        else:
            raise ValueError(
                f"Some but not all evidence of paged node present:\n" f"\tArgs: {args}\n" f"\tFields: {fields}"
            )

    def _is_scalar_type(self, schema_node: GraphQLField) -> bool:
        return self._get_schema_node_type(schema_node).__class__ == GraphQLScalarType

    def _get_schema_node_fields(self, schema_node: GraphQLField) -> GraphQLFieldMap:
        t = self._get_schema_node_type(schema_node)
        return t.fields

    def _get_schema_node_interfaces(self, schema_node: GraphQLField) -> tuple[GraphQLInterfaceType]:
        t = self._get_schema_node_type(schema_node)
        return t.interfaces if hasattr(t, "interfaces") else None

    def _get_schema_node_type(self, schema_node: GraphQLField) -> Any:
        t = schema_node.type
        while hasattr(t, "of_type"):
            t = t.of_type
        return t

    def _fill_out_pagination_args(self, query_node: FieldNode) -> Direction:
        """Make sure the pagination arguments are complete and valid

        Possible states…
        Provided nothing -> first: <default>, after: null
        Provided first or last -> use number as page size and infer direction, after/before: null
        Provided after or before -> infer direction, use default page size
        Provided conflicting direction -> use forward, delete backward
        Provided complete, correct info -> use as-is
        """
        new_arguments = ()
        deleted_arguments = ()
        direction = Query.Direction.FORWARD
        first = next((x for x in query_node.arguments if x.name.value == "first"), None)
        last = next((x for x in query_node.arguments if x.name.value == "last"), None)
        after = next((x for x in query_node.arguments if x.name.value == "after"), None)
        before = next((x for x in query_node.arguments if x.name.value == "before"), None)
        if first:
            deleted_arguments += last or ()
            deleted_arguments += before or ()
            if not after:
                new_arguments += (ArgumentNode(name=NameNode(value="after"), value=NullValueNode()),)
            direction = Query.Direction.FORWARD
        elif last:
            deleted_arguments += after or ()
            if not after:
                new_arguments += (ArgumentNode(name=NameNode(value="before"), value=NullValueNode()),)
            direction = Query.Direction.BACKWARD
        elif after:
            deleted_arguments = deleted_arguments + (before or ())
            new_arguments += (
                ArgumentNode(name=NameNode(value="first"), value=IntValueNode(value=self.default_page_size)),
            )
            direction = Query.Direction.FORWARD
        elif before:
            new_arguments += (
                ArgumentNode(name=NameNode(value="last"), value=IntValueNode(value=self.default_page_size)),
            )
            direction = Query.Direction.BACKWARD
        else:
            new_arguments += (
                ArgumentNode(name=NameNode(value="first"), value=IntValueNode(value=self.default_page_size)),
                ArgumentNode(name=NameNode(value="after"), value=NullValueNode()),
            )
            direction = Query.Direction.FORWARD

        query_node.arguments = tuple(x for x in query_node.arguments if x not in deleted_arguments) + new_arguments
        return direction

    def _fill_out_page_info(self, query_node: FieldNode, dir: Direction) -> None:
        if not query_node.selection_set:
            query_node.selection_set = SelectionSetNode(selections=())
        pi = next((x for x in query_node.selection_set.selections if x.name.value == "pageInfo"), None)
        if not pi:
            pi = FieldNode(
                name=NameNode(value="pageInfo"),
                directives=[],
                arguments=[],
                selection_set=SelectionSetNode(selections=()),
            )
            query_node.selection_set.selections += (pi,)
        new_selections = ()
        if dir == Query.Direction.FORWARD:
            pi.selection_set.selections = tuple(
                x for x in pi.selection_set.selections if x.name.value not in ["startCursor", "hasPreviousPage"]
            )
            for field in ["endCursor", "hasNextPage"]:
                if not next((x for x in pi.selection_set.selections if x.name.value == field), False):
                    new_selections += (FieldNode(name=NameNode(value=field), directives=[], arguments=[]),)
        elif dir == Query.Direction.BACKWARD:
            pi.selection_set.selections = tuple(
                x for x in pi.selection_set.selections if x.name.value not in ["endCursor", "hasNextPage"]
            )
            for field in ["startCursor", "hasPreviousPage"]:
                if not next((x for x in pi.selection_set.selections if x.name.value == field), False):
                    new_selections += (FieldNode(name=NameNode(value=field), directives=[], arguments=[]),)
        pi.selection_set.selections += new_selections

    def _edges_or_nodes_not_provided(self, query_node: FieldNode) -> bool:
        return not query_node.selection_set or not next(
            (
                x
                for x in query_node.selection_set.selections
                if isinstance(x, FieldNode) and (x.name.value == "edges" or x.name.value == "nodes")
            ),
            False,
        )

    def _sub_in_edges_and_node(self, query_node: FieldNode) -> None:
        node = FieldNode(
            name=NameNode(value="node"), directives=[], arguments=[], selection_set=query_node.selection_set
        )
        edges = FieldNode(
            name=NameNode(value="edges"),
            directives=[],
            arguments=[],
            selection_set=SelectionSetNode(selections=(node,)),
        )
        query_node.selection_set = SelectionSetNode(selections=(edges,))
