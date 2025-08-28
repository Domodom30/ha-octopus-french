"""Utils for Octopus French integration."""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from python_graphql_client import GraphqlClient

from ..const import (
    GRAPH_QL_ENDPOINT,
    SOLAR_WALLET_LEDGER,
    POT_WALLET_LEDGER,
    ELECTRICITY_LEDGER,
    GAZ_LEDGER,
    QUERY_GET_MEASUREMENTS,
    QUERY_GET_GAZ_MEASUREMENTS
)

from ..utils.logger import LOGGER

class OctopusFrench:
    def __init__(self, email, password):
        self._email = email
        self._password = password
        self._token = None
        self._token_expires_at = None

    async def login(self):
        """Login et obtention du token JWT."""
        mutation = """
           mutation obtainKrakenToken($input: ObtainJSONWebTokenInput!) {
              obtainKrakenToken(input: $input) {
                token
              }
            }
        """
        variables = {"input": {"email": self._email, "password": self._password}}

        client = GraphqlClient(endpoint=GRAPH_QL_ENDPOINT)
        response = await client.execute_async(mutation, variables)

        if "errors" in response:
            return False

        self._token = response["data"]["obtainKrakenToken"]["token"]
        # Le token expire généralement après 1 heure, on se donne une marge
        self._token_expires_at = datetime.now() + timedelta(minutes=50)
        return True

    def _is_token_expired(self):
        """Vérifie si le token est expiré ou va expirer bientôt."""
        if not self._token or not self._token_expires_at:
            return True
        return datetime.now() >= self._token_expires_at

    async def _ensure_valid_token(self):
        """S'assure que le token est valide, sinon le renouvelle."""
        if self._is_token_expired():
            success = await self.login()
            if not success:
                raise Exception("Failed to renew expired token")

    async def _execute_with_retry(self, query, variables=None):
        """Exécute une requête GraphQL avec retry en cas d'expiration du token."""
        await self._ensure_valid_token()
        
        headers = {"Authorization": f"JWT {self._token}"}
        client = GraphqlClient(endpoint=GRAPH_QL_ENDPOINT, headers=headers)
        response = await client.execute_async(query, variables)

        # Vérifier si le token a expiré
        if "errors" in response:
            token_expired = any(
                "Signature of the JWT has expired" in error.get("message", "") or
                "KT-CT-1124" in error.get("extensions", {}).get("errorCode", "")
                for error in response["errors"]
            )
            
            if token_expired:
                success = await self.login()
                if success:
                    # Retry avec le nouveau token
                    headers = {"Authorization": f"JWT {self._token}"}
                    client = GraphqlClient(endpoint=GRAPH_QL_ENDPOINT, headers=headers)
                    response = await client.execute_async(query, variables)
                else:
                    raise Exception("Failed to renew expired token during request")

        return response

    async def get_accounts(self):
        """Récupère tous les comptes de l'utilisateur."""
        query = """
            query getAccountNames {
                viewer {
                    accounts {
                        number
                        accountType
                        billingName
                    }
                }
            }
        """

        response = await self._execute_with_retry(query)

        if "errors" in response:
            return []

        accounts = response["data"]["viewer"]["accounts"]
        return accounts

    async def get_supply_points(self, account_number: str):
        """Récupère les points de livraison pour un compte avec la bonne query."""
        query = """
            query getSupplyPoints($accountNumber: String!) {
                account(accountNumber: $accountNumber) {
                    properties {
                        id
                        supplyPoints(first: 10) {
                            edges {
                                node {
                                    id
                                    externalIdentifier
                                    marketName
                                }
                            }
                        }
                    }
                }
            }
        """

        variables = {"accountNumber": account_number}
        response = await self._execute_with_retry(query, variables)

        if "errors" in response:
            return []

        supply_points = []
        for property in response["data"]["account"]["properties"]:
            property_id = property["id"]
            for edge in property["supplyPoints"]["edges"]:
                node = edge["node"]
                supply_points.append({
                    "property_id": property_id,
                    "electricity_point_id": node["id"],
                    "external_identifier": node["externalIdentifier"],
                    "market_name": node["marketName"],
                    "type": "ELECTRICITY" if "ELECTRICITY" in node["marketName"] else "GAS"
                })

        return supply_points

    async def get_primary_account_number(self):
        """Récupère le numéro du compte principal."""
        accounts = await self.get_accounts()
        
        if not accounts:
            raise Exception("Aucun compte trouvé")
        
        # Prendre le premier compte actif
        return accounts[0]["number"]

    async def get_electricity_supply_point(self, account_number: str):
        """Récupère le premier point de livraison électricité actif."""
        supply_points = await self.get_supply_points(account_number)
        
        electricity_points = [
            sp for sp in supply_points 
            if sp["type"] == "ELECTRICITY" and sp["external_identifier"]
        ]
        
        if not electricity_points:
            raise Exception("Aucun point de livraison électricité trouvé")
        
        # Prendre le premier point de livraison électricité
        return electricity_points[0]["external_identifier"]

    async def get_gas_supply_point(self, account_number: str):
        """Récupère le premier point de livraison gaz actif."""
        supply_points = await self.get_supply_points(account_number)
        
        gaz_points = [
            sp for sp in supply_points 
            if sp["type"] == "GAS" and sp["external_identifier"]
        ]
        
        if not gaz_points:
            LOGGER.warning("Aucun point de livraison de gaz trouvé")
            return None
        
        # Prendre le premier point de livraison du gaz
        return gaz_points[0]["external_identifier"]
    
    async def _get_gas_measurements(self, account_number: str, gas_point_id: str):
        """Récupère les mesures de gaz avec pagination."""
        if not gas_point_id:
            LOGGER.info("Aucun point de livraison gaz disponible")
            return {}
        
        try:
            all_edges = []
            has_next_page = True
            after_cursor = None
            
            # Récupérer toutes les pages de données
            while has_next_page:
                variables_gas = {
                    "accountNumber": account_number,
                    "first": 100,  # Maximum autorisé par l'API
                    "pceRef": gas_point_id,
                    "after": after_cursor
                }
                
                response_gas = await self._execute_with_retry(QUERY_GET_GAZ_MEASUREMENTS, variables_gas)
                
                if "errors" in response_gas:
                    LOGGER.warning("Erreur lors de la récupération des données gaz: %s", response_gas["errors"])
                    break
                
                if "data" not in response_gas or "gasReading" not in response_gas["data"]:
                    break
                
                gas_reading = response_gas["data"]["gasReading"]
                edges = gas_reading.get("edges", [])
                all_edges.extend(edges)
                
                # Vérifier s'il y a une page suivante
                page_info = gas_reading.get("pageInfo", {})
                has_next_page = page_info.get("hasNextPage", False)
                after_cursor = page_info.get("endCursor")
                
                if not has_next_page:
                    break
            
            # Traiter toutes les données récupérées
            return self._process_gas_measurements(all_edges)
                
        except Exception as err:
            LOGGER.warning("Erreur lors de la récupération des données gaz: %s", err)
            return {}

    def _process_gas_measurements(self, edges):
        """Traite les mesures de gaz à partir des edges."""
        if not edges:
            return {}
        
        monthly_data = []
        yearly_total = 0
        current_month = datetime.now().strftime("%Y-%m")
        current_month_data = {}
        
        # Regrouper par mois
        monthly_consumption = {}
        
        for edge in edges:
            node = edge["node"]
            reading_date = node.get("readingDate", "")
            
            if not reading_date:
                continue
            
            month_key = reading_date[:7]  # YYYY-MM
            consumption = float(node.get("consumption", 0))
            
            # Ajouter à la consommation mensuelle
            if month_key in monthly_consumption:
                monthly_consumption[month_key] += consumption
            else:
                monthly_consumption[month_key] = consumption
        
        # Créer les données mensuelles
        for month_key, total_consumption in monthly_consumption.items():
            month_data = {
                "month": month_key,
                "total": total_consumption
            }
            
            monthly_data.append(month_data)
            yearly_total += total_consumption
            
            # Check if this is the current month
            if month_key == current_month:
                current_month_data = month_data
        
        # Trier par date (du plus ancien au plus récent)
        monthly_data.sort(key=lambda x: x["month"])
        
        return {
            "current_month": current_month_data,
            "monthly_data": monthly_data,
            "yearly_total": yearly_total
        }

    async def account(
        self,
        account_number: str = None,
        first: int = 1000,
        reading_frequency: str = "MONTH_INTERVAL",
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        timezone: str = "Europe/Paris",
    ) -> Dict[str, Any]:
        """Récupère les mesures d'un compte."""
        
        # S'assurer que le token est valide avant de commencer
        await self._ensure_valid_token()
        
        # Si aucun numéro de compte fourni, récupère le compte principal
        if not account_number:
            account_number = await self.get_primary_account_number()

        # Récupère les points de livraison
        electricity_point_id = await self.get_electricity_supply_point(account_number)
        gas_point_id = await self.get_gas_supply_point(account_number)

        LOGGER.info("Using electricity point: %s", electricity_point_id)
        LOGGER.info("Using gas point: %s", gas_point_id)

        # Configuration pour électricité
        utility_electricity_filters = [
            {
                "electricityFilters": {
                    "readingFrequencyType": reading_frequency,
                    "marketSupplyPointId": electricity_point_id,
                }
            }
        ]

        # Set default dates if not provided
        if not start_at:
            start_at = datetime.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT00:00:00.000")
        if not end_at:
            end_at = datetime.now().strftime("%Y-%m-%dT00:00:00.000")

        # Variables pour électricité
        variables = {
            "accountNumber": account_number,
            "first": first,
            "utilityFilters": utility_electricity_filters,
            "startAt": start_at,
            "endAt": end_at,
            "timezone": timezone,
        }

        # Exécuter la requête électricité
        response = await self._execute_with_retry(QUERY_GET_MEASUREMENTS, variables)

        # Traitement des erreurs pour électricité
        if "errors" in response:
            unauthorized_errors = [
                error for error in response["errors"] 
                if "Unauthorized" in error.get("message", "") or "KT-CT-4718" in error.get("extensions", {}).get("errorCode", "")
            ]
            
            if unauthorized_errors:
                utility_electricity_filters = [{"electricityFilters": {"readingFrequencyType": reading_frequency}}]
                variables["utilityFilters"] = utility_electricity_filters
                response = await self._execute_with_retry(QUERY_GET_MEASUREMENTS, variables)
                
                if "errors" in response:
                    # Essayer avec un autre point de livraison
                    supply_points = await self.get_supply_points(account_number)
                    electricity_points = [
                        sp for sp in supply_points 
                        if sp["type"] == "ELECTRICITY" and sp["external_identifier"] != electricity_point_id
                    ]
                    
                    if electricity_points:
                        new_supply_point = electricity_points[0]["external_identifier"]
                        utility_electricity_filters = [{
                            "electricityFilters": {
                                "readingFrequencyType": reading_frequency,
                                "marketSupplyPointId": new_supply_point,
                            }
                        }]
                        variables["utilityFilters"] = utility_electricity_filters
                        response = await self._execute_with_retry(QUERY_GET_MEASUREMENTS, variables)
                        
                        if "errors" in response:
                            raise Exception(f"GraphQL error with alternative supply point: {response['errors']}")
                        electricity_point_id = new_supply_point
                    else:
                        raise Exception(f"GraphQL error after all retries: {response['errors']}")

        # Traitement des données
        ledgers = response["data"]["account"]["ledgers"]

        electricity = next((x for x in ledgers if x['ledgerType'] == ELECTRICITY_LEDGER), {'balance': 0})
        gaz = next((x for x in ledgers if x['ledgerType'] == GAZ_LEDGER), {'balance': 0})
        solar_wallet = next((x for x in ledgers if x['ledgerType'] == SOLAR_WALLET_LEDGER), {'balance': 0})
        pot_wallet = next((x for x in ledgers if x['ledgerType'] == POT_WALLET_LEDGER), {'balance': 0})

        # Traitement des mesures électricité
        electricity_measurements = self._process_electricity_measurements(response)
        
        # Traitement des mesures gaz avec pagination
        gas_measurements = await self._get_gas_measurements(account_number, gas_point_id)

        return {
            "account_number": account_number,
            "electricity_point_id": electricity_point_id,
            "gas_point_id": gas_point_id,
            "octopus_solar_wallet": float(solar_wallet.get("balance", 0)) / 100 if solar_wallet else 0,
            "octopus_electricity": float(electricity.get("balance", 0)) / 100 if electricity else 0,
            "octopus_gaz": float(gaz.get("balance", 0)) / 100 if gaz else 0,
            "octopus_pot": float(pot_wallet.get("balance", 0)) / 100 if pot_wallet else 0,
            "electricity_measurements": electricity_measurements,
            "gas_measurements": gas_measurements
        }

    def _process_electricity_measurements(self, response):
        """Traite les mesures d'électricité."""
        properties_data = []
        
        if "data" not in response or "account" not in response["data"]:
            return {}
            
        for i, property in enumerate(response["data"]["account"]["properties"]):
            property_id = property["id"]
            prop_measurements = property.get("measurements", {})
            
            # Vérifier les erreurs d'autorisation
            has_authorization_error = any(
                error for error in response.get("errors", [])
                if any(
                    path_segment == f"properties[{i}]" or 
                    path_segment == f"properties[{i}].measurements"
                    for path_segment in error.get("path", [])
                )
                and "Unauthorized" in error.get("message", "")
            )
            
            if has_authorization_error:
                continue
            
            if prop_measurements and prop_measurements.get("edges"):
                properties_data.append({
                    "property_id": property_id,
                    "utility_type": "ELECTRICITY",
                    "measurements": prop_measurements
                })

        # Process the electricity measurements data
        return self._process_measurements_data(properties_data, "ELECTRICITY")

    def _process_measurements_data(self, properties_data, utility_type):
        """Process measurements data for a specific utility type."""
        if not properties_data:
            return {}
        
        processed = {
            "current_month": {},
            "monthly_data": [],
            "yearly_total": 0,
        }
        
        # Pour l'électricité, on garde HP/HC
        if utility_type == "ELECTRICITY":
            processed["yearly_hp"] = 0
            processed["yearly_hc"] = 0
        
        current_month = datetime.now().strftime("%Y-%m")
        
        for property_data in properties_data:
            measurements_data = property_data.get("measurements", {})
            if not measurements_data or not measurements_data.get("edges"):
                continue
            
            for edge in measurements_data["edges"]:
                node = edge["node"]
                start_date = node.get("startAt", "")
                
                if not start_date:
                    continue
                
                month_key = start_date[:7]  # YYYY-MM
                total_value = float(node.get("value", 0))
                
                month_data = {
                    "month": month_key,
                    "total": total_value,
                    "start_date": start_date,
                    "end_date": node.get("endAt", ""),
                    "property_id": property_data["property_id"],
                    "utility_type": utility_type
                }
                
                # Pour l'électricité, extraire HP et HC
                if utility_type == "ELECTRICITY":
                    hp_value = 0
                    hc_value = 0
                    
                    for stat in node.get("metaData", {}).get("statistics", []):
                        if stat.get("label") == "HP" and stat.get("value"):
                            hp_value = float(stat["value"])
                        elif stat.get("label") == "HC" and stat.get("value"):
                            hc_value = float(stat["value"])
                    
                    month_data["hp"] = hp_value
                    month_data["hc"] = hc_value
                    processed["yearly_hp"] += hp_value
                    processed["yearly_hc"] += hc_value
                
                processed["monthly_data"].append(month_data)
                processed["yearly_total"] += total_value
                
                # Check if this is the current month
                if month_key == current_month:
                    processed["current_month"] = month_data
        
        # Sort monthly data by date
        processed["monthly_data"].sort(key=lambda x: x["month"])
        
        return processed