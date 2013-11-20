#!/usr/bin/python
#
# Copyright (C) 2012 Cyril Bouthors <cyril@bouthors.org>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.
#

from distutils.core import setup

setup(
    name='nagios2mantis',
    version='2.0',
    description='Converts Nagios notifications to Mantis issues thanks to the '
                'Soap API.',
    author='Cyril Bouthors',
    author_email='cyril@boutho.rs',
    url='http://cyril.boutho.rs/',
    packages=['nagios2mantis'],
)
