import ConfigParser
from datetime import datetime
import os.path
import tempfile
import time
import unittest

import mock

from SOAPpy import faultType

from nagios2mantis import get_summary
from nagios2mantis import DbSpool
from nagios2mantis import main
from nagios2mantis import Config
from nagios2mantis import Nagios2Mantis
from nagios2mantis import get_project_id


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
        self.assertEquals(tuple(result)[0][:3], (u'hostname', None, 1))

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

    def test_remove_old_rels(self):
        self.spool.add_relation('hostname', 'apache2', 1)
        time.sleep(1)
        self.spool.remove_old_rels(datetime.now())
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

    def test_close(self):
        self.spool.db = mock.MagicMock()

        self.spool.close()

        self.spool.db.close.assert_called_once_with()


class MainTest(unittest.TestCase):
    def test_unknown_command(self):
        with self.assertRaises(SystemExit), mock.patch('sys.stderr'):
            main(['test'])

    def test_print_help(self):
        with self.assertRaises(SystemExit), mock.patch('sys.stdout'):
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

    def test_clean(self):
        with mock.patch('nagios2mantis.clean') as clean_mock:
            main(['clean'])
            self.assertTrue(clean_mock.called)
            self.assertEquals(clean_mock.call_args[0][0].configuration_file,
                              '/etc/nagios2mantis.ini')
            self.assertEquals(clean_mock.call_args[0][0].func,
                              clean_mock)


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


