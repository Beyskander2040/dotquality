import base64
import re
import xml.etree.ElementTree as ET

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

# LOT 9 est une intégration frontend (bpmn-js) : elle n'ajoute aucun champ ni
# méthode côté serveur. Ce fichier ne duplique donc pas les tests LOT 8
# (déjà exhaustifs sur write()/verrouillage/checksum) ; il vérifie
# spécifiquement ce que LOT 9 a réellement changé : manifeste/assets, vue,
# et ré-affirme explicitement (comme demandé au §17 du brief) que le
# verrouillage serveur protège bien contre un contournement "frontend".

# LOT 11 : action_approve() exige désormais un BPMN XML valide et
# identifiable (précondition §11) — utilisé par les tests de verrouillage
# de ce fichier qui doivent atteindre l'état "approved" pour s'exécuter.
_VALID_BPMN_XML = (
    "<?xml version='1.0'?>"
    "<bpmn:definitions xmlns:bpmn='http://www.omg.org/spec/BPMN/20100524/MODEL'>"
    "<bpmn:process id='Process_1'><bpmn:task id='Task_1'/></bpmn:process>"
    "</bpmn:definitions>"
)

_FORBIDDEN_LOT10_12_SUBSTRINGS = (
    "odoo_model",
    "odoo_method",
    "odoo_action",
    "smq_document_id",
    "properties-panel",
    "execution_id",
    "process_instance",
    "current_task",
    "camunda",
    "flowable",
    "moddle-extension",
)


