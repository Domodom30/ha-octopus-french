import requests

class OctopusFrenchAPI:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.token = None

    def login(self):
        query = """
        mutation Login($email: String!, $password: String!) {
          obtainKrakenToken(input: {email: $email, password: $password}) {
            token
          }
        }
        """
        resp = requests.post(
            "https://api.oefr-kraken.energy/v1/graphql/",
            json={"query": query, "variables": {"email": self.username, "password": self.password}},
        )
        data = resp.json()
        self.token = data["data"]["obtainKrakenToken"]["token"]
        return self.token

    def _request(self, query, variables=None):
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = requests.post(
            "https://api.oefr-kraken.energy/v1/graphql/",
            json={"query": query, "variables": variables or {}},
            headers=headers,
        )
        return resp.json()

    def accounts_ledgers(self):
        query = """
        query {
          viewer {
            accounts {
              number
              ledgers {
                ledgerType
                balance
              }
            }
          }
        }
        """
        return self._request(query)

    def consumption(self, account_number, fuel_type="ELECTRICITY"):
        query = """
        query($accountNumber: String!, $fuelType: FuelType!) {
          accountConsumption(accountNumber: $accountNumber, fuelType: $fuelType) {
            consumption {
              startAt
              endAt
              consumption
              unit
            }
          }
        }
        """
        return self._request(query, {"accountNumber": account_number, "fuelType": fuel_type})
