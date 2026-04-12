"""Test minimal location_harvest (sans réseau)."""
from bs4 import BeautifulSoup

from services.location_harvest import finalize_scraped_location, harvest_locations_from_page


def test_json_ld_localbusiness():
    html = """
    <html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@type":"LocalBusiness","name":"Test",
     "address":{"@type":"PostalAddress","streetAddress":"10 rue de Paris",
     "postalCode":"57000","addressLocality":"Metz","addressCountry":"FR"},
     "telephone":"+33 3 87 00 00 00"}
    </script></head><body></body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    hits = harvest_locations_from_page(soup, "https://exemple.fr/contact", 0)
    fin = finalize_scraped_location(hits)
    assert fin["postal_code"] == "57000"
    assert fin["locality"] == "Metz"
    assert "rue" in fin["street_address"].lower()
    assert fin.get("telephone")


if __name__ == "__main__":
    test_json_ld_localbusiness()
    print("ok")
