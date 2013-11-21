import ConfigParser
import unittest

import mock

from nagios2mantis import get_summary
from nagios2mantis import DbSpool
from nagios2mantis import main
from nagios2mantis import Config


class GetSummaryTest(unittest.TestCase):
    def test_hostname_state(self):
        summary = get_summary('localhost', 'DOWN', None)
        self.assertEquals(summary, 'localhost is DOWN')

    def test_hostname_state_service(self):
        summary = get_summary('localhost', 'DOWN', 'apache2')
        self.assertEquals(summary, 'apache2 is DOWN on host localhost')


class DbSpoolTest(unittest.TestCase):
    def setUp(self):
        self.spool = DbSpool(':memory:')

    def test_get_issue_id_none(self):
        issue_id = self.spool.get_issue_id('localhost', None)
        self.assertIsNone(issue_id)

    def test_get_issue_id_normal(self):
        self.spool.add_relation('localhost', None, 1)
        issue_id = self.spool.get_issue_id('localhost', None)
        self.assertEquals(1, issue_id)

    def test_get_issue_id_normal_with_service(self):
        self.spool.add_relation('localhost', 'apache2', 1)
        issue_id = self.spool.get_issue_id('localhost', 'apache2')
        self.assertEquals(1, issue_id)

    def test_get_issue_id_raises(self):
        self.spool.db.execute('''
        INSERT INTO nagios_mantis_relation (hostname, service, issue_id)
        VALUES ('localhost', NULL, 1);''')
        self.spool.db.execute('''
        INSERT INTO nagios_mantis_relation (hostname, service, issue_id)
        VALUES ('localhost', NULL, 1);''')
        with self.assertRaises(AssertionError):
            self.spool.get_issue_id('localhost', None)

    def assert_nb_nagios_mantis(self, expected_nb):
        nb = self.spool.db.execute(
            'SELECT COUNT(*) FROM nagios_mantis_relation')
        nb = list(nb)[0][0]
        self.assertEquals(expected_nb, nb)

    def test_add_relation(self):
        self.spool.add_relation('hostname', None, 1)
        self.assert_nb_nagios_mantis(1)
        result = self.spool.db.execute('SELECT * FROM nagios_mantis_relation;')
        self.assertEquals(tuple(result), ((u'hostname', None, 1),))

    def test_add_relation_raises(self):
        self.spool.add_relation('hostname', None, 1)
        with self.assertRaises(AssertionError):
            self.spool.add_relation('hostname', None, 1)

    def test_del_relation_service_none(self):
        self.spool.add_relation('hostname', None, 1)
        self.spool.del_relation('hostname', None)
        self.assert_nb_nagios_mantis(0)

    def test_del_relation_service_not_none(self):
        self.spool.add_relation('hostname', 'apache2', 1)
        self.spool.del_relation('hostname', 'apache2')
        self.assert_nb_nagios_mantis(0)

    def test_add_service_none(self):
        self.spool.add('localhost', 'DOWN', None, 'NOT OK', 1)
        result = self.spool.db.execute('SELECT * FROM nagios2mantis;')
        self.assertEquals(tuple(result),
                          ((1, u'localhost', u'DOWN', None, u'NOT OK', 1),))

    def test_add_service_not_none(self):
        self.spool.add('localhost', 'DOWN', 'apache2', 'NOT OK', 1)
        result = self.spool.db.execute('SELECT * FROM nagios2mantis;')
        self.assertEquals(tuple(result), (
            (1, u'localhost', u'DOWN', 'apache2', u'NOT OK', 1),))

    def test_rows_0(self):
        result = self.spool.rows()
        self.assertEquals(tuple(result), ())

    def test_rows_1(self):
        self.spool.add('localhost', 'DOWN', 'apache2', 'NOT OK', 1)
        result = self.spool.rows()
        self.assertEquals(tuple(result), (
            (1, u'localhost', u'DOWN', 'apache2', u'NOT OK', 1),))

    def test_delete_not_exist(self):
        self.spool.delete(1)

    def test_delete(self):
        self.spool.add('localhost', 'DOWN', 'apache2', 'NOT OK', 1)
        self.spool.delete(1)
        result = self.spool.db.execute('SELECT * FROM nagios2mantis;')
        self.assertEquals(tuple(result), ())


