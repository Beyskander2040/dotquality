from odoo import fields, models


class MgmtsystemNonconformityStage(models.Model):
    _inherit = "mgmtsystem.nonconformity.stage"

    # Le SMQ distingue "Résolue" (traitement terminé, en attente de clôture
    # formelle) de "Clôturée" (done) : on étend la sélection existante plutôt
    # que de créer un second champ d'état.
    state = fields.Selection(selection_add=[("resolved", "Résolue")])

    def _relabel_fr(self, name):
        # Un <field name="name">...</field> dans les données ne remplace que
        # la valeur "source" (en_US) d'un champ traduit ; la traduction fr_FR
        # existante (héritée de mgmtsystem_nonconformity) reste inchangée.
        # with_context(lang=...) + write() cible explicitement fr_FR.
        self.with_context(lang="fr_FR").write({"name": name})
