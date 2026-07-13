import requests
import json

# Désactive les avertissements SSL (pour certificats auto-signés Aruba CX)
requests.packages.urllib3.disable_warnings()


class ArubaCXAPIClient:
    def __init__(self, ip, username, password, api_version="v10.11"):
        self.ip = ip
        self.username = username
        self.password = password
        self.api_version = api_version
        self.base_url = f"https://{self.ip}/rest/{self.api_version}"
        self.session = requests.Session()
        self.logged_in = False

    def login(self):
        """Se connecte au switch via REST API et obtient le cookie de session."""
        login_url = f"{self.base_url}/login"
        try:
            response = self.session.post(
                login_url,
                params={"username": self.username, "password": self.password},
                verify=False,
                timeout=5
            )
            if response.status_code == 200:
                print(f"✅ [LOGIN] Connexion réussie à {self.ip}")
                self.logged_in = True
                return True
            else:
                print(f"🚨 [LOGIN] Échec connexion ({response.status_code}): {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"🚨 [LOGIN] Erreur réseau vers {self.ip}: {e}")
            return False

    def get_system_info(self):
        return self._get_endpoint("/system", "system")

    def get_interfaces(self):
        return self._get_endpoint("/system/interfaces", "interfaces")

    def get_transceivers(self):
        return self._get_endpoint("/system/interfaces/transceivers", "transceivers")


    def get_interfaces_details(self):
        """
        Va d'abord chercher la liste des interfaces pour obtenir les URIs,
        puis fait un GET sur chaque URI pour récupérer les détails complets.
        Retourne une liste d'objets JSON.
        """
        if not self.logged_in:
            print(f"🚨 [GET interfaces] Non connecté à {self.ip}")
            return []

        url_list = f"{self.base_url}/system/interfaces"
        try:
            response = self.session.get(url_list, verify=False, timeout=5)
            if response.status_code != 200:
                print(f"🚨 [GET interfaces] Erreur {response.status_code}: {response.text}")
                return []

            interface_refs = response.json()  # ça donne ton dict { "1/1/1": "/rest/v10.11/..." }
            detailed_interfaces = []

            # Pour chaque interface, aller chercher les détails
            for intf_name, uri in interface_refs.items():
                full_url = f"https://{self.ip}{uri}"
                resp_intf = self.session.get(full_url, verify=False, timeout=5)
                if resp_intf.status_code == 200:
                    detailed_interfaces.append(resp_intf.json())
                else:
                    print(f"⚠️ [GET interface {intf_name}] {resp_intf.status_code}")

            print(f"✅ [GET interfaces details] {len(detailed_interfaces)} interfaces récupérées depuis {self.ip}")
            return detailed_interfaces

        except requests.exceptions.RequestException as e:
            print(f"🚨 [GET interfaces] Erreur réseau vers {self.ip}: {e}")
            return []





    


    def logout(self):
        """Termine la session proprement."""
        if not self.logged_in:
            return
        logout_url = f"{self.base_url}/logout"
        try:
            self.session.post(logout_url, verify=False, timeout=5)
            print(f"👋 [LOGOUT] Déconnexion réussie de {self.ip}")
        except requests.exceptions.RequestException as e:
            print(f"⚠️ [LOGOUT] Erreur lors de la déconnexion: {e}")
        finally:
            self.logged_in = False

            
    def _get_endpoint(self, path, label):
        """Méthode interne pour factoriser les GET"""
        if not self.logged_in:
            print(f"🚨 [GET {label}] Non connecté à {self.ip}")
            return None
        url = f"{self.base_url}{path}"
        try:
            response = self.session.get(url, verify=False, timeout=5)
            if response.status_code == 200:
                print(f"✅ [GET {label}] Données récupérées sur {self.ip}")
                return response.json()
            else:
                print(f"🚨 [GET {label}] Erreur {response.status_code}: {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"🚨 [GET {label}] Erreur réseau vers {self.ip}: {e}")
            return None
