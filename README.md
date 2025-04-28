# GitHubGQL
GitHubGQL provides a simplified, opinionated way to access the [GitHub GraphQL API](https://docs.github.com/en/graphql), particularly with respect to handling paging.

## GitHubGQL's primary advantages over straight GraqphQL queries:

### Auto-Paging
Specify page size and/or direction if you choose, or just leave it up to the defaults. GitHubGQL will handle your query by merging together multiple requests, incrementing arbitrarily nested paging cursors automatically.

### Selectable Execution Mode
Choose among 3 execution modes:

__All__
: Execute your query all at once and get the results delivered pre-merged.

__Iterator__
: Retrieve an interator and get results one page at a time. Use the GitHubGQL Merger to merge them, or operate on them individually.

__Callback__
: Register a callback to receive page results as they are ready.

### Auto-Adjust of Page Sizes to Fit GitHub Quotas (optional)

__Each Page__
: Every paged selection must request pages between 1-100 items, inclusive. Values falling outside this range will be adjusted to the nearest acceptable value.

__Total Potential Size__
: Assuming all pages get filled by the server to their maximum allocated size, the total number of nodes returned from the query must not exceed 500,000. GitHubGQL can (and by default does) automatically reduce page sizes to make your query fit this quota.

### Default Fields (optional)

GraphQL requires the client to specify each and every field it wishes to be returned in the response. GitHubGQL auto-requests basic, common fields essential to the identification of each datum, driven by its Interfaces. If you also specify the same field explicitly, no problem! GitHubGQL handles it.

### Query Cleanup (optional)

Auto-cleanup for common malformation patterns in the input query. At this time the only implementation is deletion of empty bracketed scopes.

### Results Cleanup

Auto-cleanup and simplification of the results you receive back, eliminating now-unnecessary paging data and nesting of collections within edges and nodes.

## Example
Given a complex, nested query with multiple levels of collections, a standard GQL query to the GitHub API must contain and request instrumentation to manage paging information. This information includes cursors, the total number of elements to expect, and notification of whether or not the request has a next page. In order to complete a request, the client must request additional pages in a bottom-up manner throughout the query graph, only incrementing a cursor when all cursors below it are completed, then reset the lower cursors to their beginning.

Additionally, the GitHub GQL organizes collections into edges and nodes, facilitating true graph navigation. For common use, these edges and nodes can be implicit, allowing the client to speak only in terms of collections of objects. Thus, the following query:

```
query deeplyNestedQuery {
  viewer {
    email
    id
    login
    name
    url
    websiteUrl
    repositories(first: 72, after: null) {
      edges {
        node {
          createdAt
          homepageUrl
          id
          nameWithOwner
          url
          assignableUsers(first: 72, after: null) {
            edges {
              node {
                email
                id
                login
                name
                url
                websiteUrl
                contributionsCollection {
                  commitContributionsByRepository(maxRepositories: 5) {
                    contributions(first: 72, after: null) {
                      edges {
                        node {
                          url
                          user {
                            email
                            id
                            login
                            name
                            url
                            websiteUrl
                          }
                          repository {
                            createdAt
                            homepageUrl
                            id
                            nameWithOwner
                            url
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
```
…could be reduced to:
```
query deeplyNestedQuery {
    viewer {
        repositories {
            assignableUsers {
                contributionsCollection {
                    commitContributionsByRepository(maxRepositories: 5) {
                        contributions {
                            repository
                        }
                    }
                }
            }
        }
    }
}
```

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