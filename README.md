# GitHubGQL
GitHubGQL provides a simplified, opinionated way to access the [GitHub GraphQL API](https://docs.github.com/en/graphql), particularly with respect to handling paging.

## Overview
Given a complex, nested query with multiple levels of collections, a standard GQL query to the GitHub API must contain and request instrumentation to manage paging information. This information includes cursors, the total number of elements to expect, and notification of whether or not the request has a next page. In order to complete a request, the client must request additional pages in a bottom-up manner throughout the query graph, only incrementing a cursor when all cursors below it are completed, then reset the lower cursors to their beginning.

Additionally, the GitHub GQL organizes collections into edges and nodes, facilitating true graph navigation. For common use, these edges and nodes can be implicit, allowing the client to speak only in terms of collections of objects. Thus, the following query:

```
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
```
…could potentially be reduced to:
```
query deeplyNestedQuery($maxContributionsRepos: Int) {
    viewer {
        email
        repositories {
            description
            assignableUsers {
                isViewer
                contributionsCollection {
                    commitContributionsByRepository(maxRepositories: $maxContributionsRepos) {
                        repository {
                            createdAt
                        }
                    }
                }
            }
        }
    }
}
```
In addition to the paging information, the previous example illustrates a separate feature of GitHubGQL. Each collection will automatically fetch a small subset of fields inherent to its identification. Thus where the first query requests fields like `id`, `name`, or `login`, the second can omit those fields and only list non-ID fields like `isViewer` and `createdAt`.

## Install
```
pip install GitHubGQL
```

## Usage
### Get All Data at Once
```
from githubgql.Client import GitHubGQL

query = '''
query deeplyNestedQuery($maxContributionsRepos: Int) {
    viewer {
        email
        repositories {
            description
            assignableUsers {
                isViewer
                contributionsCollection {
                    commitContributionsByRepository(maxRepositories: $maxContributionsRepos) {
                        repository {
                            createdAt
                        }
                    }
                }
            }
        }
    }
}
'''
vars = {'maxContributionsRepos': 5}

client = GitHubGQL()  # Scrapes Personal Access Token from `git config --get
                      # user.password` and uses default_page_size of 100
results = client.execute_all(query, vars)
```

### Paged Data via Iterator
```
from githubgql.Client import GitHubGQL

# ...same query and vars as above...

pat = get_my_personal_access_token()  # exercise for the reader
client = GitHubGQL(pat, default_page_size=47)

merged_results = {}
for result in client.execute_iter():
    GitHubGQL.Merger.merge(merged_results, result)
    if next((x for x in result['viewer']['repositories'] if x['name'] == 'bgm-nerdrock'), False):
        # Got what we need; use it
        break
```

### Paged Data via Callback
```
from githubgql.Client import GitHubGQL

# ...same query and vars as above...

pat = get_my_personal_access_token()  # exercise for the reader
client = GitHubGQL(pat)  # default_page_size of 100

merged_results = {}

def callback(result):
    GitHubGQL.Merger.merge(merged_results, result)
    if next((x for x in result['viewer']['repositories'] if x['name'] == 'bgm-nerdrock'), False):
        # Got what we need; use it
        return False
    return True

client.execute_callback(callback)
```

## Documentation
In progress, stay tuned for docs site

## Development
### Contributing
Long-term discussion and bug reports are maintained via GitHub Issues. Code review is done via GitHub Pull Requests.

For more information read CONTRIBUTING.md.

### Maintainership
Until this project gets any traction at all, no need for maintainers