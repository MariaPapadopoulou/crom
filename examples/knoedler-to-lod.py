
import json
import codecs
import re
import inspect

from cromulent import model, vocab
from cromulent.model import factory, TimeSpan, ManMadeObject, Type, Identifier, \
	Production, Actor, Person, Place, Group, Material, Mark, \
	Activity, InformationObject, Purchase, Acquisition, MonetaryAmount, \
	Currency, MeasurementUnit, Dimension, PhysicalObject

from cromulent.vocab import Painting, Drawing, Furniture, Sculpture, Tapestry, AccessionNumber
from cromulent.vocab import dimensionUnits, dimensionTypes

from cromulent.extra import Payment

factory.base_url = "http://data.getty.edu/provenance/"
factory.context_uri = "http://data.getty.edu/contexts/crm_context.jsonld"
 
endOfMonths = {'01': 31, '02': 28, '03':31, '04':30, '05':31, '06':30,\
	'07':31, '08':31, '09':30, '10':31, '11':30, '12':31}

# At the moment it's just an activity, no subtype info
class TakeInventory(Activity): 
	pass

aat_type_mapping = {
	"Painting": Painting,
	"Drawing": Drawing,
	"Furniture": Furniture,
	"Sculpture": Sculpture,
	"Tapestry": Tapestry,
	"Watercolor": Painting,
	"Pastel": Painting
}

aat_genre_mapping = { 
	"Abstract" : "300134134", # maybe?
	"abstract" : "300134134", # maybe?
	"Genre": "300139140", # maybe?
	"History": "300386045",  
	"Landscape": "300015636",
	"Portrait": "300015637",
	"Still Life": "300015638"
}

genreTypes = {}
for (k,v) in aat_genre_mapping.items():
	t = Type("http://vocab.getty.edu/aat/%s" % v)
	t.label = k
	genreTypes[k] = t

knoedler = Group("knoedler")
knoedler.label = "Knoedler"

def process_money_value(value):
	value = value.replace('[', '')
	value = value.replace(']', '')
	value = value.replace('-', '')
	value = value.replace("?", '')
	value = value.replace('not written', '')
	value = value.replace('sold at auction', '')
	value = value.replace('x', '')
	value = value.replace('Lot Price', '')
	value = value.replace('See sales book', '')
	value = value.strip()
	return value

def process_materials(what, materials):
	materials = materials.lower()
	materials = materials.replace("&", "and")
	materials = materials.replace("card [cardboard]", "cardboard")
	materials = materials.replace("c [canvas]", "canvas")
	materials = materials.replace("w/c [watercolor]", "watercolor")
	materials = materials.replace("[bronze]", "bronze")
	materials = materials.replace("c on p [canvas on panel]", "canvas on panel")
	materials = materials.replace("[from sales book 9, 1907-1912, f. 361]", "")
	materials = materials.replace("p [panel]", "panel")
	materials = materials.replace('terra cotta', 'terracotta')
	materials = materials.replace(',', '')
	materials = materials.replace('-', '')
	materials = materials.replace('procelain', 'porcelain')
	materials = materials.strip()
	matwds = materials.split(' ')
	mats = []
	for mw in matwds:
		if mw in ['on', 'and']:
			continue
		try:
			mats.append(materialTypes[mw])
		except:
			# print "Material not found: %s" % mw
			pass

	return mats

divre = re.compile('^([0-9]+) ([0-9]+)/([0-9]+)( |$)')
unitre = re.compile('^([0-9.]+) (high|height|h|long|length|l)( |$)')
	
