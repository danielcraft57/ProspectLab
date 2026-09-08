"""Tests du filtre principal_only pour les campagnes."""
import unittest

from services.database.entreprises import EntrepriseManager


class TestCampagnePrincipalOnly(unittest.TestCase):
  """Vérifie le repli sur le meilleur email scraper si email_principal absent."""

  def test_principal_only_fallback_sur_meilleur_scraper(self):
    """Sans email_principal, principal_only garde un email (personne prioritaire)."""
    em = EntrepriseManager()
    rows = [
      {
        'id': 1,
        'nom': 'Acme',
        'secteur': 'IT',
        'responsable': 'Bob',
        'email_principal': None,
        'email': 'contact@acme.fr',
        'email_nom': 'Contact',
        'source': 'page',
        'entreprise_id': 1,
        'is_person': 0,
        'domain': 'acme.fr',
        'is_principal': 0,
      },
      {
        'id': 1,
        'nom': 'Acme',
        'secteur': 'IT',
        'responsable': 'Bob',
        'email_principal': None,
        'email': 'jean.dupont@acme.fr',
        'email_nom': 'Jean Dupont',
        'source': 'page',
        'entreprise_id': 1,
        'is_person': 1,
        'domain': 'acme.fr',
        'is_principal': 0,
      },
    ]
    result = em._group_campagne_email_rows(
      rows,
      principal_only=True,
      exclude_placeholders=False,
      exclude_risky=False,
    )
    self.assertEqual(len(result), 1)
    emails = result[0]['emails']
    self.assertEqual(len(emails), 1)
    self.assertEqual(emails[0]['email'], 'jean.dupont@acme.fr')
    self.assertTrue(emails[0]['is_principal'])

  def test_principal_only_garde_email_principal_explicite(self):
    """Avec email_principal, seul ce contact est conservé."""
    em = EntrepriseManager()
    rows = [
      {
        'id': 2,
        'nom': 'Beta',
        'secteur': 'RH',
        'responsable': 'Alice',
        'email_principal': 'alice@beta.fr',
        'email': 'autre@beta.fr',
        'email_nom': 'Autre',
        'source': 'page',
        'entreprise_id': 2,
        'is_person': 1,
        'domain': 'beta.fr',
        'is_principal': 0,
      },
      {
        'id': 2,
        'nom': 'Beta',
        'secteur': 'RH',
        'responsable': 'Alice',
        'email_principal': 'alice@beta.fr',
        'email': 'alice@beta.fr',
        'email_nom': None,
        'source': 'principal',
        'entreprise_id': 2,
        'is_person': 0,
        'domain': 'beta.fr',
        'is_principal': 1,
      },
    ]
    result = em._group_campagne_email_rows(
      rows,
      principal_only=True,
      exclude_placeholders=False,
      exclude_risky=False,
    )
    self.assertEqual(len(result), 1)
    emails = result[0]['emails']
    self.assertEqual(len(emails), 1)
    self.assertEqual(emails[0]['email'], 'alice@beta.fr')


if __name__ == '__main__':
  unittest.main()
