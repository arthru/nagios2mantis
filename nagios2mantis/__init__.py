#!/usr/bin/python
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
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.
#

from ConfigParser import RawConfigParser
from datetime import datetime
from datetime import timedelta
import argparse
import yaml
import sqlite3
from SOAPpy import WSDL, faultType
import logging

NAGIOS_STATES = ['UP', 'DOWN', 'CRITICAL', 'WARNING', 'OK', 'UNKNOWN',
                 'PENDING']


class Config(RawConfigParser):
    def __init__(self, configuration_file):
        RawConfigParser.__init__(self)
        self.read(configuration_file)

        self.wsdl = self.get('Mantis', 'wsdl')
        self.username = self.get('Mantis', 'username')
        self.password = self.get('Mantis', 'password')
        self.project_id = self.get('Mantis', 'default_mantis_project_id')
        self.issue_description = unicode(self.get(
            'Mantis', 'issue_description'), 'UTF-8')
        self.note_description = unicode(self.get(
            'Mantis', 'note_description'), 'UTF-8')
        self.category_name = unicode(self.get('Mantis', 'category_name'),
                                     'UTF-8')
        self.sqlite_file = self.get('Mantis2nagios', 'sqlite_file')
        self.inotify_file = self.get('Mantis2nagios', 'inotify_file')


def get_summary(hostname, state, service):
    # Host alert
    if service is None:
        return '{hostname} is {state}'.format(
            hostname=hostname,
            state=state,
        )
    # Service alert
    return '{service} is {state} on host {hostname}'.format(
        service=service,
        state=state,
        hostname=hostname,
    )


class Nagios2Mantis(object):
    def __init__(self, config):
        self.config = config
        self.db_spool = DbSpool(config.sqlite_file)

    @property
    def mantis(self):
        if not hasattr(self, '_mantis'):
            self._mantis = WSDL.Proxy(self.config.wsdl)
        return self._mantis

    def empty_cache(self):
        for row in self.db_spool.rows():
            try:
                self.empty_row(row)
            except:
                logging.exception('Treating row whose id is %d failed', row[0])
        self.db_spool.close()

    def empty_row(self, row):
        row_id, hostname, state, service, plugin_output, project_id = row
        summary = get_summary(hostname, state, service)
        issue = self.find_issue(hostname, service)

        if issue is None:
            if state == 'UP':
                return
            issue = {
                'summary': summary,
                'description': self.config.issue_description.format(
                    plugin_output=plugin_output
                ),
                'category': self.config.category_name,
                'project': {
                    'id': project_id
                },
            }
            self.add_issue(hostname, service, issue, row_id)
        else:
            self.add_note(issue['id'],
                          self.config.note_description.format(
                              state=state,
                              plugin_output=plugin_output),
                          row_id)

    def find_issue(self, hostname, service):
        # Find an existing issue
        issue_id = self.db_spool.get_issue_id(hostname, service)
        try:
            issue = self.mantis.mc_issue_get(
                self.config.username,
                self.config.password,
                issue_id
            )
        except faultType:
            issue = None
        if issue is None or issue['status']['id'] in [80, 90]:
            self.db_spool.del_relation(hostname, service)
            issue = None
        return issue

    def add_issue(self, hostname, service, issue, row_id):
        try:
            # Open Mantis issue
            logging.info('Add an issue \'%s\'', issue['summary'])
            issue_id = self.mantis.mc_issue_add(
                self.config.username,
                self.config.password,
                issue
            )
            self.db_spool.add_relation(hostname, service, issue_id)
        except faultType:
            logging.exception(
                'An error occured while adding an issue in Mantis. '
                'Params where (%s, %s, %s).',
                self.config.username,
                self.config.password,
                issue
            )
        else:
            self.db_spool.delete(row_id)

    def add_note(self, issue_id, summary, row_id):
        try:
            # Add a note
            logging.info('Add a note \'%s\' to issue %d', summary,
                         issue_id)
            note = {'text': summary}
            self.mantis.mc_issue_note_add(
                self.config.username,
                self.config.password,
                issue_id,
                note
            )
        except faultType:
            logging.exception(
                'An error occured while adding a note in Mantis. '
                'Params where (%s, %d, %s).',
                self.config.username,
                issue_id,
                note
            )
        else:
            self.db_spool.delete(row_id)

    def spool(self, hostname, state, service, plugin_output, project_id):
        try:
            self.db_spool.add(hostname, state, service, plugin_output,
                              project_id)
            self.db_spool.close()
            self.notify()
        except:
            logging.exception(
                'An error occured while addind a new item to treat. '
                'Params where hostname:%s ; state:%s ; service:%s ; '
                'plugin_output:%s ; project_id:%d',
                hostname, state, service, plugin_output, project_id
            )

    def notify(self):
        open(self.config.inotify_file, 'w').close()


def empty(args):  # pragma: no cover
    config = Config(args.configuration_file)
    nagios2mantis = Nagios2Mantis(config)
    nagios2mantis.empty_cache()


def get_project_id(host_notes):
    if host_notes is not None and host_notes is not '':
        host_notes = yaml.load(host_notes)
        if 'mantis_project_id' in host_notes:
            return host_notes['mantis_project_id']
    return None


def spool(args):  # pragma: no cover
    config = Config(args.configuration_file)
    nagios2mantis = Nagios2Mantis(config)

    project_id = get_project_id(args.host_notes) or config.project_id

    nagios2mantis.spool(args.hostname, args.state, args.service,
                        args.plugin_output, project_id)