def process_dimensions(dims):
	dims = dims.lower()
	# assume default of inches
	dims = dims.replace('"', '')
	dims = dims.replace('in.', '')
	dims = dims.replace('inches', '')
	dims = dims.replace('//', '/')
	dims = dims.replace('[', '')
	dims = dims.replace(']', '')
	dims = dims.replace('X', 'x')
	dl = dims.split('x')

	dimensions = []
	p = 0
	for d in dl:
		d = d.strip()
		# check for (nn n/n)
		which = ""
		m = divre.match(d)
		if m:
			(main, numr, denom, end) = m.groups()
			ttl = int(main) + (float(numr) / float(denom))
		else:
			try:
				ttl = int(d)
			except:
				m = unitre.match(d)
				if m:
					(ttl, which, end) = m.groups()
					if which.startswith('h'):
						which = 'h'
					else:
						which = 'w'
				else:
					# print "----- %s" % d
					continue
		if not which:
			which = "w" if p else "h"
		p += 1
		dimensions.append([ttl, which])
	return dimensions

stock_books = {}
pages = {}

fh = file('knoedler_cache.json')
cache = json.load(fh)
fh.close()

recs = cache.values()
recs = sorted(recs, key=lambda x: x['star_id'])[:10]

for rec in recs:

	bookId = rec['stock_book_id']
	try:
		book = stock_books[bookId]
	except:
		# create the book
		book = InformationObject(bookId)
		book.label = "Knoedler Stock Book %s" % bookId
		stock_books[bookId] = book

	pageId = "%s/%s" % (bookId, rec['page_num'])
	try:
		page = pages[pageId]
	except:
		# create the page in the book
		page = InformationObject(pageId)
		page.label = "Page %s" % rec['page_num']
		pages[pageId] = page
		book.composed_of = page

	# create the entry
	entryId = "%s/%s" % (pageId, rec['row_num'])
	entry = InformationObject(entryId)
	entry.label = "Row %s" % rec['row_num']
	page.composed_of = entry

	# the description and notes fields are related to the entry
	# not the object
	if rec['notes']:
		entry.description = rec['notes']
	if rec['description']:
		entry.description = rec['description']

	oid = rec['pi_id']

	# create the activity that the entry describes

	# The outbound activity
	txn = None
	inv = None

	txnType = rec['transaction']
	if txnType == "Sold":
		txn = Purchase(oid)
	elif txnType in ['Exchanged', 'Presented', 'Transferred']:
		if rec['price_amount']:
			txn = Purchase(oid)
		else:
			txn = Acquisition(oid)
	elif txnType in ["Unsold", "Cancelled"]:
		# Stock taking, or never left inventory due to no sale
		inv = TakeInventory(oid)
	elif txnType in ["Lost", "Removed"]:
		# Leaves inventory, but not via a transfer of ownership
		# E8 can represent end of ownership. There's just no new owner.
		txn = Acquisition(oid)
	elif txnType == "Voided":
		# Bad data; voided should be skipped (per Kelly)
		continue
	elif txnType == "Returned":
		# Can't tell what this actually means yet
		# Could be entering or leaving Knoedler stock!
		continue
	elif txnType == "Unknown":
		if rec['price_amount']:
			txn = Purchase(oid)
		else:
		 inv = TakeInventory(oid)
	else:
		# I think this is only Disjointed
		# print_rec(rec)
		continue

	# The inbound activity that always happens
	# For consistency, always generate a Payment
	if rec['purchase_amount']:
		inTxn = Purchase("purch_%s" % oid)
		pay = Payment("purch_%s" % oid)
		inTxn.consists_of = pay

		amnt = MonetaryAmount("purch_price_%s" % oid)
		value = process_money_value(rec['purchase_amount'])
		if value:
			try:
				amnt.value = float(value)
			except:
				amnt.description = value
		if rec['purchase_currency']:
			curr = Currency(rec['purchase_currency'])
			curr.label = rec['purchase_currency']
			amnt.currency = curr
		if rec['purchase_note']:
			amnt.description = rec['purchase_note']		
		pay.paid_amount = amnt
		pay.paid_from = knoedler
		inTxn.sales_price = amnt

	else:
		inTxn = Acquisition("purch_%s" % oid)

	inTxn.transferred_title_to = knoedler
	if rec['seller_name'] or rec['seller_name_auth']:
		# Look up in authority?
		seller = Actor("seller_%s" % oid)
		seller.label = rec['seller_name_auth'] if rec['seller_name_auth'] else rec['seller_name']
		if rec['seller_loc'] or rec['seller_loc_auth']:
			sellerPlace = Place("seller_place_%s" % oid)
			sellerPlace.label = rec['seller_loc_auth'] if rec['seller_loc_auth'] else rec['seller_loc']
			seller.current_or_former_residence = sellerPlace
		inTxn.transferred_title_from = seller
		if rec['purchase_amount']:
			pay.paid_to = seller

	# CurationPeriod
	curated = Activity("curated_%s" % oid)
	curated.started_by = inTxn

	if txn:
		# from
		txn.transferred_title_from = knoedler
		# to
		if rec['buyer_name'] or rec['buyer_name_auth']:
			# Look up in authority?
			buyer = Actor("buyer_%s" % oid)
			buyer.label = rec['buyer_name_auth'] if rec['buyer_name_auth'] else rec['buyer_name']
			if rec['buyer_loc'] or rec['buyer_loc_auth']:
				buyerPlace = Place("buyer_place_%s" % oid)
				buyerPlace.label = rec['buyer_loc_auth'] if rec['buyer_loc_auth'] else rec['buyer_loc']
				buyer.current_or_former_residence = buyerPlace
			txn.transferred_title_to = buyer

		# when
		if rec['sale_date_year']:
			# if year, then all. blank is "00"			
			yr = rec['sale_date_year']
			mt = rec['sale_date_month']
			dy = rec['sale_date_day']
			if dy != "00":
				start = "%s-%s-%s" % (yr,mt,dy)
				end = start
			elif mt != "00":
				start = "%s-%s-01" % (yr,mt)
				end = "%s-%s-%s" % (yr,mt,endOfMonths[mt])
			else:
				start = "%s-01-01" % yr
				end = "%s-12-31" % yr
			span = TimeSpan("sale_span_%s" % oid)
			span.begin_of_the_begin = start
			span.end_of_the_end = end
			txn.timespan = span

		value = process_money_value(rec['price_amount'])
		if value:
			amnt = MonetaryAmount("sale_price_%s" % oid)
			try:
				amnt.value = float(value)
			except:
				amnt.description = value
			if rec['price_currency']:
				curr = Currency(rec['price_currency'])
				curr.label = rec['price_currency']
				amnt.currency = curr
			if rec['price_note']:
				amnt.description = rec['price_note']
			txn.sales_price = amnt

			# Check knoedler_share
			if rec['knoedler_share_amount']:

				value = process_money_value(rec['knoedler_share_amount'])
				if value:
					amnt = MonetaryAmount("shared_price_%s" % oid)
					try:
						amnt.value = float(value)
					except:
						amnt.description = value
					if rec['knoedler_share_currency']:
						curr = Currency(rec['knoedler_share_currency'])
						curr.label = rec['knoedler_share_currency']
						amnt.currency = curr
					if rec['knoedler_share_note']:
						amnt.description = rec['knoedler_share_note']

				pay = Payment("kshare_%s" % oid)
				txn.consists_of = pay
				pay.paid_amount = amnt
				pay.paid_to = knoedler
				if rec['buyer_name'] or rec['buyer_name_auth']:
					pay.paid_from = buyer

			else:
				pay = Payment("sale_%s" % oid)
				txn.consists_of = pay
				pay.paid_amount = amnt
				pay.paid_to = knoedler
				if rec['buyer_name'] or rec['buyer_name_auth']:
					pay.paid_from = buyer

		curated.finished_by = txn
	elif inv:
		# Taking of Inventory as part of the curation period
		curated.consists_of = inv

		# If taking inventory, then the entry date is for that
		if rec['entry_date_year']:
			# if year, then all. blank is "00"			
			yr = rec['entry_date_year']
			mt = rec['entry_date_month']
			dy = rec['entry_date_day']
			if dy != "00":
				start = "%s-%s-%s" % (yr,mt,dy)
				end = start
			elif mt != "00":
				start = "%s-%s-01" % (yr,mt)
				end = "%s-%s-%s" % (yr,mt,endOfMonths[mt])
			else:
				start = "%s-01-01" % yr
				end = "%s-12-31" % yr
			span = TimeSpan("sale_span_%s" % oid)
			span.begin_of_the_begin = start
			span.end_of_the_end = end
			inv.timespan = span


	if not inv:
		# entry date is for purchase
		if rec['entry_date_year']:
			# if year, then all. blank is "00"			
			yr = rec['entry_date_year']
			mt = rec['entry_date_month']
			dy = rec['entry_date_day']
			if dy != "00":
				start = "%s-%s-%s" % (yr,mt,dy)
				end = start
			elif mt != "00":
				start = "%s-%s-01" % (yr,mt)
				end = "%s-%s-%s" % (yr,mt,endOfMonths[mt])
			else:
				start = "%s-01-01" % yr
				end = "%s-12-31" % yr
			span = TimeSpan("purch_span_%s" % oid)
			span.begin_of_the_begin = start
			span.end_of_the_end = end
			inTxn.timespan = span

	# create the object of the transaction

	objectType = rec['object_type']
	try:
		what = aat_type_mapping[objectType](oid)
	except:
		what = ManMadeObject(oid)

	curated.used_specific_object = what
	inTxn.transferred_title_of = what
	entry.refers_to = inTxn
	if txn:
		txn.transferred_title_of = what
		entry.refers_to = txn
	elif txnType == "Voided":
		entry.refers_to = what	

	what.label = rec['title']

	idnt = AccessionNumber("knoedler_%s" % oid)
	idnt.value = rec['knoedler_id']
	# No way to say it's Knoedler's number?
	# Could have a Creation of the Identifier performed by Knoedler :(

	if rec['artist_name'] or rec['artist_name_auth']:
		artist = Person("artist_%s" % oid)
		artist.label = rec['artist_name_auth'] if rec['artist_name_auth'] else rec['artist_name']
		if rec['nationality']:
			artist.nationality = Place("artist_natl_%s" % oid)
			artist.nationality.label = rec['nationality']

		prodn = Production("production_%s" % oid)
		prodn.carried_out_by = artist
		what.produced_by = prodn

	if rec['artist_name_2'] or rec['artist_name_auth_2']:
		artist = Person("artist2_%s" % oid)
		artist.label = rec['artist_name_auth_2'] if rec['artist_name_auth_2'] else rec['artist_name_2']
		if rec['nationality_2']:
			artist.nationality = Place('artist_2_natl_%s' % oid)
			artist.nationality.label = rec['nationality_2']
		prodn.carried_out_by = artist

	# genre
	if rec['genre'] and not rec['genre'] == '[not identified]':
		if not aat_genre_mapping.has_key(rec['genre']):
			print "Not found: %s" % (rec['genre'])
		else:	
			what.classified_as = genreTypes[rec['genre']]

	# subject
	if rec['subject']:
		s = rec['subject']
		if s.find(';'):
			ss = [x.strip() for x in s.split(';')]
		else:
			ss = [s]
		for s in ss:
			# s  = s.replace('Int\xe9rieurs', 'Interiors')
			sid = s.replace(' ', '')
			sid = sid.replace('(', '')
			sid = sid.replace(')', '')
			t = Type(sid)
			t.label = s
			what.depicts = t

	# materials
	if rec['materials']:
		# XXX Finish this
		process_materials(what, rec['materials'])
		# what.made_of = material

	if rec['dimensions']:
		# XXX Finish this too
		dims = process_dimensions(rec['dimensions'])
		for d in dims:
			dim = Dimension("%s_%s" % (d[0], oid))
			dim.value = d[0]
			dim.unit = dimensionUnits['inches']
			if d[1] == 'h':
				what.height = dim
			else:
				what.width = dim				

collection = InformationObject("collection")
for s in stock_books.values():
	collection.composed_of = s

factory.full_names = False
outstr = factory.toString(collection, compact=False)
