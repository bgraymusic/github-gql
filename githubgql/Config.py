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

from pathlib import Path
import yaml


class Config:
    """Access to config.yml data"""

    instance: Config = None

    @staticmethod
    def get() -> Config:
        return Config.instance or Config()

    def __init__(self):
        self.github_graphql_endpoint = None
        self.github_graphql_schema = None
        self.paged_selections = None
        self.unpaged_selections = None

        with open(f"{Path(__file__).parent}/config.yml", "r") as f:
            data = yaml.load(f.read(), yaml.BaseLoader)
        for key, value in data.items():
            setattr(self, key, value)
