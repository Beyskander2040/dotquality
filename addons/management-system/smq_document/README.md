# SMQ - Document

Gestion documentaire du SMQ : identité (`smq.document`), taxonomie
(`smq.document.type`), statuts (`smq.document.stage`) et versions contrôlées
(`smq.document.version`).

## Workflow

`Brouillon → En validation → Publié → En vigueur`, avec possibilité de passer
en `Obsolète` à tout moment. Ce lot n'implémente pas encore l'approbation à
paliers (voir `smq_document_approval`, module optionnel à venir avec
`base_tier_validation`) — chaque transition est un bouton simple, sans
validateur dédié.

Une version quittant le brouillon est figée (fichier, motif, description,
auteur, numéro) : toute évolution du contenu nécessite une nouvelle version
(bouton "Nouvelle version" sur le document).

Quand une version devient "en vigueur", l'ancienne version "en vigueur" du
même document (s'il y en a une) passe automatiquement "obsolète".

## Dépendances

`smq_quality` (processus, groupes de sécurité, menu racine), `mail`.
