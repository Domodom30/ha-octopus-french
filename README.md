Copiez l'URL du dépôt[](https://github.com/Domodom30/ha-octopus-french), sélectionnez _Intégration_ comme catégorie, puis cliquez sur _Ajouter_.

## Configuration

Une fois installé, allez dans _Appareils et services -> Ajouter une intégration_ et recherchez _Octopus_.

L'assistant vous demandera votre email et votre mot de passe pour [Octopus Energy](https://octopusenergy.fr/).

## Entités
Une fois le composant configuré, vous aurez deux entités pour chaque compte associé à votre email (généralement un seul).

### Solar Wallet
L'entité Solar Wallet affiche la valeur actuelle de votre Solar Wallet. Cette valeur (en euros) est mise à jour en fonction de votre dernière facture. Actuellement, il n'est pas possible de consulter cette valeur en temps réel.

## Octopus Credit
L'entité Octopus Credit affiche la valeur actuelle de votre crédit Octopus obtenu grâce à des parrainages ou d'autres éventuelles bonifications.

### Dernière facture
Cette entité affiche le coût de votre dernière facture.

De plus, dans les attributs, vous trouverez les dates d'émission de cette facture ainsi que la période (début et fin) correspondante.

## Utilisation

Vous pourrez utiliser ces entités pour visualiser l'état ou créer des automatisations, par exemple, pour être informé lorsqu'un changement se produit dans l'attribut "Émise" de la dernière facture.

Une manière de représenter les données serait la suivante :

```yaml
title: Octopus Spain
type: entities
entities:
  - entity: sensor.ultima_factura_octopus
  - entity: sensor.solar_wallet
  - entity: sensor.octopus_credit
  - type: attribute
    entity: sensor.ultima_factura_octopus
    name: Début
    icon: mdi:calendar-start
    attribute: Début
  - type: attribute
    entity: sensor.ultima_factura_octopus
    name: Fin
    icon: mdi:calendar-end
    attribute: Fin
  - type: attribute
    entity: sensor.ultima_factura_octopus
    name: Émise
    icon: mdi:email-fast-outline
    attribute: Émise