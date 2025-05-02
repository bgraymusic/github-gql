"""
This module offers a simplified, opinionated way to access the GitHub
GraphQL API, particularly with respect to handling paging. Given the
following deeply nested, 66-line GraphQL query:

query deeplyNestedQuery {
    viewer {
        id
        login
        email
        repositories(first: 5, after: null) {
            edges {
                node {
                    id
                    name
                    description
                    assignableUsers(first: 5, after: null) {
                        edges {
                            node {
                                id
                                login
                                isViewer
                                contributionsCollection(first: 5, after: null) {
                                    edges {
                                        node {
                                            commitContributionsByRepository(first: 5, after: null, maxRepositories: 5) {
                                                edges {
                                                    node {
                                                        repository {
                                                            id
                                                            name
                                                            createdAt
                                                        }
                                                    }
                                                    cursor
                                                }
                                                pageInfo {
                                                    endCursor
                                                    hasNextPage
                                                }
                                                totalCount
                                            }
                                        }
                                        cursor
                                    }
                                    pageInfo {
                                        endCursor
                                        hasNextPage
                                    }
                                    totalCount
                                }
                            }
                            cursor
                        }
                        pageInfo {
                            endCursor
                            hasNextPage
                        }
                        totalCount
                    }
                }
                cursor
            }
            pageInfo {
                endCursor
                hasNextPage
            }
            totalCount
        }
    }
}

With paging handled by this module, you need only provide the information
that truly describes the data you intend to retrieve, in 18 lines:

query deeplyNestedQuery {
    viewer {
        email
        repositories {
            description
            assignableUsers {
                isViewer
                contributionsCollection {
                    commitContributionsByRepository(maxRepositories: 5) {
                        repository {
                            createdAt
                        }
                    }
                }
            }
        }
    }
}

Behind the scenes, this module instruments your query with:

1. Default minimum fields representing the ID of the paged selection, merged
   with any other explicitly listed fields.
2. Pagination boilerplate, handling paging attributes, cursors for advancing
   page to page, hasNextPage to know when done, and totalCount to track
   completeness.
3. Edges and node structures

It then sends the query to the server, analyzes the result and follows up with
pagination requests as necessary, updating the cursors. The result is stripped
of all the instrumentation, leaving you with a clean data representation.
"""

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

import shlex
import subprocess
import sys
from typing import TypeAlias, Callable

from gql import Client as GQLClient
from gql.transport.requests import RequestsHTTPTransport

from githubgql.Clock import Clock

from .Config import Config
from .Merger import Merger
from .Paginator import Paginator
from .Schema import Schema


