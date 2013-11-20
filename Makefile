#
# Copyright (C) 2013 Cyril Bouthors <cyril@boutho.rs>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.
#

DESTDIR=/usr/local

all: man/nagios2mantis.1;

include autobuild.mk

clean:
	$(RM) man/nagios2mantis.1

man/nagios2mantis.1: bin/nagios2mantis
	mkdir -p man
	help2man --name $(@F) --version-string=1.0 --no-discard-stderr $< -o $@

install:
	./setup.py install --prefix=debian/nagios2mantis/usr \
		--install-layout=deb
	mkdir -p $(DESTDIR)/usr/bin
	cp -p bin/* $(DESTDIR)/usr/bin
	cp -pr etc $(DESTDIR)
	mkdir -p $(DESTDIR)/usr/share/man/man1
	cp -p man/*.1 $(DESTDIR)/usr/share/man/man1