class MainTest(unittest.TestCase):
    def test_unknown_command(self):
        with self.assertRaises(SystemExit):
            main(['test'])

    def test_print_help(self):
        with self.assertRaises(SystemExit):
            main(['-h'])

    def test_spool(self):
        args = ['--configuration-file', '/tmp/test.ini', 'spool', '--hostname',
                'localhost', '--service', 'apache2', '--plugin-output', 'OK',
                '--state', 'UP', '--host-notes', 'test']
        with mock.patch('nagios2mantis.spool') as spool_mock:
            main(args)
            self.assertEquals(spool_mock.call_args[0][0].configuration_file,
                              '/tmp/test.ini')
            self.assertEquals(spool_mock.call_args[0][0].func,
                              spool_mock)
            self.assertEquals(spool_mock.call_args[0][0].hostname,
                              'localhost')
            self.assertEquals(spool_mock.call_args[0][0].state,
                              'UP')
            self.assertEquals(spool_mock.call_args[0][0].service,
                              'apache2')
            self.assertEquals(spool_mock.call_args[0][0].plugin_output,
                              'OK')
            self.assertEquals(spool_mock.call_args[0][0].host_notes,
                              'test')

    def test_spool_no_service(self):
        args = ['--configuration-file', '/tmp/test.ini', 'spool', '--hostname',
                'localhost', '--plugin-output', 'OK',
                '--state', 'UP', '--host-notes', 'test']
        with mock.patch('nagios2mantis.spool') as spool_mock:
            main(args)
            self.assertEquals(spool_mock.call_args[0][0].configuration_file,
                              '/tmp/test.ini')
            self.assertEquals(spool_mock.call_args[0][0].func,
                              spool_mock)
            self.assertEquals(spool_mock.call_args[0][0].hostname,
                              'localhost')
            self.assertEquals(spool_mock.call_args[0][0].state,
                              'UP')
            self.assertIsNone(spool_mock.call_args[0][0].service)
            self.assertEquals(spool_mock.call_args[0][0].plugin_output,
                              'OK')
            self.assertEquals(spool_mock.call_args[0][0].host_notes,
                              'test')

    def test_empty(self):
        with mock.patch('nagios2mantis.empty') as empty_mock:
            main(['empty'])
            self.assertTrue(empty_mock.called)
            self.assertEquals(empty_mock.call_args[0][0].configuration_file,
                              '/etc/nagios2mantis.ini')
            self.assertEquals(empty_mock.call_args[0][0].func,
                              empty_mock)

    def test_empty_conffile(self):
        with mock.patch('nagios2mantis.empty') as empty_mock:
            main(['--configuration-file', '/tmp/test.ini', 'empty'])
            self.assertTrue(empty_mock.called)
            self.assertEquals(empty_mock.call_args[0][0].configuration_file,
                              '/tmp/test.ini')


class ConfigTest(unittest.TestCase):
    def test(self):
        config = Config('tests/nagios2mantis_test.ini')
        self.assertEquals(config.wsdl, 'http://your-mantis.com/api/soap/'
                          'mantisconnect.php?wsdl')
        self.assertEquals(config.username, 'mantis_login')
        self.assertEquals(config.password, 'mantis_password')
        self.assertEquals(config.project_id, '1')
        self.assertEquals(config.issue_description,
                          'Nagios error detected: {plugin_output}')
        self.assertEquals(config.note_description,
                          'Nagios error detected. {state}: {plugin_output}')
        self.assertEquals(config.category_name, 'General')
        self.assertEquals(config.sqlite_file,
                          '/var/lib/nagios2mantis/spool.sqlite')
        self.assertEquals(config.inotify_file,
                          '/var/lib/nagios2mantis/nagios2mantis.inotify')

    def test_fail(self):
        with self.assertRaises(ConfigParser.NoSectionError):
            Config('nagios2mantis_test_fail.ini')
