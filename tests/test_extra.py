
import unittest 

try:
	from collections import OrderedDict
except:
	# 2.6
	from ordereddict import OrderedDict

from cromulent import extra
from cromulent.model import factory, Person, DataError, Dimension


class TestExtraClasses(unittest.TestCase):

	def test_payment(self):
		factory.context_uri = "http://example.org/context.json",
		expect = OrderedDict([
			('@context', factory.context_uri), \
			('id', u'http://lod.example.org/museum/Payment/1'), ('type', 'Payment'), \
			('paid_to', 'http://lod.example.org/museum/Person/1')])
		p = extra.Payment('1')
		who = Person('1')
		p.paid_to = who
		pjs = factory.toJSON(p)
		self.assertEqual(pjs, expect)

	def test_add_schema(self):
		who = Person("1")
		self.assertRaises(DataError, who.__setattr__, 'exact_match', who)
		extra.add_schema_properties()
		who.exact_match = who
		self.assertEqual(who.exact_match, [who])

	def test_add_value(self):
		what = Dimension("1")
		self.assertRaises(DataError, what.__setattr__, 'value', 6)
		extra.add_rdf_value()
		what.value = 6
		self.assertEqual(what.value, 6)
