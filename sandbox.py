#!/usr/bin/env python3

import json
from pprint import pprint

from githubgql.Client import GitHubGQL


query = '''
query getViewerData {
    viewer {
        id
        login
        repositories {
            labels
        }
    }
    repository(owner: "bgraymusic", name: "bgm-nerdrock") {
        assignableUsers
    }
}
'''

four_level_query = '''
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
'''

client = GitHubGQL()
data = client.execute_all(four_level_query, page_size=5)
print(json.dumps(data, cls=GitHubGQL._Encoder))
