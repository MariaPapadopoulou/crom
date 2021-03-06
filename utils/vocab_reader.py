from lxml import etree
import codecs
import json
import sys

default_key_order = 10000

# Order imposed by the library
# @context = 0, id = 1, rdf:type = 2
# rdfs:label = 5, rdf:value = 6, dc:description = 7

fh = file('../cromulent/data/key_order.json')
data = fh.read()
fh.close()
key_order_hash = json.loads(data)

# Allow configuration of overrides for the mapping of ontology to python/json
fh = file('../cromulent/data/overrides.json')
data = fh.read()
fh.close()
property_overrides = json.loads(data)

# Allow subsetting of CRM into in-use / not-in-use to enable the library
# to warn on instantiation of not-in-use properties or classes
fh = file('crm-profile.json')
data = fh.read()
fh.close()
profile_flags = json.loads(data)

PROFILE_ONLY = '--profile' in sys.argv

NS = {'rdf':"http://www.w3.org/1999/02/22-rdf-syntax-ns#",
	'xsd':"http://www.w3.org/2001/XMLSchema#",
	'rdfs':"http://www.w3.org/2000/01/rdf-schema#",
	'dcterms':"http://purl.org/dc/terms/",
	'owl':"http://www.w3.org/2002/07/owl#",
	'crm':"http://www.cidoc-crm.org/cidoc-crm/",
	'xml': "http://www.w3.org/XML/1998/namespace",
	'la': "https://linked.art/ns/terms/"
}

fh = file('cidoc_inverse.xml')
data = fh.read()
fh.close()
dom = etree.XML(data)
stuff = []

classes = dom.xpath("//rdfs:Class", namespaces=NS)
classXHash = {}
for c in classes:
	name = c.xpath('@rdf:about', namespaces=NS)[0]
	if name.startswith(NS['la']):
		name = name.replace(NS['la'], 'la:')

	useflag = str(profile_flags.get(name, 0))
	if classXHash.has_key(name):
		classXHash[name][0] = c
	else:
		classXHash[name] = [c, useflag]

	label = c.xpath('./rdfs:label[@xml:lang="en"]/text()', namespaces=NS)[0]
	try:
		comment = c.xpath('./rdfs:comment/text()', namespaces=NS)[0]
		comment = comment.strip()
		comment = comment.replace('\n', '\\n').replace('\t', ' ')
	except:
		comment = ""

	subClsL = c.xpath('./rdfs:subClassOf/@rdf:resource', namespaces=NS)
	if subClsL:
		# could be multiples
		subCls = '|'.join(subClsL)
		for s in subClsL:
			try:
				classXHash[s][1] = 3
			except KeyError:
				classXHash[s] = [None, 3]
	else:
		subCls = ""

	if name.startswith('la:'):
		ccname = name[3:]
	else:
		uc1 = name.find("_")
		ccname = name[uc1+1:]
		ccname = ccname.replace("_or_", "_Or_").replace("_of_", "_Of_")
		ccname = ccname.replace('-', '').replace('_', '')

	stuff.append([name, "class", ccname, label, comment, subCls, useflag])

props = dom.xpath("//rdf:Property",namespaces=NS)
propXHash = {}
for p in props:
	name = p.xpath('@rdf:about', namespaces=NS)[0]
	useflags = profile_flags.get(name, [0,0]) or [0,0]
	propXHash[name] = [p, useflags[0]]

	label = p.xpath('./rdfs:label[@xml:lang="en"]/text()', namespaces=NS)[0]
	try:
		comment = p.xpath('./rdfs:comment/text()', namespaces=NS)[0]
		comment = comment.strip()
		comment = comment.replace('\n', '\\n').replace('\t', ' ')
	except:
		comment = ""

	domn = p.xpath('./rdfs:domain/@rdf:resource', namespaces=NS)
	if domn:		
		domn = domn[0]
		for (k,v) in NS.items():
			domn = domn.replace(v,"%s:" % k)
	else:
		domn = ""
	rang = p.xpath('./rdfs:range/@rdf:resource', namespaces=NS)
	if rang:
		rang = rang[0]
		for (k,v) in NS.items():
			rang = rang.replace(v,"%s:" % k)
	else:
		rang = ""
	subProp = p.xpath('./rdfs:subPropertyOf/@rdf:resource', namespaces=NS)
	if subProp:
		subProp = subProp[0]
	else:
		subProp = ""

	inverse = p.xpath('./owl:inverseOf/@rdf:resource', namespaces=NS)
	if inverse:
		inverse = inverse[0]
	else:
		inverse = ""

	uc1 = name.find("_")
	pno = name[:uc1]
	if property_overrides.has_key(pno):
		ccname = property_overrides[pno]
	else:
		ccname = name[uc1+1:]
		ccname = ccname.replace("-", "")
		if ccname.startswith("is_"):
			ccname = ccname[3:]
		elif ccname.startswith("has_") or ccname.startswith("had_") or ccname.startswith("was_"):
			ccname = ccname[4:]

	koi = str(key_order_hash.get(ccname, default_key_order))

	# either 0, or [1/2, 0/1] for okay/warn, single/multiple
	stuff.append([name, "property", ccname, label, comment, subProp, domn, rang, inverse, koi, 
		str(useflags[0]), str(useflags[1])])


# outdata = '\n'.join(['\t'.join(x) for x in stuff])
fh = codecs.open('../cromulent/data/crm_vocab.tsv', 'w', 'utf-8')
for l in stuff:
	name = l[0]
	line = '\t'.join(l) + "\n"	
	if classXHash.has_key(name):
		okay = classXHash[name][1]
	elif propXHash.has_key(name):
		okay = propXHash[name][1]
	else:
		okay = 0
		print "Could not find %s" % name
	if not PROFILE_ONLY or okay:
		fh.write(line)
fh.close()
