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
"""
The primary entry point is :class:`githubgql.Client.GitHubGQL`. This is where
you set up your authentication credentials and tell the system how to behave.
From there, queries, mutations, and other operations are triggered by calling
selected `execute_*` methods.
"""

from .Client import GitHubGQL


__all__ = ["GitHubGQL"]
