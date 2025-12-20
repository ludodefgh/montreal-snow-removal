#!/usr/bin/env python3
"""Script de test pour l'API Planif-Neige.

Usage:
    python3 test_api.py YOUR_API_TOKEN

Ce script teste la connexion à l'API Planif-Neige et affiche les résultats.
"""

import sys
import asyncio
from datetime import datetime, timedelta
from zeep import Client
from zeep.transports import Transport
from zeep.plugins import Plugin
from requests import Session


class CustomTransport(Transport):
    """Custom Zeep Transport that forces User-Agent on all HTTP requests."""

    def __init__(self, user_agent: str, **kwargs):
        """Initialize with User-Agent header."""
        super().__init__(**kwargs)
        self.user_agent = user_agent

    def _load_remote_data(self, url):
        """Override to add User-Agent header to GET requests."""
        if self.session:
            self.session.headers['User-Agent'] = self.user_agent
        return super()._load_remote_data(url)


class UserAgentPlugin(Plugin):
    """Zeep plugin to ensure User-Agent header is sent on SOAP requests."""

    def __init__(self, user_agent: str):
        """Initialize plugin with User-Agent string."""
        self.user_agent = user_agent

    def egress(self, envelope, http_headers, operation, binding_options):
        """Add User-Agent to outgoing HTTP headers."""
        http_headers["User-Agent"] = self.user_agent
        return envelope, http_headers


