import unittest

from nagios2mantis import get_summary
from nagios2mantis import DbSpool


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