class GitHubGQL:

    Merger = Merger()
    "A deep merger for handling the data structures in a result object."

    ResultPage: TypeAlias = dict[str, dict | list | str]
    "The type of one page of execution results."

    Iterator: TypeAlias = Paginator
    "An iterator used to loop through pages as they arrive."

    Callback: TypeAlias = Callable[[ResultPage], bool]
    "A function that can be passed into execute_callback for page-by-page processing."

    def __init__(
        self,
        pat: str = None,
        *,
        default_page_size: int = 100,
        auto_fit_quotas=True,
        inject_default_fields=True,
        cleanup_query=True,
    ):
        """Construct a GitHub GraphQL client.

        Args:
            pat: A Personal Access Token issued by GitHub that has all the
                privileges required for the queries the user intends to
                execute.
                Default: look up token via ``git config --get user.password``.
            default_page_size: How many items will be requested from
                collections per GraphQL call, unless overridden on a per-query
                basis. Many calls may be required to fulfill a complicated
                request.
                Default: 100 (GitHub maximum)
            auto_fit_quotas: Automatically adjust the default page size to be
                between 1-100, and proportionally auto-adjust all page sizes
                to keep the total query <= 500,000 nodes.
                Default: True
            inject_default_fields: Automatically inject fields into nodes that
                GitHubGQL has determined are commonly used to identify that
                type, such as ``id``, ``url``, or ``number``. Fields necessary
                to disambiguate and merge paged lists will be injected
                regardless of this argument.
                Default: True
            cleanup_query: Automatically detect and correct common mistakes in
                query construction. Override to fail loudly and do your own
                corrections.
                Default: True
        """
        with Clock("Constructing GitHubGQL client"):
            try:
                pat = (
                    pat
                    or subprocess.run(
                        shlex.split("git config --get user.password"), capture_output=True, check=True, text=True
                    ).stdout.strip()
                )
            except subprocess.CalledProcessError:
                print("GitHubGQL: Implicit Personal Access Token unavailable; provide one explicitly", file=sys.stderr)
                raise

            self.default_page_size = min(max(default_page_size, 1), 100) if auto_fit_quotas else default_page_size
            self.auto_fit_quotas = auto_fit_quotas
            self.inject_default_fields = inject_default_fields
            self.cleanup_query = cleanup_query
            gql_transport = RequestsHTTPTransport(
                url=Config.get().github_graphql_endpoint, headers={"Authorization": f"bearer {pat}"}
            )
            self.gql_client = GQLClient(schema=Schema.get(), transport=gql_transport)

    def execute_all(self, query: str, *, vars: dict[str, str] = None) -> ResultPage:
        """Execute the provided query to completion, with as many calls as necessary.

        Args:
            query: The query to execute. This can be standard GraphQL as
                described by online documentation, or a simplified, GitHub-only
                version with auto-pagination as described above.
            vars: The variables to substitute into the query.

        Returns:
            A dictionary containing the results of the query executed. If a
            simplified query was provided for auto-pagination, the results do
            not include pageInfo data.

        Example::

            results = client.execute_all(query, vars, 5)
        """
        paginator = Paginator(
            self.gql_client, query, vars, page_size=self.default_page_size, auto_fit_quotas=self.auto_fit_quotas
        )
        merged_results = {}
        for result in paginator:
            GitHubGQL.Merger.merge(merged_results, result)
        return merged_results

    def execute_iter(self, query: str, *, vars: dict[str, str] = None) -> Iterator:
        """Return an iterator for the provided query.

        Args:
            query: The query to execute. This can be standard GraphQL as
                described by online documentation, or a simplified, GitHub-only
                version with auto-pagination as described above.
            vars: The variables to substitute into the query.

        Returns:
            An iterator allowing the client to control their own merging
            and/or other operations

        Example::

            merged_results = {}
            for result in client.execute_iter():
                Client.Merger.merge(merged_results, result)
                if next((x for x in result['viewer']['repositories'] if x['name'] == 'bgm-nerdrock']), False):
                    # Got what we need
                    break
        """
        return Paginator(self.gql_client, query, vars, self.default_page_size).__iter__()

    def execute_callback(self, callback: GitHubGQL.Callback, query: str, *, vars: dict[str, str] = None) -> None:
        """Execute the query page by page, calling `callback` for each page.

        Args:
            callback: A function to call for each page. The page results are
                sent, and the function may operate on each as required. The
                iterator stops when all data is consumed, the callback returns
                `False`, or an exception is raised.
            query: The query to execute. This can be standard GraphQL as
                described by online documentation, or a simplified, GitHub-only
                version with auto-pagination as described above.
            vars: The variables to substitute into the query.

        Returns:
            Nothing

        Example::

            merged_results = {}

            def callback(result):
                Client.Merger.merge(merged_results, result)
                if next((x for x in result['viewer']['repositories'] if x['name'] == 'bgm-nerdrock']), False):
                    # Got what we need
                    return False
                return True

            client.execute_callback(callback)
        """
        paginator = Paginator(self.gql_client, query, vars, self.default_page_size)
        try:
            for result in paginator:
                if not callback(result):
                    break
        except Exception as e:
            print(e, file=sys.stderr)
