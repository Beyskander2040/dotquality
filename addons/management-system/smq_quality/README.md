# SMQ - Quality Core

Module cœur du SMQ (Système de Management de la Qualité) : aucune dépendance
aux modules ERP (Achats, Ventes, Stock, Fabrication, Comptabilité). Sert de
base commune aux futurs modules `smq_document`, `smq_quality_bridge`, etc.

## Contenu

- `smq.process` / `smq.process.category` : registre des processus qualité,
  indépendant de `mgmtsystem.system` (module `mgmtsystem`, OCA).
- Groupes de sécurité communs (`Employé` → `Administrateur SMQ`, chaîne
  d'implication linéaire), destinés à être réutilisés par tous les modules
  SMQ à venir.
- Menu racine `SMQ` (application dédiée dans le sélecteur d'apps Odoo).

## Dépendances

`mail` uniquement — chatter et activités sur `smq.process`.

## Données de démonstration

6 processus (`PR-01` à `PR-06`) répartis sur 3 catégories ISO 9001
(management / réalisation / support), chargés en mode démo uniquement.
