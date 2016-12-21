
from cromulent.model import factory, Document, Activity, Event, TimeSpan, \
	ManMadeObject, Acquisition, Type
from cromulent.vocab import Painting

factory.base_url = "http://data.getty.edu/provenance/"
factory.default_lang = "en"

catalog = Document("catalog")
page = Document("catalog-entry")
catalog.composed_of = page
auction = Activity("auction")
catalog.documents = auction
lot = Activity("lot")
auction.consists_of = lot
page.documents = lot
txn = Acquisition("sale")
lot.consists_of = txn
what = Painting('my-painting')
txn.transferred_title_of = what
what.label = "My First Paint By Numbers"

print factory.toString(catalog, compact=False)
