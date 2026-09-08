from odoo import fields, models


class MgmtsystemReview(models.Model):
    _inherit = "mgmtsystem.review"

    # Relabellisation FR uniquement — aucun nouveau champ, aucune nouvelle
    # logique : le moteur OCA (participants, politique, changements,
    # conclusion, état, lignes liées à des Actions/NC déjà existantes) est
    # repris tel quel, à l'identique du pattern déjà suivi pour NC/Action/Audit.
    name = fields.Char(string="Titre")
    date = fields.Datetime(string="Date")
    user_ids = fields.Many2many(string="Participants")
    policy = fields.Html(string="Politique qualité")
    changes = fields.Html(string="Changements ayant un impact sur le SMQ")
    conclusion = fields.Html(string="Conclusion")
    state = fields.Selection(
        [("open", "Ouverte"), ("done", "Clôturée")],
        string="État",
        default="open",
        tracking=True,
    )


class MgmtsystemReviewLine(models.Model):
    _inherit = "mgmtsystem.review.line"

    name = fields.Char(string="Titre")
    type = fields.Selection(
        [("action", "Action corrective"), ("nonconformity", "Non-conformité")],
        string="Type d'entrée",
    )
    action_id = fields.Many2one(string="Action corrective")
    nonconformity_id = fields.Many2one(string="Non-conformité")
    decision = fields.Text(string="Décision")
