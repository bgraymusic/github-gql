Usage
=====

.. _installation:

Installation
------------

To use GitHubGQL, first install it using pip:

.. code-block:: console

   (.venv) $ pip install github-graphql-paginator

Querying from the GitHub GraphQL API
------------------------------------

To retrieve a structured dictionary of all labels in all repositories under
the current viewer (as defined by the Personal Access Token used), with all
nodes auto-populated with common identification info, plus the name of each
label, use the following query string:

.. code-block:: python

    query = """
    query getViewerData {
        viewer {
            repositories {
                labels {
                    name
                }
            }
        }
    }
    """

The above string is equivalent to the following string provided directly to
the standard GitHub GraphQL API:

.. code-block:: python

    query = """
    query getViewerData {
        viewer {
            email
            id
            login
            name
            url
            websiteUrl
            repositories(first: 100, after: null) {
                edges {
                    node {
                        createdAt
                        homepageUrl
                        id
                        nameWithOwner
                        url
                        labels(first: 100, after: null) {
                            edges {
                                node {
                                    id
                                    name
                                }
                            }
                            pageInfo {
                            endCursor
                            hasNextPage
                            }
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }
    """

…except that even the above may require receiving results with paging info and
issuing followup requests to complete all data. In addition, it becomes tricky
to manage multiple layers of cursors covering nested pages, making sure lower
level pages are complete before advancing higher level pages.

With GitHubGQL, and using the former query string, you need only execute:

.. code-block:: python

    client = GitHubGQL()
    data = client.execute_all(query)

…and receive back all data among all pages merged together, absent any paging
instrumentation cluttering up the results. It's as if the data were returned
from one request to the API server. You also need not worry about the `edges`
and `node` levels if you don't want to; the response mirrors the same format
and leveling you specify in your request.