class TestSmqBpmnEditorLot9(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")
        cls.writer = cls.env["res.users"].create(
            {
                "name": "Rédacteur LOT9 Test",
                "login": "smq_bpmn_lot9_writer_test",
                "email": "smq_bpmn_lot9_writer_test@example.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("smq_quality.group_smq_writer").id,
                        ],
                    )
                ],
            }
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Responsable Qualité LOT9 Test",
                "login": "smq_bpmn_lot9_manager_test",
                "email": "smq_bpmn_lot9_manager_test@example.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("smq_quality.group_smq_quality_manager").id,
                        ],
                    )
                ],
            }
        )
        cls.process = cls.env["smq.process"].with_user(cls.admin).create(
            {"code": "PROC-LOT9-TEST", "name": "Processus test LOT 9"}
        )

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.admin)

    def _new_version(self, version="V1", **vals):
        values = {"process_id": self.process.id, "version": version}
        values.update(vals)
        return self.env["smq.process.version"].create(values)

    def _module_path(self, relative):
        import odoo.modules.module as module_tools

        return module_tools.get_module_resource("smq_bpmn", *relative.split("/"))

    def _read_module_file(self, relative):
        with open(self._module_path(relative), "r", encoding="utf-8") as f:
            return f.read()

    # ------------------------------------------------------------------
    # A. Manifeste et assets
    # ------------------------------------------------------------------

    def test_a1_manifest_declares_bpmn_js_exactly_once(self):
        manifest = self.env["ir.module.module"].search([("name", "=", "smq_bpmn")])
        self.assertTrue(manifest)
        import odoo.modules.module as module_tools

        manifest_dict = module_tools.load_manifest("smq_bpmn")
        backend_assets = manifest_dict["assets"]["web.assets_backend"]
        bpmn_js_entries = [a for a in backend_assets if "bpmn-modeler.development.js" in a]
        self.assertEqual(len(bpmn_js_entries), 1)

    def test_a2_depends_unchanged(self):
        # LOT 11 : "mail" a été ajouté explicitement (smq.process.version
        # hérite désormais de mail.thread pour le chatter, §14) — dépendance
        # déjà transitivement présente via smq_quality, mais déclarée
        # directement puisque le module utilise mail.thread lui-même.
        import odoo.modules.module as module_tools

        manifest_dict = module_tools.load_manifest("smq_bpmn")
        self.assertEqual(manifest_dict["depends"], ["smq_quality", "mail"])

    def test_a3_no_external_dependencies_added(self):
        import odoo.modules.module as module_tools

        manifest_dict = module_tools.load_manifest("smq_bpmn")
        self.assertFalse(manifest_dict.get("external_dependencies"))

    def test_a4_asset_bundle_compiles_and_contains_new_widget(self):
        attachment = self.env["ir.qweb"]._get_asset_bundle("web.assets_backend").js()
        content = base64.b64decode(attachment.datas)
        self.assertIn(b"SmqBpmnEditor", content)
        self.assertIn(b"smq_bpmn_editor", content)

    # ------------------------------------------------------------------
    # B. Vue
    # ------------------------------------------------------------------

    def test_b1_bpmn_xml_field_uses_new_widget(self):
        view = self.env.ref("smq_bpmn.view_smq_process_version_form")
        self.assertIn('widget="smq_bpmn_editor"', view.arch)

    def test_b2_bpmn_xml_readonly_tied_to_state(self):
        view = self.env.ref("smq_bpmn.view_smq_process_version_form")
        self.assertIn("state != 'draft'", view.arch)

    def test_b3_get_view_loads_without_error(self):
        version = self._new_version("VB3")
        result = version.get_view(view_type="form")
        self.assertIn("smq.process.version", result["models"])

    # ------------------------------------------------------------------
    # C. Sécurité — le verrouillage LOT 8 protège contre un contournement
    #    "frontend" (§17 du brief : à tester explicitement).
    # ------------------------------------------------------------------

    def test_c1_editor_draft_write_allowed(self):
        version = self._new_version("VC1")
        version.with_user(self.writer).write({"bpmn_xml": "<xml>editor draft</xml>"})
        self.assertEqual(version.bpmn_xml, "<xml>editor draft</xml>")

    def test_c2_editor_approved_write_refused(self):
        # LOT 11 : "approved" exige désormais un BPMN XML valide et
        # identifiable (précondition §11) avant que action_approve() ne
        # réussisse — le fixture doit donc être un XML BPMN réel, pas un
        # simple XML de convenance comme au LOT 9.
        version = self._new_version("VC2", bpmn_xml=_VALID_BPMN_XML)
        version.action_submit_review()
        version.action_approve()
        with self.assertRaises(ValidationError):
            version.with_user(self.writer).write({"bpmn_xml": "<xml>hack</xml>"})

    def test_c3_manager_approved_write_refused(self):
        # Le rôle Manager ne doit pas pouvoir contourner le verrouillage
        # d'une version approuvée par une simple écriture — seule une
        # nouvelle version (draft) permet de faire évoluer le BPMN.
        version = self._new_version("VC3", bpmn_xml=_VALID_BPMN_XML)
        version.action_submit_review()
        version.action_approve()
        with self.assertRaises(ValidationError):
            version.with_user(self.manager).write({"bpmn_xml": "<xml>hack</xml>"})

    def test_c4_new_version_is_the_only_way_to_change_approved_bpmn(self):
        version = self._new_version("VC4", bpmn_xml=_VALID_BPMN_XML)
        version.action_submit_review()
        version.action_approve()
        new_version = self.env["smq.process.version"].with_user(self.manager).create(
            {"process_id": self.process.id, "version": "VC4-bis", "bpmn_xml": "<xml>v2</xml>"}
        )
        self.assertEqual(new_version.state, "draft")
        self.assertEqual(new_version.bpmn_xml, "<xml>v2</xml>")

    # ------------------------------------------------------------------
    # D. Non-régression LOT 8 / absence de portée LOT 10-12
    # ------------------------------------------------------------------

    def test_d1_no_new_fields_on_process_version(self):
        expected = {
            "process_id", "version", "name", "state", "bpmn_xml", "bpmn_checksum",
            "created_by", "created_date", "approved_by", "approved_date",
            "obsolete_date", "notes", "active",
        }
        fields = self.env["smq.process.version"]._fields
        for name in expected:
            self.assertIn(name, fields)
        for forbidden in _FORBIDDEN_LOT10_12_SUBSTRINGS:
            self.assertNotIn(forbidden, fields)

    def test_d2_no_new_fields_on_process(self):
        fields = self.env["smq.process"]._fields
        for forbidden in _FORBIDDEN_LOT10_12_SUBSTRINGS:
            self.assertNotIn(forbidden, fields)

    def test_d3_no_forbidden_lot10_12_substrings_in_new_js_files(self):
        # LOT 10 (postérieur à ce fichier) a légitimement introduit
        # odoo_model/odoo_method/odoo_action dans smq_bpmn_editor_widget.esm.js
        # (mapping BPMN -> Odoo, hors périmètre du LOT 9 mais explicitement
        # demandé au LOT 10) — même principe que le renommage du LOT 3F pour
        # "execution_status". Ce fichier vérifie donc, pour le JS du LOT 9
        # spécifiquement, l'absence des concepts qui restent hors périmètre
        # après LOT 10 (exécution, moteur, package properties-panel externe).
        forbidden_for_js = tuple(
            s
            for s in _FORBIDDEN_LOT10_12_SUBSTRINGS
            if s not in ("odoo_model", "odoo_method", "odoo_action", "smq_document_id")
        )
        for relative in (
            "static/src/js/smq_bpmn_editor.esm.js",
            "static/src/js/smq_bpmn_editor_widget.esm.js",
        ):
            content = self._read_module_file(relative).lower()
            for forbidden in forbidden_for_js:
                self.assertNotIn(forbidden, content, f"{forbidden!r} found in {relative}")

    def test_d4_checksum_recomputed_after_frontend_style_save(self):
        version = self._new_version("VD4")
        xml_content = "<xml>contenu simulant un saveXML() de bpmn-js</xml>"
        version.with_user(self.writer).write({"bpmn_xml": xml_content})
        import hashlib

        expected = hashlib.sha256(xml_content.encode("utf-8")).hexdigest()
        self.assertEqual(version.bpmn_checksum, expected)

    # ------------------------------------------------------------------
    # E. Diagramme par défaut (canvas jamais vide, §11 du brief)
    # ------------------------------------------------------------------

    def _extract_default_xml(self):
        content = self._read_module_file("static/src/js/smq_bpmn_editor.esm.js")
        match = re.search(
            r"const DEFAULT_BPMN_XML = `(.*?)`;", content, re.DOTALL
        )
        self.assertTrue(match, "DEFAULT_BPMN_XML constant not found")
        return match.group(1)

    def test_e1_default_diagram_is_well_formed_xml(self):
        default_xml = self._extract_default_xml()
        ET.fromstring(default_xml)  # lève une exception si le XML est invalide

    def test_e2_default_diagram_has_start_task_end(self):
        default_xml = self._extract_default_xml()
        self.assertIn("startEvent", default_xml)
        self.assertIn("bpmn:task", default_xml)
        self.assertIn("endEvent", default_xml)

    def test_e3_default_diagram_not_used_when_xml_already_set(self):
        # Sanity : le diagramme par défaut vit uniquement dans le JS (jamais
        # écrit en base) — une version créée avec un bpmn_xml explicite
        # conserve exactement ce contenu, jamais remplacé par le brouillon
        # par défaut.
        version = self._new_version("VE3", bpmn_xml="<xml>contenu réel</xml>")
        self.assertEqual(version.bpmn_xml, "<xml>contenu réel</xml>")