class Nagios2MantisTest(unittest.TestCase):
    def setUp(self):
        self.config = Config('tests/nagios2mantis_test.ini')
        self.config.sqlite_file = ':memory:'
        self.config.inotify_file = tempfile.mkstemp()[1]

    def tearDown(self):
        os.remove(self.config.inotify_file)

    def test_notify(self):
        nagios2mantis = Nagios2Mantis(self.config)
        before_time = os.path.getctime(self.config.inotify_file)
        time.sleep(1)
        nagios2mantis.notify()
        after_time = os.path.getctime(self.config.inotify_file)
        self.assertNotEquals(before_time, after_time)

    def test_spool(self):
        nagios2mantis = Nagios2Mantis(self.config)
        nagios2mantis.db_spool.add = mock.MagicMock()
        nagios2mantis.db_spool.close = mock.MagicMock()
        before_time = os.path.getctime(self.config.inotify_file)
        time.sleep(1)

        nagios2mantis.spool('localhost', 'UP', None, 'OK', 1)

        nagios2mantis.db_spool.add.assert_called_once_with(
            'localhost', 'UP', None, 'OK', 1)
        nagios2mantis.db_spool.close.assert_called_once_with()
        after_time = os.path.getctime(self.config.inotify_file)
        self.assertNotEquals(before_time, after_time)

    def test_mantis(self):
        nagios2mantis = Nagios2Mantis(self.config)
        with mock.patch('SOAPpy.WSDL.Proxy') as ws_mock:
            mantis_ws = nagios2mantis.mantis
            ws_mock.assert_called_once_with(
                'http://your-mantis.com/api/soap/mantisconnect.php?wsdl')
            self.assertEquals(mantis_ws, nagios2mantis._mantis)

    def test_mantis_twice(self):
        nagios2mantis = Nagios2Mantis(self.config)
        with mock.patch('SOAPpy.WSDL.Proxy') as ws_mock:
            mantis_ws = nagios2mantis.mantis
            mantis_ws_2 = nagios2mantis.mantis

            ws_mock.assert_called_once_with(
                'http://your-mantis.com/api/soap/mantisconnect.php?wsdl')
            self.assertEquals(mantis_ws, mantis_ws_2)

    def test_add_note(self):
        nagios2mantis = Nagios2Mantis(self.config)
        nagios2mantis.db_spool.delete = mock.MagicMock()
        with mock.patch('SOAPpy.WSDL.Proxy'):
            nagios2mantis.add_note(1, 'test', 1)
            nagios2mantis.mantis.mc_issue_note_add.assert_called_once_with(
                'mantis_login', 'mantis_password', 1, {'text': 'test'})
            nagios2mantis.db_spool.delete.assert_called_once_with(1)

    def test_add_note_failed(self):
        nagios2mantis = Nagios2Mantis(self.config)
        nagios2mantis.db_spool.delete = mock.MagicMock()
        with mock.patch('SOAPpy.WSDL.Proxy'):
            nagios2mantis.mantis.mc_issue_note_add.side_effect = faultType

            nagios2mantis.add_note(1, 'test', 1)

            nagios2mantis.mantis.mc_issue_note_add.assert_called_once_with(
                'mantis_login', 'mantis_password', 1, {'text': 'test'})
            self.assertFalse(nagios2mantis.db_spool.delete.called)

    def test_add_issue(self):
        nagios2mantis = Nagios2Mantis(self.config)
        nagios2mantis.db_spool.delete = mock.MagicMock()
        nagios2mantis.db_spool.add_relation = mock.MagicMock()
        with mock.patch('SOAPpy.WSDL.Proxy'):
            nagios2mantis.mantis.mc_issue_add.return_value = 2
            nagios2mantis.add_issue('localhost', 'apache2',
                                    {'summary': 'test'}, 1)

            nagios2mantis.mantis.mc_issue_add.assert_called_once_with(
                'mantis_login', 'mantis_password', {'summary': 'test'})
            nagios2mantis.db_spool.delete.assert_called_once_with(1)
            nagios2mantis.db_spool.add_relation.assert_called_once_with(
                'localhost', 'apache2', 2)

    def test_add_issue_failed(self):
        nagios2mantis = Nagios2Mantis(self.config)
        nagios2mantis.db_spool.delete = mock.MagicMock()
        nagios2mantis.db_spool.add_relation = mock.MagicMock()
        with mock.patch('SOAPpy.WSDL.Proxy'):
            nagios2mantis.mantis.mc_issue_add.side_effect = faultType
            nagios2mantis.add_issue('localhost', 'apache2',
                                    {'summary': 'test'}, 1)

            nagios2mantis.mantis.mc_issue_add.assert_called_once_with(
                'mantis_login', 'mantis_password', {'summary': 'test'})
            self.assertFalse(nagios2mantis.db_spool.delete.called)
            self.assertFalse(nagios2mantis.db_spool.add_relation.called)

    def test_find_issue(self):
        nagios2mantis = Nagios2Mantis(self.config)
        nagios2mantis.db_spool.get_issue_id = mock.MagicMock(return_value=1)
        nagios2mantis.db_spool.del_relation = mock.MagicMock()
        with mock.patch('SOAPpy.WSDL.Proxy'):
            nagios2mantis.mantis.mc_issue_get.return_value = None

            result = nagios2mantis.find_issue('localhost', 'apache2')

            self.assertIsNone(result)
            nagios2mantis.db_spool.get_issue_id.assert_called_once_with(
                'localhost', 'apache2')
            nagios2mantis.db_spool.del_relation.assert_called_once_with(
                'localhost', 'apache2')
            nagios2mantis.mantis.mc_issue_get.assert_called_once_with(
                'mantis_login', 'mantis_password', 1)

    def test_find_issue_fault(self):
        nagios2mantis = Nagios2Mantis(self.config)
        nagios2mantis.db_spool.get_issue_id = mock.MagicMock(return_value=1)
        nagios2mantis.db_spool.del_relation = mock.MagicMock()
        with mock.patch('SOAPpy.WSDL.Proxy'):
            nagios2mantis.mantis.mc_issue_get.side_effect = faultType

            result = nagios2mantis.find_issue('localhost', 'apache2')

            self.assertIsNone(result)
            nagios2mantis.db_spool.get_issue_id.assert_called_once_with(
                'localhost', 'apache2')
            nagios2mantis.db_spool.del_relation.assert_called_once_with(
                'localhost', 'apache2')
            nagios2mantis.mantis.mc_issue_get.assert_called_once_with(
                'mantis_login', 'mantis_password', 1)

    def test_find_issue_found_not_closed(self):
        nagios2mantis = Nagios2Mantis(self.config)
        nagios2mantis.db_spool.get_issue_id = mock.MagicMock(return_value=1)
        nagios2mantis.db_spool.del_relation = mock.MagicMock()
        with mock.patch('SOAPpy.WSDL.Proxy'):
            nagios2mantis.mantis.mc_issue_get.return_value = {'status': {
                'id': 10}}

            result = nagios2mantis.find_issue('localhost', 'apache2')

            self.assertEquals(result, {'status': {'id': 10}})
            nagios2mantis.db_spool.get_issue_id.assert_called_once_with(
                'localhost', 'apache2')
            self.assertFalse(nagios2mantis.db_spool.del_relation.called)
            nagios2mantis.mantis.mc_issue_get.assert_called_once_with(
                'mantis_login', 'mantis_password', 1)

    def test_find_issue_found_closed(self):
        nagios2mantis = Nagios2Mantis(self.config)
        nagios2mantis.db_spool.get_issue_id = mock.MagicMock(return_value=1)
        nagios2mantis.db_spool.del_relation = mock.MagicMock()
        with mock.patch('SOAPpy.WSDL.Proxy'):
            nagios2mantis.mantis.mc_issue_get.return_value = {'status': {
                'id': 80}}

            result = nagios2mantis.find_issue('localhost', 'apache2')

            self.assertIsNone(result)
            nagios2mantis.db_spool.get_issue_id.assert_called_once_with(
                'localhost', 'apache2')
            nagios2mantis.mantis.mc_issue_get.assert_called_once_with(
                'mantis_login', 'mantis_password', 1)
            nagios2mantis.db_spool.del_relation.assert_called_once_with(
                'localhost', 'apache2')

    def test_empty_row_not_found(self):
        nagios2mantis = Nagios2Mantis(self.config)
        nagios2mantis.find_issue = mock.MagicMock(return_value=None)
        nagios2mantis.add_issue = mock.MagicMock()
        nagios2mantis.add_note = mock.MagicMock()

        nagios2mantis.empty_row((1, 'localhost', 'DOWN', 'apache2', 'OK', 1))

        nagios2mantis.find_issue.assert_called_once_with(
            'localhost', 'apache2')
        expected_issue = {
            'category': u'General',
            'project': {'id': 1},
            'description': u'Nagios error detected: OK',
            'summary': 'apache2 is DOWN on host localhost'
        }
        nagios2mantis.add_issue.assert_called_once_with('localhost', 'apache2',
                                                        expected_issue, 1)
        self.assertFalse(nagios2mantis.add_note.called)

    def test_empty_row_not_found_state_up(self):
        nagios2mantis = Nagios2Mantis(self.config)
        nagios2mantis.find_issue = mock.MagicMock(return_value=None)
        nagios2mantis.add_issue = mock.MagicMock()
        nagios2mantis.add_note = mock.MagicMock()

        nagios2mantis.empty_row((1, 'localhost', 'UP', 'apache2', 'OK', 1))

        nagios2mantis.find_issue.assert_called_once_with(
            'localhost', 'apache2')
        self.assertFalse(nagios2mantis.add_issue.called)
        self.assertFalse(nagios2mantis.add_note.called)

    def test_empty_row_found(self):
        nagios2mantis = Nagios2Mantis(self.config)
        nagios2mantis.find_issue = mock.MagicMock(return_value={'id': 1})
        nagios2mantis.add_issue = mock.MagicMock()
        nagios2mantis.add_note = mock.MagicMock()

        nagios2mantis.empty_row((1, 'localhost', 'UP', 'apache2', 'OK', 1))

        nagios2mantis.find_issue.assert_called_once_with(
            'localhost', 'apache2')
        nagios2mantis.add_note.assert_called_once_with(
            1, u'Nagios error detected. UP: OK', 1)
        self.assertFalse(nagios2mantis.add_issue.called)

    def test_empty_cache(self):
        nagios2mantis = Nagios2Mantis(self.config)

        nagios2mantis.db_spool.rows = mock.MagicMock(return_value=[1, 2])
        nagios2mantis.empty_row = mock.MagicMock()
        nagios2mantis.db_spool.close = mock.MagicMock()

        nagios2mantis.empty_cache()

        nagios2mantis.db_spool.rows.assert_called_once_with()
        self.assertEquals(nagios2mantis.empty_row.call_count, 2)
        nagios2mantis.db_spool.close.assert_called_once_with()

    def test_empty_cache_none(self):
        nagios2mantis = Nagios2Mantis(self.config)

        nagios2mantis.db_spool.rows = mock.MagicMock(return_value=[])
        nagios2mantis.empty_row = mock.MagicMock()
        nagios2mantis.db_spool.close = mock.MagicMock()

        nagios2mantis.empty_cache()

        nagios2mantis.db_spool.rows.assert_called_once_with()
        self.assertFalse(nagios2mantis.empty_row.called)
        nagios2mantis.db_spool.close.assert_called_once_with()


class GetProjectIdTest(unittest.TestCase):
    def test_none(self):
        result = get_project_id(None)
        self.assertIsNone(result)

    def test_empty(self):
        result = get_project_id('')
        self.assertIsNone(result)

    def test_not_yaml(self):
        result = get_project_id('test')
        self.assertIsNone(result)

    def test_normal(self):
        result = get_project_id('mantis_project_id: 1')
        self.assertEquals(result, 1)
