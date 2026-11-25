# Dictionnaire des données — Territorial Pulse

Tableau panel mensuel couvrant les **8 préfectures et provinces** de la région **Tanger-Tétouan-Al Hoceïma** d'après le découpage administratif officiel, de **janvier 2019 à octobre 2025** (`82` mois × `8` territoires = `656` observations).

## Clés primaires
| Colonne | Type | Description |
| :--- | :--- | :--- |
| `province_id` | `STRING` | Identifiant unique harmonisé (`TTA-01` à `TTA-08`). |
| `date` | `DATE` | Premier jour du mois (`YYYY-MM-01`). |
| `province_name` | `STRING` | Nom officiel de la préfecture ou province. |
| `province_type` | `STRING` | Statut administratif (`Préfecture` ou `Province`). |

## Variables brutes et sources
| Colonne | Unité | Source | Rôle |
| :--- | :--- | :--- | :--- |
| `nightlights_mean` | `nW/cm²/sr` | NASA Black Marble / EOG VIIRS | Radiance nocturne moyenne mensuelle (corrigée nuages). |
| `nightlights_sum` | `nW/cm²/sr` | NASA Black Marble / EOG VIIRS | Somme zonale de radiance nocturne. |
| `cloud_free_pct` | `%` | Indicateur qualité VIIRS | Pourcentage d'observations mensuelles sans couverture nuageuse. |
| `hcp_employment_index` | `0-100` | HCP (Enquêtes emploi / annuaires) | Indice d'emploi et d'activité formelle de référence. |
| `hcp_unemployment_rate` | `%` | HCP | Taux de chômage provincial estimé. |
| `hcp_activity_rate` | `%` | HCP | Taux d'activité de la population en âge de travailler. |
| `population_est` | `habitants` | HCP / RGPH | Population estimée interpolée mensuellement. |
| `business_creations` | `nombre/mois` | OMPIC | Créations nettes d'entreprises par mois. |
| `tourism_nights` | `nuitées/mois` | Observatoire du Tourisme | Nuitées enregistrées dans les établissements classés. |
| `port_traffic_kt` | `milliers t/mois` | Autorité Portuaire (Tanger Med / ports) | Volume portuaire et logistique mensuel. |
| `web_trends_index` | `0-100` | Google Trends (`pytrends`) | Signal de recherche emploi, immobilier et hôtellerie. |
| `job_offers_count` | `nombre/mois` | Portails d'offres d'emploi (agrégé) | Volume d'offres d'emploi publiées par territoire. |

## Variables désaisonnalisées et modélisées
| Colonne | Plage | Description |
| :--- | :--- | :--- |
| `nightlights_sa` | `0-100` | Score normalisé désaisonnalisé de luminosité nocturne. |
| `employment_idx` | `0-100` | Score composite normalisé emploi HCP + offres d'emploi. |
| `business_creations_sa` | `0-100` | Score normalisé désaisonnalisé de créations d'entreprises. |
| `tourism_nights_sa` | `0-100` | Score normalisé désaisonnalisé de nuitées touristiques. |
| `port_traffic_sa` | `0-100` | Score normalisé désaisonnalisé de trafic portuaire. |
| `web_trends_sa` | `0-100` | Score normalisé désaisonnalisé de recherches web. |
| `tpi_score` | `0-100` | **Territorial Pulse Index (TPI)** — baromètre composite pondéré. |
| `tpi_pca_score` | `0-100` | Indice alternatif issu de la 1re composante principale (ACP) pour validation de sensibilité. |
| `tpi_rank` | `1-8` | Classement mensuel du territoire dans la région (`1` = plus dynamique). |
| `cluster_label` | `STRING` | Typologie K-Means (`Moteur`, `En transition`, `Fragile`). |
