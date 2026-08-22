# SMQ Document Upload

Ajoute une zone d'upload de fichiers (PDF, Word, ...) visible directement sur le
formulaire des pages du SMQ (`document.page`, module `document_page`), sans
modifier le code source de ce module.

## Contenu

- `models/document_page.py` : hérite `document.page` et ajoute le champ
  `document_ids` (`One2many` vers `ir.attachment`, filtré sur
  `res_model = 'document.page'`). C'est le même mécanisme natif Odoo utilisé
  pour les onglets "Documents" des fiches produit.
- `views/document_page_views.xml` : hérite la vue formulaire de
  `document_page` pour afficher ce champ avec le widget `many2many_binary`
  (zone de dépôt de fichiers), juste au-dessus du contenu de la page.

## Droits d'accès

Aucune règle d'accès supplémentaire n'est nécessaire : l'upload suit les
droits déjà définis sur `document.page` (groupes Editor/Manager du module
`document_page`). Le groupe "Document / User" reste en lecture seule, par
conception.

## Comportement du versioning

Les fichiers déposés s'accumulent dans la liste : déposer un nouveau fichier
ne supprime pas les précédents, qui restent visibles et téléchargeables. Ce
comportement n'est pas (pour l'instant) strictement lié à une révision
(`document.page.history`) précise.
