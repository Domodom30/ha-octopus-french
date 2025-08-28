"""Constants for Octopus French integration."""

from datetime import datetime, timedelta
from typing import Final

DOMAIN = "octopus_french"
PACKAGE_NAME = "custom_components.octopus_french"
ATTRIBUTION = "Data provided by Octopus Energy French"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"

GRAPH_QL_ENDPOINT = "https://api.oefr-kraken.energy/v1/graphql/"
SOLAR_WALLET_LEDGER = "SOLAR_WALLET_LEDGER"
POT_WALLET_LEDGER = "POT_LEDGER"
ELECTRICITY_LEDGER = "FRA_ELECTRICITY_LEDGER"
GAZ_LEDGER = "FRA_GAS_LEDGER"

# Facteur de conversion gaz m³ -> kWh (valeur pour Lyon)
GAS_CONVERSION_FACTOR = 11.29

QUERY_GET_MEASUREMENTS = """
query getMeasurements($accountNumber: String!, $first: Int!, $utilityFilters: [UtilityFiltersInput!], $startAt: DateTime, $endAt: DateTime, $timezone: String) {
  account(accountNumber: $accountNumber) {
    properties {
      id
      measurements(
        first: $first
        utilityFilters: $utilityFilters
        startAt: $startAt
        endAt: $endAt
        timezone: $timezone
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
                value
                label
                type
              }
            }
          }
        }
      }
    }
    ledgers {
      ledgerType
      name
      number
      balance
    }
  }
}
"""

QUERY_GET_GAZ_MEASUREMENTS = """
query getMeasurements($accountNumber: String!, $first: Int!, $pceRef: String!, $after: String) {
  account(accountNumber: $accountNumber) {
    id
  }
  gasReading(accountNumber: $accountNumber, pceRef: $pceRef, first: $first, after: $after) {
    edges {
      node {
        consumption
        readingDate
        indexStartValue
        indexEndValue
        statusProcessed
        readingType
        energyQualification
      }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

SCAN_INTERVAL = timedelta(hours=1)