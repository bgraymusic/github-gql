from __future__ import annotations

from gql import Client as GQLClient

from .Query import Query
from .Results import Results
from .PathKey import PathKey


class Paginator:
    def __init__(self, gql_client: GQLClient, query_str: str, vars: dict[str, str], page_size):
        """Construct a paginator for the query provided"""
        self.gql_client = gql_client
        self.query = Query(query_str, default_page_size=page_size)
        self.vars = vars
        self.complete = False

    def __iter__(self) -> Paginator:
        return self

    def __next__(self) -> None:
        if self.complete:
            raise StopIteration
        else:
            results = self.gql_client.execute(self.query.get_doc(), self.vars)
            self.complete = not self._update_pagination(Results(results))
            return results

    def _update_pagination(self, results: Results) -> bool:
        has_changes: bool = False
        for path, updates in results.get_updates().items():
            cursor, done = self._get_update_action(updates)
            if done:
                continue
            elif (self._all_descendants_done(results.get_updates(), path)):
                self.query.update_paged_node_cursor(path, cursor)
                self._clear_descendant_cursors(results.get_updates(), path)
                has_changes = True
        return has_changes

    def _get_update_action(self, updates: list[Results.CursorInfo]) -> tuple[str, bool]:
        done = all((x.done for x in updates))
        max_count_update = max(updates, key=lambda x: getattr(x, 'count'))
        return (max_count_update.cursor, done)

    def _all_descendants_done(self, updates: Results.UpdateMapping, path: PathKey):
        for descendant in self._get_descendant_paths(updates, path):
            if not all((x.done for x in updates[descendant])):
                return False
        return True

    def _get_descendant_paths(self, updates: Results.UpdateMapping, path: PathKey):
        candidates = [x for x in updates.keys() if len(x) > len(path)]
        return [x for x in candidates if x[:len(path)] == path]

    def _clear_descendant_cursors(self, updates: Results.UpdateMapping,  path: PathKey):
        for descendant in self._get_descendant_paths(updates, path):
            self.query.update_paged_node_cursor(descendant, None)