def test_wsdl_loading(wsdl_url: str) -> bool:
    """Test si le WSDL se charge correctement.

    Args:
        wsdl_url: URL du WSDL

    Returns:
        True si le chargement réussit, False sinon
    """
    print(f"\n{'='*60}")
    print(f"Test 1: Chargement du WSDL")
    print(f"{'='*60}")
    print(f"URL: {wsdl_url}")

    try:
        session = Session()
        session.verify = True
        # Ajouter un User-Agent de navigateur pour éviter le blocage
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        session.headers.update({'User-Agent': user_agent})

        # Transport personnalisé qui force le User-Agent sur TOUTES les requêtes
        transport = CustomTransport(user_agent=user_agent, session=session, timeout=30)

        # Plugin pour les requêtes SOAP
        user_agent_plugin = UserAgentPlugin(user_agent)

        print("⏳ Chargement du WSDL...")
        client = Client(wsdl=wsdl_url, transport=transport, plugins=[user_agent_plugin])

        print("✅ WSDL chargé avec succès!")
        print(f"   Services disponibles: {list(client.wsdl.services.keys())}")

        return True

    except Exception as e:
        print(f"❌ Échec du chargement du WSDL")
        print(f"   Erreur: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        return False


def test_api_call(api_token: str, use_production: bool = True) -> dict:
    """Test un appel à l'API GetPlanificationsForDate.

    Args:
        api_token: Token d'authentification API
        use_production: Utiliser l'API de production (True) ou test (False)

    Returns:
        Dictionnaire avec les résultats du test
    """
    print(f"\n{'='*60}")
    print(f"Test 2: Appel API GetPlanificationsForDate")
    print(f"{'='*60}")

    # Choisir l'URL
    if use_production:
        wsdl_url = "https://servicesenligne2.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService?wsdl"
        env = "PRODUCTION"
    else:
        wsdl_url = "https://servicesenlignedev.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService?wsdl"
        env = "TEST"

    print(f"Environnement: {env}")
    print(f"Token: {api_token[:5]}...{api_token[-5:]} (masqué)")

    try:
        # Initialiser le client
        session = Session()
        session.verify = True
        # Ajouter un User-Agent de navigateur pour éviter le blocage
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        session.headers.update({'User-Agent': user_agent})

        # Transport personnalisé qui force le User-Agent sur TOUTES les requêtes
        transport = CustomTransport(user_agent=user_agent, session=session, timeout=30)

        # Plugin pour les requêtes SOAP
        user_agent_plugin = UserAgentPlugin(user_agent)

        client = Client(wsdl=wsdl_url, transport=transport, plugins=[user_agent_plugin])

        # Préparer les paramètres
        # Date depuis les 7 derniers jours
        from_date = datetime.now() - timedelta(days=7)
        from_date_str = from_date.strftime("%Y-%m-%dT%H:%M:%S")

        print(f"\n⏳ Appel API...")
        print(f"   fromDate: {from_date_str}")

        # Faire l'appel - le SOAP attend un objet imbriqué
        response = client.service.GetPlanificationsForDate(
            getPlanificationsForDate={
                'fromDate': from_date_str,
                'tokenString': api_token
            }
        )

        # Analyser la réponse
        code_retour = getattr(response, 'responseStatus', None)
        desc = getattr(response, 'responseDesc', 'N/A')
        planifs = getattr(response, 'planifications', None)

        print(f"\n✅ Réponse reçue!")
        print(f"   Code retour: {code_retour}")
        print(f"   Description: {desc}")

        # Interpréter le code de retour
        error_messages = {
            0: "OK - Succès",
            1: "Accès invalide - Vérifier les paramètres",
            2: "Accès refusé - Token invalide",
            8: "Aucune donnée pour la plage demandée (normal)",
            9: "Date invalide",
            14: "Délais minimum entre accès non respecté (5 min)",
        }

        msg = error_messages.get(code_retour, f"Code inconnu: {code_retour}")

        if code_retour == 0 or code_retour == 8:
            print(f"   ✅ {msg}")
        else:
            print(f"   ⚠️  {msg}")

        # Afficher les planifications
        if planifs:
            if not isinstance(planifs, list):
                planifs = [planifs]

            print(f"\n📊 Nombre de planifications: {len(planifs)}")

            if len(planifs) > 0:
                print(f"\nExemple de planification (première entrée):")
                p = planifs[0]

                # Debug: afficher tous les attributs disponibles
                print(f"   Type wrapper: {type(p)}")
                print(f"   Count: {getattr(p, 'count', 'N/A')}")
                print(f"   Duration: {getattr(p, 'duration', 'N/A')}")

                # Les vraies planifications sont dans l'attribut 'planification'
                inner_planifs = getattr(p, 'planification', None)
                if inner_planifs:
                    if not isinstance(inner_planifs, list):
                        inner_planifs = [inner_planifs]
                    print(f"\n   Nombre de planifications internes: {len(inner_planifs)}")
                    if len(inner_planifs) > 0:
                        ip = inner_planifs[0]
                        print(f"   Type d'entrée: {type(ip)}")
                        print(f"   Attributs disponibles: {[attr for attr in dir(ip) if not attr.startswith('_')]}")

                        # Essayer différentes variantes de noms
                        for attr_name in ['COTE_RUE_ID', 'coteRueId', 'cote_rue_id', 'CoteRueId']:
                            val = getattr(ip, attr_name, None)
                            if val is not None:
                                print(f"   {attr_name}: {val}")
                                break
                else:
                    print(f"   Aucune planification interne (normal si pas d'opération en cours)")
        else:
            print(f"\n📊 Aucune planification retournée")

        return {
            'success': code_retour in [0, 8],
            'code': code_retour,
            'count': len(planifs) if planifs else 0
        }

    except Exception as e:
        print(f"\n❌ Erreur lors de l'appel API")
        print(f"   Type: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        return {'success': False, 'error': str(e)}


def test_specific_address(api_token: str, cote_rue_id: int, use_production: bool = True) -> None:
    """Test pour une adresse spécifique.

    Args:
        api_token: Token d'authentification API
        cote_rue_id: ID du côté de rue à tester
        use_production: Utiliser l'API de production (True) ou test (False)
    """
    print(f"\n{'='*60}")
    print(f"Test 3: Recherche d'adresse spécifique")
    print(f"{'='*60}")
    print(f"COTE_RUE_ID: {cote_rue_id}")

    try:
        if use_production:
            wsdl_url = "https://servicesenligne2.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService?wsdl"
        else:
            wsdl_url = "https://servicesenlignedev.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService?wsdl"

        session = Session()
        session.verify = True
        # Ajouter un User-Agent de navigateur pour éviter le blocage
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        session.headers.update({'User-Agent': user_agent})

        # Transport personnalisé qui force le User-Agent sur TOUTES les requêtes
        transport = CustomTransport(user_agent=user_agent, session=session, timeout=30)

        # Plugin pour les requêtes SOAP
        user_agent_plugin = UserAgentPlugin(user_agent)

        client = Client(wsdl=wsdl_url, transport=transport, plugins=[user_agent_plugin])

        # Chercher dans les 30 derniers jours
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")

        print(f"⏳ Recherche...")
        response = client.service.GetPlanificationsForDate(
            getPlanificationsForDate={
                'fromDate': from_date,
                'tokenString': api_token
            }
        )

        planif_wrapper = getattr(response, 'planifications', None)

        if not planif_wrapper:
            print(f"❌ Aucune planification trouvée")
            return

        # Extract inner planifications list
        planifs = getattr(planif_wrapper, 'planification', None)
        if not planifs:
            print(f"❌ Aucune planification trouvée")
            return

        if not isinstance(planifs, list):
            planifs = [planifs]

        print(f"📊 Total de planifications: {len(planifs)}")

        # Chercher l'adresse spécifique
        found = False
        for p in planifs:
            if getattr(p, 'COTE_RUE_ID', None) == cote_rue_id:
                found = True
                print(f"\n✅ Adresse trouvée!")
                print(f"   COTE_RUE_ID: {getattr(p, 'COTE_RUE_ID', 'N/A')}")
                print(f"   ETAT_DENEIG: {getattr(p, 'ETAT_DENEIG', 'N/A')}")
                print(f"   DATE_DEB_PLANIF: {getattr(p, 'DATE_DEB_PLANIF', 'N/A')}")
                print(f"   DATE_FIN_PLANIF: {getattr(p, 'DATE_FIN_PLANIF', 'N/A')}")
                print(f"   DATE_MAJ: {getattr(p, 'DATE_MAJ', 'N/A')}")
                break

        if not found:
            print(f"\n⚠️  Adresse non trouvée dans les planifications")
            print(f"   Cela peut être normal si aucun déneigement n'est planifié")
            print(f"   Total de planifications: {len(planifs)}")

    except Exception as e:
        print(f"\n❌ Erreur: {e}")


def main():
    """Point d'entrée principal du script."""
    print("\n" + "="*60)
    print("   Test API Planif-Neige - Ville de Montréal")
    print("="*60)

    # Vérifier les arguments
    if len(sys.argv) < 2:
        print("\n❌ Usage: python3 test_api.py YOUR_API_TOKEN [COTE_RUE_ID] [--test]")
        print("\nExemple:")
        print("   python3 test_api.py aaaaa-bbbbb-ccccc-ddddd")
        print("   python3 test_api.py aaaaa-bbbbb-ccccc-ddddd 16006081")
        print("   python3 test_api.py aaaaa-bbbbb-ccccc-ddddd --test")
        print("   python3 test_api.py aaaaa-bbbbb-ccccc-ddddd 16006081 --test")
        print("\nOptions:")
        print("   --test    Utiliser l'API de test au lieu de production")
        sys.exit(1)

    api_token = sys.argv[1]

    # Déterminer si on utilise l'API de test ou production
    use_production = "--test" not in sys.argv

    # Extraire COTE_RUE_ID s'il est fourni (peut être argv[2] ou argv[3] selon si --test est présent)
    cote_rue_id = None
    for arg in sys.argv[2:]:
        if arg != "--test" and arg.isdigit():
            cote_rue_id = int(arg)
            break

    env_name = "PRODUCTION" if use_production else "TEST"
    print(f"\n🌍 Environnement: {env_name}")

    # Test 1: Charger le WSDL
    if use_production:
        wsdl_url = "https://servicesenligne2.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService?wsdl"
    else:
        wsdl_url = "https://servicesenlignedev.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService?wsdl"

    wsdl_success = test_wsdl_loading(wsdl_url)

    if not wsdl_success:
        print("\n⚠️  Le WSDL n'a pas pu être chargé.")
        print("   Le serveur est peut-être temporairement indisponible.")
        print("   Réessayez dans quelques minutes.")
        sys.exit(1)

    # Test 2: Appeler l'API
    api_result = test_api_call(api_token, use_production=use_production)

    # Test 3: Chercher une adresse spécifique (si fournie)
    if cote_rue_id and api_result.get('success'):
        test_specific_address(api_token, cote_rue_id, use_production=use_production)

    # Résumé
    print(f"\n{'='*60}")
    print("Résumé des tests")
    print(f"{'='*60}")
    print(f"✅ WSDL: {'OK' if wsdl_success else 'ÉCHEC'}")
    print(f"{'✅' if api_result.get('success') else '❌'} API: {'OK' if api_result.get('success') else 'ÉCHEC'}")

    if api_result.get('success'):
        print(f"\n🎉 Tous les tests ont réussi!")
        print(f"   Votre intégration Home Assistant devrait fonctionner.")
    else:
        print(f"\n⚠️  Certains tests ont échoué.")
        print(f"   Vérifiez votre token API ou réessayez plus tard.")

    print("\n")


if __name__ == "__main__":
    main()
