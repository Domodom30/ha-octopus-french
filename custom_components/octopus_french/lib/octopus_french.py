"""Octopus Energy France – Client avec login JWT + getMeasurements."""
from __future__ import annotations

import uuid
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
from ..utils.logger import LOGGER

import aiohttp


GRAPH_QL_ENDPOINT = "https://api.oefr-kraken.energy/v1/graphql/"

MUTATION_LOGIN = """
mutation obtainKrakenToken($input: ObtainJSONWebTokenInput!) {
  obtainKrakenToken(input: $input) {
    token
  }
}
"""

QUERY_ACCOUNTS = """
query {
  viewer {
    accounts { number }
  }
}
"""

QUERY_GET_MEASUREMENTS = """
query getMeasurements(
  $accountNumber: String!,
  $first: Int!,
  $utilityFilters: [UtilityFiltersInput!],
  $startOn: Date,
  $endOn: Date,
  $startAt: DateTime,
  $endAt: DateTime,
  $timezone: String,
  $cursor: String
) {
  account(accountNumber: $accountNumber) {
    number
    properties {
      id
      address
      postcode
      splitAddress
      measurements(
        first: $first,
        utilityFilters: $utilityFilters,
        startOn: $startOn,
        endOn: $endOn,
        startAt: $startAt,
        endAt: $endAt,
        timezone: $timezone,
        after: $cursor
      ) {
        edges {
          node {
            value
            unit
            ... on IntervalMeasurementType {
              startAt
              endAt
            }
            metaData {
              statistics {
                label
                type
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""


class OctopusFrench:
    """Client Kraken FR: login email+password -> JWT, puis requêtes GraphQL auth."""

    def __init__(self, email: str, password: str, session: Optional[aiohttp.ClientSession] = None):
        self._email = email
        self._password = password
        self._token: Optional[str] = None
        self._session = session
        self._own_session = False
        self._corr_id = uuid.uuid4().hex[:8]

    # ---------- Helpers ----------
    def _mask_email(self, email: str) -> str:
        try:
            user, domain = email.split("@", 1)
            if len(user) <= 2:
                user_masked = (user[0] + "…") if user else "…"
            else:
                user_masked = user[0] + "…" + user[-1]
            return f"{user_masked}@{domain}"
        except Exception:
            return "email-masqué"

    def _token_preview(self, token: str, keep: int = 6) -> str:
        if not token:
            return "∅"
        return f"{token[:keep]}…{token[-keep:]} (len={len(token)})"

    @contextmanager
    def _log_step(self, step: str, **meta):
        meta_str = " ".join([f"{k}={v}" for k, v in meta.items()]) if meta else ""
        LOGGER.debug("[OctopusFR][%s] ▶️ %s %s", self._corr_id, step, meta_str)
        t0 = time.monotonic()
        try:
            yield
            dt = time.monotonic() - t0
            LOGGER.debug("[OctopusFR][%s] ✅ %s (%.3fs)", self._corr_id, step, dt)
        except Exception:
            dt = time.monotonic() - t0
            LOGGER.exception("[OctopusFR][%s] 💥 %s a échoué (%.3fs)", self._corr_id, step, dt)
            raise

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self):
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    # ---------- Auth ----------
    async def login(self) -> bool:
        variables = {"input": {"email": self._email, "password": self._password}}
        headers = {"Content-Type": "application/json"}

        masked = self._mask_email(self._email)
        with self._log_step("login", user=masked):
            sess = await self._get_session()
            async with sess.post(
                GRAPH_QL_ENDPOINT, json={"query": MUTATION_LOGIN, "variables": variables}, headers=headers
            ) as resp:
                data = await resp.json()

        if "errors" in data:
            LOGGER.warning("[OctopusFR][%s] Login refusé: %s", self._corr_id, data["errors"])
            self._token = None
            return False

        try:
            self._token = data["data"]["obtainKrakenToken"]["token"]
            LOGGER.info("[OctopusFR][%s] Login OK (token=%s)", self._corr_id, self._token_preview(self._token))
            return True
        except Exception:
            LOGGER.error("[OctopusFR][%s] Réponse login invalide: %s", self._corr_id, data)
            self._token = None
            return False

    async def _post_graphql(self, query: str, variables: Optional[Dict[str, Any]] = None, *, retry_on_auth=True) -> Dict[str, Any]:
        if not self._token:
            ok = await self.login()
            if not ok:
                raise Exception("Échec login: pas de token")

        headers = {
            "Authorization": f"JWT {self._token}",
            "Content-Type": "application/json",
        }

        sess = await self._get_session()
        async with sess.post(GRAPH_QL_ENDPOINT, json={"query": query, "variables": variables}, headers=headers) as resp:
            data = await resp.json()

        if "errors" in data:
            auth_error = any(
                (e.get("extensions", {}) or {}).get("errorType") == "AUTHORIZATION" or
                "Unauthorized" in (e.get("message") or "")
                for e in data.get("errors", [])
            )
            if auth_error and retry_on_auth:
                LOGGER.info("[OctopusFR][%s] Auth échouée, on retente un login…", self._corr_id)
                if await self.login():
                    return await self._post_graphql(query, variables, retry_on_auth=False)
            LOGGER.error("[OctopusFR][%s] Erreurs GraphQL: %s", self._corr_id, data["errors"])
            raise Exception(f"GraphQL error: {data['errors']}")

        return data.get("data", {})

    # ---------- API ----------
    async def accounts(self) -> List[Dict[str, Any]]:
        """Liste des comptes accessibles avec compteurs électriques et gaz."""
        data = await self._post_graphql(QUERY_ACCOUNTS)
        raw_accounts = data.get("viewer", {}).get("accounts", [])

        results = []
        for acc in raw_accounts:
            acc_number = acc.get("number")
            if not acc_number:
                continue

            # On récupère les mesures pour détecter les compteurs
            acc_data = await self.get_measurements(acc_number, first=1)
            meters = {"electricity": [], "gas": []}

            properties = acc_data.get("properties", [])
            for prop in properties:
                measurements = prop.get("measurements", {}).get("edges", [])
                for m in measurements:
                    node = m.get("node", {})
                    unit = node.get("unit")
                    if unit == "kWh":
                        meters["electricity"].append(prop.get("id"))
                    elif unit == "m³":
                        meters["gas"].append(prop.get("id"))

            results.append({
                "number": acc_number,
                "meters": meters
            })

        return results

    async def get_measurements(
        self,
        account_number: str,
        *,
        first: int = 1000,
        meter_id: Optional[str] = None,
        reading_frequency: str = "MONTH_INTERVAL",
        start_on: Optional[str] = None,
        end_on: Optional[str] = None,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        timezone: str = "Europe/Paris",
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Récupère les mesures d'un compte (consommation & métadonnées) via getMeasurements."""
        utility_filters = [
            {
                "electricityFilters": {
                    "readingFrequencyType": reading_frequency,
                    **({"marketSupplyPointId": meter_id} if meter_id else {})
                }
            }
        ]

        variables = {
            "accountNumber": account_number,
            "first": first,
            "utilityFilters": utility_filters,
            "startOn": start_on,
            "endOn": end_on,
            "startAt": start_at,
            "endAt": end_at,
            "timezone": timezone,
            "cursor": cursor,
        }

        data = await self._post_graphql(QUERY_GET_MEASUREMENTS, variables)
        return data.get("account", {})
