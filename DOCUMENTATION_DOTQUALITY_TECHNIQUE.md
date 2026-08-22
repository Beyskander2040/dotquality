# DotQuality — Documentation technique

**Architecture, modules, sécurité et état du code.**
Complément technique au document fonctionnel — destiné à une audience technique ou
à répondre aux questions de due diligence pendant/après un pitch.

Statut : premier prototype générique, mono-secteur/mono-société, 63 tests
automatisés (0 échec).

---

## Sommaire

1. [Stack et principes d'architecture](#1-stack-et-principes-darchitecture)
2. [Modules custom](#2-modules-custom)
3. [Modèles de données clés](#3-modèles-de-données-clés)
4. [Interface et navigation](#4-interface-et-navigation)
5. [Sécurité et rôles](#5-sécurité-et-rôles)
6. [Qualité du code](#6-qualité-du-code)
7. [Modules OCA disponibles mais non branchés](#7-modules-oca-disponibles-mais-non-branchés)
8. [Dette technique connue](#8-dette-technique-connue)
9. [Ce qu'il faut construire pour la configurabilité multi-secteurs](#9-ce-quil-faut-construire-pour-la-configurabilité-multi-secteurs)
10. [Cartographie complète de la navigation](#10-cartographie-complète-de-la-navigation)
11. [Glossaire](#11-glossaire)

---

## 1. Stack et principes d'architecture

- **Odoo 17 Community**, auto-hébergé (conteneurs Docker `odoo_qms_web` +
  `odoo_qms_db`).
- Suite OCA **"management-system"** (`mgmtsystem*`) : partiellement installée et
  intégrée, partiellement installée mais non exploitée (section 7).
- Modules custom sous `addons/management-system/`.

**Principe d'extension systématique** : un module de base définit des points
d'extension (dictionnaires de clés → domaines/comptages/actions, méthodes conçues
pour être surchargées), et chaque module qui en dépend les complète via héritage
Odoo (`_inherit`) sans jamais modifier le fichier du module de base. Ce pattern est
utilisé de façon identique par `smq_quality_bridge` (pour intégrer les moteurs OCA),
`smq_organization` et `smq_referential` — c'est le même mécanisme qui permettra
demain de brancher des modules sectoriels sans toucher au cœur.

**Principe de non-fabrication de données** : toute donnée affichée (compteur, KPI,
tendance) est soit calculée depuis un enregistrement réel, soit explicitement
absente ("À venir"). Aucune valeur simulée n'est présentée comme réelle.

---

## 2. Modules custom

| Module | Rôle | Dépendances | Application Odoo |
|---|---|---|---|
| `smq_quality` | Cœur : processus, tableau de bord OWL, sidebar custom, sécurité commune | `mail` | Oui (`application: True`) |
| `smq_document` | Documents maîtrisés et versions contrôlées | `smq_quality` | Non |
| `smq_quality_bridge` | Intègre non-conformité/action/audit OCA au SMQ | `smq_quality`, `smq_document`, `mgmtsystem_nonconformity`, `mgmtsystem_action`, `mgmtsystem_action_efficacy`, `mgmtsystem_audit` | Non |
| `smq_organization` | Sites, activités, parties intéressées, périmètre | `smq_quality`, `hr` | Non |
| `smq_referential` | Référentiels, exigences, matrice de conformité | `smq_quality`, `smq_document` | Non |

Seul `smq_quality` est déclaré comme application (point d'entrée dans le sélecteur
d'apps Odoo) ; les autres modules s'y greffent.

---

## 3. Modèles de données clés

### `smq_quality`
- `smq.process` — code (unique par société), nom, description, responsable
  (`res.users`), catégorie, statut (brouillon/actif/archivé), hérite
  `mail.thread` + `mail.activity.mixin`.
- `smq.process.category` — référentiel simple (nom, séquence).
- `smq.dashboard.tile` — support du tableau de bord : `kind` (module/kpi),
  `count` calculé (`_compute_count`, non stocké), `action_xmlid`. Points
  d'extension : `_COUNTERS`, `_KPI_MODEL_BY_KEY`, `_UPGRADED_ACTIONS`,
  `_KPI_ACTION_XMLIDS`, `_FUTURE_MODULES`.
- `smq.coming.soon` — modèle technique vide, sert uniquement de `res_model` aux
  actions "à venir" tant qu'aucun vrai modèle n'existe.

### `smq_document`
- `smq.document` — identité du document (code, type, processus, responsable,
  confidentialité, périodicité de révision), champs calculés dérivés de la version
  active (`stage_id`, `current_version_id`, `next_review_date`...).
- `smq.document.version` — moteur d'état réel :
  `draft → in_validation → approved → published → effective → obsolete`. Verrous :
  écriture directe de `state` bloquée hors méthodes de workflow, champs clés
  verrouillés dès la sortie de `draft`, pièce jointe obligatoire pour soumettre,
  motif de changement obligatoire à partir de la version 2.
- `smq.document.type`, `smq.document.stage` — configuration.
- Deux wizards (`TransientModel`) pour le rejet et la mise en vigueur avec date.

### `smq_quality_bridge`
- Étend `mgmtsystem.nonconformity` : lien processus/documents, priorité, impact,
  analyse de cause, méthode d'analyse, workflow SMQ
  (`analyse → traitement → résolue → clôturée`) avec contrôles serveur
  (`_check_user_can`) sur chaque transition — pas seulement un masquage de bouton.
- Étend `mgmtsystem.action` (+ `mgmtsystem_action_efficacy`) : `efficacy_result`
  calculé (effective/partielle/inefficace).
- Étend `mgmtsystem.audit` : lien processus/documents, compteurs de
  non-conformités/opportunités d'amélioration.
- Étend `smq.process` et `smq.document` : boutons statistiques vers
  non-conformités/audits liés.
- Étend `smq.dashboard.tile` : KPI réels (non-conformités ouvertes, actions en
  retard, audits à venir), tendance des non-conformités sur 6 mois.

### `smq_organization`
- `smq.site`, `smq.activity`, `smq.stakeholder` (catégorie, attentes, niveau
  d'influence), `smq.scope` (agrège sites/activités/processus).
- Étend `smq.process` : `site_id`, `department_id` (réutilise `hr.department`
  natif, pas de modèle recréé), `smq_activity_ids`.

### `smq_referential`
- `smq.referential` — référentiel normatif générique (code, version, organisme
  émetteur).
- `smq.referential.requirement` — exigence hiérarchique (`parent_id`/`child_ids`,
  `complete_name` calculé récursivement).
- `smq.compliance.line` — la matrice de conformité : exigence × processus
  (optionnel) → applicabilité, état, preuves (`smq.document` ou pièces jointes),
  écart, date/responsable d'évaluation. Contrainte d'unicité SQL **et** Python
  (la contrainte SQL seule ne détecte pas les doublons quand `process_id` est
  vide, car Postgres ne compare jamais deux `NULL` comme égaux).

---

## 4. Interface et navigation

- **Sidebar custom** (`SmqSidebar`, composant OWL2) injectée dans le WebClient via
  `patch()` — mécanisme officiel Odoo, pas une modification du cœur. Visible
  uniquement dans le contexte de l'app SMQ (`menuService.getCurrentApp().xmlid`).
  - Navigation en accordéon : chaque module affiche ses sous-modules uniquement au
    clic (état `expandedGroups`), tous repliés par défaut.
  - Sectionnement visuel (Qualité / Amélioration & Parties prenantes /
    Administration) via un simple attribut `sectionLabel` sur le premier groupe de
    chaque section — pas de restructuration de données, juste un séparateur visuel.
  - Repliable en mode icônes (état persisté en `localStorage`), logo DotQuality
    affiché en version complète ou en icône seule selon l'état.
  - Réactivité à l'app active gérée via l'événement bus `MENUS:APP-CHANGED` (le
    même mécanisme que `NavBar` utilise en interne).
- **Tableau de bord** (`SmqDashboard`, composant OWL2, `ir.actions.client`) :
  Quality Health Score, KPI avec tendance, watchlist, "Mes tâches", chaîne qualité,
  tendance NC, grille de modules par catégorie, actions rapides regroupées en
  menu déroulant natif Odoo (`Dropdown`/`DropdownItem`).
- **Navbar Odoo** recolorée dans le contexte SMQ uniquement
  (`body.o_smq_app_active`) : les couleurs de la navbar Odoo sont exposées comme
  variables CSS avec valeur de repli (`var(--NavBar-entry-color, ...)`) mais jamais
  définies nativement — les redéfinir au niveau du `body` suffit à toute la navbar
  sans surcharger chaque sélecteur interne.

---

## 5. Sécurité et rôles

Catégorie de module dédiée "SMQ", 6 groupes hiérarchiques (chaque groupe implique
le précédent via `implied_ids`) :

1. `group_smq_employee` — lecture sur la quasi-totalité des modèles SMQ.
2. `group_smq_writer` — création/modification de documents et non-conformités en
   brouillon.
3. `group_smq_verifier` — validation/rejet de version de document, démarrage
   d'analyse de non-conformité.
4. `group_smq_quality_manager` — publication, mise en vigueur, clôture, CRUD complet
   sur référentiels/scope/parties intéressées.
5. `group_smq_direction` — niveau hiérarchique, pas encore de droits fonctionnels
   distincts.
6. `group_smq_admin` — configuration (catégories, types, statuts, référentiels de
   non-conformité, sites, activités) ; seul groupe pré-affecté à un utilisateur
   (`base.user_admin`) dans les données du module.

Chaque transition de workflow sensible est vérifiée **côté serveur**
(`_check_user_can()` ou équivalent), en plus du masquage de bouton côté vue — un
appel API ou un import direct ne peut pas contourner la règle.

---

## 6. Qualité du code

| Module | Tests automatisés |
|---|---|
| `smq_quality` | 23 |
| `smq_document` | 21 |
| `smq_quality_bridge` | 25 |
| `smq_organization` | 6 |
| `smq_referential` | 6 |
| **Total** | **63** (0 échec, 0 erreur) |

Les tests couvrent notamment : unicité des codes, statuts par défaut, workflow
documentaire complet (soumission → validation → publication → mise en vigueur),
verrouillage des champs post-brouillon, obligation de pièce jointe, contrôle de
groupe sur les actions sensibles, calcul des KPI et de la tendance sur données
réelles, génération de la matrice de conformité, détection des doublons de lignes
de conformité (y compris le cas non couvert par la contrainte SQL seule).

---

## 7. Modules OCA disponibles mais non branchés

Constat d'audit : plusieurs modules de la suite OCA "management-system" sont déjà
installés dans l'environnement mais vivent comme une application Odoo séparée
("Système de gestion"), avec ses propres groupes de sécurité, invisible depuis la
sidebar SMQ, et **zéro donnée en base**.

| Module OCA | Modèles apportés | Limite identifiée |
|---|---|---|
| `mgmtsystem_hazard` + `mgmtsystem_hazard_risk` | `mgmtsystem.hazard`, échelles probabilité/sévérité/usage paramétrables, criticité calculée (formule configurable par société), mesures de maîtrise, risque résiduel | 100 % orienté santé-sécurité (vocabulaire "danger", sévérité formulée en blessure/décès, catégories Physical/Chemical/Fire/Environment) — aucun champ de polarité, aucune notion d'opportunité. Généraliser ce modèle est structurellement plus proche d'une réécriture que d'un bridge simple. |
| `mgmtsystem_review` (+ `mgmtsystem_review_survey`) | `mgmtsystem.review` (participants, politique, changements, conclusion, séquence, rapport PDF), `mgmtsystem.review.line` (lien NC/action existant + décision) | Aucun ordre du jour structuré, aucun lien audit/KPI/risque, workflow binaire (ouvert/clôturé), pas de champ "prochaine revue". |
| `mgmtsystem_partner` | Ajoute uniquement une valeur `"quality"` au champ `type` natif de `res.partner` | Aucun champ de qualification/score/évaluation — ne peut pas servir de socle réel à une évaluation fournisseur. |
| `hr_skills` *(natif Odoo, pas OCA)* | `hr.skill`, `hr.employee.skill`, `hr.resume.line`... | Installé et peuplé de données de démonstration, mais aucun lien avec un poste ou un processus SMQ. |

Autres modules OCA disponibles sur le disque mais non installés, à évaluer au cas
par cas : `mgmtsystem_nonconformity_hazard`, `mgmtsystem_nonconformity_type`
(installables immédiatement, dépendances déjà présentes) ; `mgmtsystem_nonconformity_maintenance_equipment`,
`_mrp`, `_product`, `_repair` (nécessitent l'activation d'apps Odoo standard
actuellement éteintes : `maintenance`, `mrp`, `product`, `repair`).

---

## 8. Dette technique connue

**Doublon documentaire (`document_page` vs `smq_document`)** : le module OCA
`document_page` (wiki libre : catégories Manuel qualité, Procédures, Instructions)
est installé et son menu natif est accessible via l'app générique "Knowledge",
distincte de l'app SMQ. Une page réelle (`document_page`, id hors données de
démonstration) a déjà été créée par un utilisateur dans ce wiki libre, en parallèle
du circuit documentaire officiel (`smq_document`) — un doublon conceptuel déjà
matérialisé, pas seulement théorique. Recommandation : migrer le contenu existant
vers `smq_document` et désinstaller la branche wiki
(`document_page_environment_manual`, `document_page_environmental_aspect` sont
d'ailleurs déjà désinstallés dans l'environnement), sauf besoin métier explicite
d'un espace de notes libres distinct des documents maîtrisés.

**Risque de récurrence** : le même schéma de doublon est susceptible de se
reproduire entre le moteur de non-conformité déjà intégré
(`mgmtsystem_nonconformity`) et les concepts natifs d'alerte/non-conformité des
apps Odoo `quality`/`maintenance` si elles sont installées sans décision
d'architecture préalable.

---

## 9. Ce qu'il faut construire pour la configurabilité multi-secteurs

C'est la pièce architecturale qui manque pour transformer le produit actuel en
plateforme au sens du brief produit initial. À date :

1. **Aucun champ "secteur d'activité"** n'existe sur `res.company`.
2. **`SMQ_NAV`** (navigation de la sidebar) est un tableau JavaScript **codé en
   dur** dans `smq_sidebar_config.js` — strictement identique pour toute société.
3. **`smq.scope`** (module `smq_organization`) et **`smq.referential`** (module
   `smq_referential`) sont des données descriptives : rien dans l'interface ne lit
   ou ne réagit à leur contenu pour adapter l'affichage.
4. **Aucun registre de modules activables** par société, et aucune UI
   d'administration pour le piloter (le menu "Paramètres SMQ" est aujourd'hui un
   simple placeholder).

Construire cette brique implique de travailler sur le système de modules d'Odoo
lui-même (`ir.module.module`, graphe de dépendances), qui n'est pas conçu nativement
pour un basculement dynamique par client/secteur — un travail exploratoire ciblé
(prototype technique restreint) est recommandé avant tout engagement ferme sur le
chiffrage de cette partie (poste le plus incertain de la feuille de route).

---

## 10. Cartographie complète de la navigation

Légende : ✅ réel (modèle + vue + action Odoo) · 🕓 "À venir" (`comingSoon: true`
dans `smq_sidebar_config.js`, aucun modèle, dialogue de roadmap au clic).

| Groupe | Écran | actionXmlId / mécanisme | État |
|---|---|---|---|
| *(non sectionné)* | Overview | `smq_quality.action_smq_dashboard_client` | ✅ |
| Organisation & Périmètre | Sites | `smq_organization.action_smq_site` | ✅ |
| | Départements | `hr.hr_department_kanban_action` *(réutilisé, natif Odoo)* | ✅ |
| | Activités | `smq_organization.action_smq_activity` | ✅ |
| | Parties intéressées | `smq_organization.action_smq_stakeholder` | ✅ |
| | Périmètre du SMQ | `smq_organization.action_smq_scope` | ✅ |
| Quality Management | Documents / Documents en validation | `smq_document.action_smq_document_all` / `_in_validation` | ✅ |
| | Processus | `smq_quality.action_smq_process` | ✅ |
| | Risques & opportunités | — | 🕓 |
| | Objectifs qualité | — | 🕓 |
| | Indicateurs | — | 🕓 |
| Référentiels & Conformité | Référentiels / Exigences / Matrice de conformité | `smq_referential.action_smq_referential` / `_requirement` / `smq_compliance_line` | ✅ |
| Improvement | Non-conformités / Actions correctives / Audits internes | `smq_quality_bridge.action_smq_nonconformity` / `_corrective_action` / `_audit` | ✅ |
| People & Partners | Compétences & formations / Réclamations clients / Fournisseurs | — | 🕓 (groupe entier) |
| Governance | Revue de direction / Révisions | — | 🕓 (groupe entier) |
| Administration | Utilisateurs / Rôles & permissions / Société | `base.action_res_users` / `_groups` / `_company_form` | ✅ *(écrans Odoo natifs)* |
| | Paramètres SMQ | — | 🕓 |

---

## 11. Glossaire

- **SMQ** : Système de Management de la Qualité.
- **OCA** : Odoo Community Association, organisation qui maintient des modules
  Odoo open-source (dont la suite "management-system" utilisée ici).
- **Bridge (pont)** : module custom dont le rôle est d'intégrer un moteur OCA
  existant à l'expérience SMQ (sécurité, vues, workflow) sans dupliquer sa logique
  ni modifier son code.
- **`_inherit`** : mécanisme d'héritage Odoo permettant d'étendre un modèle/une vue
  existante depuis un autre module, sans modifier le module d'origine.
- **Placeholder "À venir"** : point d'entrée de menu visible dans l'interface mais
  sans modèle métier réel derrière, en attente de développement — jamais accompagné
  d'une donnée fictive.
