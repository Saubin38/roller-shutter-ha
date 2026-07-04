# Roller Shutter API — intégration Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/VOTRE_USER/rollershutter-api-ha)

Intègre des volets roulants pilotés par une API Spring Boot maison
(`RollerShutterActionController`) dans Home Assistant, sous forme
d'entités `cover.*` natives : ouvrir / fermer / stop / position précise (%),
plus deux services personnalisés (aération, position intermédiaire).

## Installation via HACS

1. Dans Home Assistant : `HACS → Intégrations → ⋮ → Dépôts personnalisés`
2. Colle l'URL de ce repo, catégorie **Intégration**, clique sur **Ajouter**
3. Recherche "Roller Shutter API" dans HACS et installe-la
4. Redémarre Home Assistant

## Installation manuelle

Copie le dossier `custom_components/rollershutter_api/` de ce repo vers
`<config_homeassistant>/custom_components/rollershutter_api/`, puis
redémarre Home Assistant.

## Configuration

Tout se fait dans `configuration.yaml`, sous la clé `cover` :

```yaml
cover:
  - platform: rollershutter_api
    host: 192.168.1.50
    port: 8080
    api_key: "TA_CLE_API_ICI"
    ssl: false
    scan_interval: 30
```

| Paramètre       | Obligatoire | Défaut               | Description                                             |
|-----------------|:-----------:|-----------------------|------------------------------------------------------------|
| `host`          | oui         | —                      | IP ou nom d'hôte du serveur exposant l'API                 |
| `api_key`       | oui         | —                      | Clé API envoyée dans le header `X-API-KEY`                 |
| `port`          | non         | `8080`                 | Port du serveur                                             |
| `ssl`           | non         | `false`                | `true` pour interroger l'API en HTTPS                       |
| `api_path`      | non         | `/api/rhollershutter`  | Chemin de base de l'API (si tu le changes côté Spring)      |
| `scan_interval` | non         | `30`                   | Fréquence (secondes) de rafraîchissement de l'état          |

Après redémarrage, un `cover.<nom>` est créé automatiquement pour
**chaque volet renvoyé par `GET /all`** — pas de déclaration manuelle
volet par volet.

## Fonctionnement

- **Ouvrir / Fermer / Stop** → mappés sur `open`, `close`, `stop`.
- **Curseur de position (0–100 %)** → mappé sur `closePercent`, avec
  conversion automatique (HA : `100 = ouvert` ↔ API : `100 = fermé`).
- **Aérer** / **Position intermédiaire** → services
  `rollershutter_api.airing` et `rollershutter_api.intermediate_position`,
  utilisables dans une automatisation :

```yaml
action:
  - service: rollershutter_api.airing
    target:
      entity_id: cover.chambre
```

## Authentification

Chaque requête envoie le header `X-API-KEY: <clé configurée>`. Si ton
`RollerShutterActionController` attend un autre mécanisme, adapte
`API_KEY_HEADER` dans `const.py` ou la méthode `_headers` dans `api.py`.

## Publier une nouvelle version (pour le mainteneur du repo)

HACS suit les **releases GitHub taguées**, pas la branche `main` :

```bash
git add .
git commit -m "Description des changements"
git push
git tag X.Y.Z
git push origin X.Y.Z
```

Puis sur GitHub : **Releases → Draft a new release**, sélectionne le tag,
publie. Pense à mettre à jour le champ `version` dans `manifest.json`
pour qu'il corresponde au tag.

## Dépannage

- Les entités n'apparaissent pas → vérifie les logs
  (`Réglages → Système → Journaux`, filtrer sur `rollershutter_api`).
- Une entité reste "indisponible" → son `name` n'est plus renvoyé par
  `GET /all` côté API.
