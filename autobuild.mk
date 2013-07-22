#
# Copyright (C) 2009 Cyril Bouthors <cyril@bouthors.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

RSYNC=rsync

VERSION=$(shell awk -F '[()]' 'NR == 1 {print $$2}' debian/changelog | cut -d- -f1)
PKG=$(shell awk 'NR == 1 {print $$1}' debian/changelog)

AUTOBUILD_DATE:=$(shell date "+%a, %m %b %Y %H:%M:%S %z")
AUTOBUILD_PACKAGE:=$(shell awk '/^Package: / {print $$2}' debian/control | head -1)
#AUTOBUILD_VERSION:=$(VERSION).r$(shell svn info | awk '/^Revision: / {print $$2}').$(shell date +%Y%m%d.%H%M)
AUTOBUILD_DISTRIBUTION=unstable
AUTOBUILD_DIR=/tmp
AUTOBUILD_ARCH:=$(shell if grep -Eq '^Architecture: all' debian/control; then echo all; else dpkg --print-architecture; fi)

# SVN_SERVER:=svn
# SVN_URL:=$(SVN_SERVER)::$(AUTOBUILD_DISTRIBUTION)

buildclean:
	rm -rf $(AUTOBUILD_DIR)/$(PKG)* $(AUTOBUILD_DIR)/$(AUTOBUILD_PACKAGE)* $(AUTOBUILD_DIR)/autobuild-$(PKG)*

debuild:
	rm -rf $(AUTOBUILD_DIR)/$(PKG)-$(VERSION)
	$(RSYNC) -aC --del --exclude .git . $(AUTOBUILD_DIR)/$(PKG)-$(VERSION)
	tar -C $(AUTOBUILD_DIR) -czf $(AUTOBUILD_DIR)/$(PKG)-$(VERSION).tar.gz $(PKG)-$(VERSION)
	cp $(AUTOBUILD_DIR)/$(PKG)-$(VERSION).tar.gz $(AUTOBUILD_DIR)/$(PKG)_$(VERSION).orig.tar.gz
	cd $(AUTOBUILD_DIR)/$(PKG)-$(VERSION) && debuild

autobuild: $(AUTOBUILD_DIR)/$(AUTOBUILD_PACKAGE)_$(AUTOBUILD_VERSION)-1_$(AUTOBUILD_ARCH).deb;

$(AUTOBUILD_DIR)/$(AUTOBUILD_PACKAGE)_$(AUTOBUILD_VERSION)-1_$(AUTOBUILD_ARCH).deb:
	rm -rf $(AUTOBUILD_DIR)/autobuild-$(PKG)-$(AUTOBUILD_VERSION)
	$(RSYNC) -aC --del --exclude .git . $(AUTOBUILD_DIR)/autobuild-$(PKG)-$(AUTOBUILD_VERSION)
	$(MAKE) -C $(AUTOBUILD_DIR)/autobuild-$(PKG)-$(AUTOBUILD_VERSION) increment-changelog-version VERSION=$(AUTOBUILD_VERSION) AUTOBUILD_VERSION=$(AUTOBUILD_VERSION)
	$(MAKE) -C $(AUTOBUILD_DIR)/autobuild-$(PKG)-$(AUTOBUILD_VERSION) debuild VERSION=$(AUTOBUILD_VERSION) AUTOBUILD_VERSION=$(AUTOBUILD_VERSION)