def clean(args):  # pragma: no cover
    config = Config(args.configuration_file)
    nagios2mantis = Nagios2Mantis(config)
    one_month_ago = datetime.now() - timedelta(days=30)
    nagios2mantis.remove_old_rels(one_month_ago)


class DbSpool(object):
    def __init__(self, sqlite_file):
        self.db = sqlite3.connect(sqlite_file, timeout=120)
        self.db.execute('''
CREATE TABLE IF NOT EXISTS nagios2mantis (
  id INTEGER PRIMARY KEY,
  hostname TEXT,
  state TEXT,
  service TEXT,
  plugin_output TEXT,
  project_id INTEGER);
''')
        self.db.execute('''
CREATE TABLE IF NOT EXISTS nagios_mantis_relation(
  hostname TEXT,
  service TEXT,
  issue_id INTEGER,
  creation DATETIME
)''')

    def add_relation(self, hostname, service, issue_id):
        db_issue_id = self.get_issue_id(hostname, service)
        assert not db_issue_id, 'A relation for hostname %s and service %s '\
            'and with issue_id %d already exists' % (hostname, service,
                                                     issue_id)

        params = {
            'hostname': hostname,
            'service': service,
            'issue_id': issue_id,
            'creation': datetime.now(),
        }
        self.db.execute('''
        INSERT INTO nagios_mantis_relation
        (hostname, service, issue_id, creation)
        VALUES (:hostname, :service, :issue_id, :creation);''', params)
        self.db.commit()

    def get_issue_id(self, hostname, service):
        if service is None:
            request = '''SELECT issue_id
            FROM nagios_mantis_relation
            WHERE hostname = :hostname AND service IS :service;'''
        else:
            request = '''SELECT issue_id
            FROM nagios_mantis_relation
            WHERE hostname = :hostname AND service = :service;'''
        cursor = self.db.cursor()
        cursor.execute(request, {'hostname': hostname, 'service': service})
        try:
            rows = cursor.fetchall()
            assert len(rows) <= 1, 'More than one issue found for hostname '\
                '%s and service %s' % (hostname, service)
            if len(rows) == 0:
                return None
            return rows[0][0]
        finally:
            cursor.close()

    def del_relation(self, hostname, service):
        if service is None:
            request = '''DELETE FROM nagios_mantis_relation
            WHERE hostname = :hostname AND service IS :service;'''
        else:
            request = '''DELETE FROM nagios_mantis_relation
            WHERE hostname = :hostname AND service = :service;'''

        self.db.execute(request, {'hostname': hostname, 'service': service})
        self.db.commit()

    def remove_old_rels(self, creation_date):
        self.db.execute(
            'DELETE FROM nagios_mantis_relation '
            'WHERE creation < :creation_date',
            {'creation_date': creation_date}
        )
        self.db.commit()

    def close(self):
        self.db.close()

    def add(self, hostname, state, service, plugin_output, project_id):
        request_params = {
            'hostname': hostname,
            'state': state,
            'service': service,
            'plugin_output': plugin_output,
            'project_id': project_id
        }
        self.db.execute('''INSERT INTO nagios2mantis
        (hostname, state, service, plugin_output, project_id)
        VALUES (:hostname, :state, :service, :plugin_output, :project_id);''',
                        request_params)
        self.db.commit()

    def rows(self):
        cursor = self.db.cursor()
        cursor.execute('''
        SELECT id, hostname, state, service, plugin_output, project_id
        FROM nagios2mantis''')
        try:
            return cursor.fetchall()
        finally:
            cursor.close()

    def delete(self, id):
        self.db.execute('''DELETE FROM nagios2mantis
        WHERE id = :id;''',
                        {'id': id})
        self.db.commit()


class HelpAction(argparse._HelpAction):
    def __call__(self, parser, namespace, values, option_string=None):
        parser.print_help()

        for action in parser._actions:
            if type(action) != argparse._SubParsersAction:
                continue
            for name, subparser in action._name_parser_map.items():
                title = "%s command" % (name)
                print "\n%s\n%s\n" % (title, len(title) * '=')
                subparser.print_help()

        parser.exit()


def main(cli_args):
    # Read command line arguments
    parser = argparse.ArgumentParser(
        description='Sends Nagios alerts to Mantis', add_help=False)
    parser.add_argument(
        '-h', '--help', action=HelpAction, default=argparse.SUPPRESS,
        help='show this help message and exit'
    )
    parser.add_argument(
        '--configuration-file',
        help='INI file containing Mantis parameters',
        default='/etc/nagios2mantis.ini'
    )
    subparsers = parser.add_subparsers()

    empty_parser = subparsers.add_parser(
        'empty', help='Create mantis ticket and empty the spool')
    empty_parser.set_defaults(func=empty)

    clean_parser = subparsers.add_parser(
        'clean',
        help='Remove old relations between nagios host/service and mantis '
             'ticket'
    )
    clean_parser.set_defaults(func=clean)

    spool_parser = subparsers.add_parser(
        'spool', help='Add an new event in the spool')
    spool_parser.add_argument(
        '--hostname',
        help='Nagios hostname',
        required=True
    )
    spool_parser.add_argument(
        '--service',
        help='Nagios service. ' +
        'Do not define the service if the alerts is about a host'
    )
    spool_parser.add_argument(
        '--state',
        help='Nagios service or host state',
        choices=NAGIOS_STATES,
        required=True
    )
    spool_parser.add_argument(
        '--plugin-output',
        help='Nagios plugin output',
        required=True
    )
    spool_parser.add_argument(
        '--host-notes',
        help='Nagios host notes: YAML formatted mantis_project_id'
    )
    spool_parser.set_defaults(func=spool)

    args = parser.parse_args(cli_args)
    args.func(args)
