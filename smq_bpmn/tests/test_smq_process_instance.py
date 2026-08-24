from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

# Diagrammes de test — mêmes conventions que les autres fichiers de tests
# smq_bpmn (XML brut avec le namespace bpmn: complet, jamais de string
# concatenation dans le code de production, uniquement dans les fixtures).

# start -> service (auto) -> user (arrêt) -> end
_XML_LINEAR_WITH_USER_TASK = (
    "<?xml version='1.0'?>"
    "<bpmn:definitions xmlns:bpmn='http://www.omg.org/spec/BPMN/20100524/MODEL'>"
    "<bpmn:process id='Process_1'>"
    "<bpmn:startEvent id='Start_1' name='Début'/>"
    "<bpmn:serviceTask id='Service_1' name='Notifier'/>"
    "<bpmn:userTask id='User_1' name='Qualifier'/>"
    "<bpmn:endEvent id='End_1' name='Fin'/>"
    "<bpmn:sequenceFlow id='Flow_1' sourceRef='Start_1' targetRef='Service_1'/>"
    "<bpmn:sequenceFlow id='Flow_2' sourceRef='Service_1' targetRef='User_1'/>"
    "<bpmn:sequenceFlow id='Flow_3' sourceRef='User_1' targetRef='End_1'/>"
    "</bpmn:process>"
    "</bpmn:definitions>"
)

# start -> end (rien d'autre)
_XML_START_TO_END = (
    "<?xml version='1.0'?>"
    "<bpmn:definitions xmlns:bpmn='http://www.omg.org/spec/BPMN/20100524/MODEL'>"
    "<bpmn:process id='Process_1'>"
    "<bpmn:startEvent id='Start_1'/>"
    "<bpmn:endEvent id='End_1'/>"
    "<bpmn:sequenceFlow id='Flow_1' sourceRef='Start_1' targetRef='End_1'/>"
    "</bpmn:process>"
    "</bpmn:definitions>"
)

# start -> user -> gateway -> (fondée: user_a -> end) / (incomplète: user_b -> end)
_XML_WITH_GATEWAY = (
    "<?xml version='1.0'?>"
    "<bpmn:definitions xmlns:bpmn='http://www.omg.org/spec/BPMN/20100524/MODEL'>"
    "<bpmn:process id='Process_1'>"
    "<bpmn:startEvent id='Start_1'/>"
    "<bpmn:userTask id='User_1' name='Qualifier'/>"
    "<bpmn:exclusiveGateway id='Gateway_1' name='Fondée ?'/>"
    "<bpmn:userTask id='User_A' name='Traiter'/>"
    "<bpmn:userTask id='User_B' name='Compléter'/>"
    "<bpmn:endEvent id='End_1'/>"
    "<bpmn:sequenceFlow id='Flow_1' sourceRef='Start_1' targetRef='User_1'/>"
    "<bpmn:sequenceFlow id='Flow_2' sourceRef='User_1' targetRef='Gateway_1'/>"
    "<bpmn:sequenceFlow id='Flow_3' sourceRef='Gateway_1' targetRef='User_A' name='fondée'/>"
    "<bpmn:sequenceFlow id='Flow_4' sourceRef='Gateway_1' targetRef='User_B' name='incomplète'/>"
    "<bpmn:sequenceFlow id='Flow_5' sourceRef='User_A' targetRef='End_1'/>"
    "<bpmn:sequenceFlow id='Flow_6' sourceRef='User_B' targetRef='End_1'/>"
    "</bpmn:process>"
    "</bpmn:definitions>"
)

_XML_NO_START = (
    "<?xml version='1.0'?>"
    "<bpmn:definitions xmlns:bpmn='http://www.omg.org/spec/BPMN/20100524/MODEL'>"
    "<bpmn:process id='Process_1'>"
    "<bpmn:endEvent id='End_1'/>"
    "</bpmn:process>"
    "</bpmn:definitions>"
)

_XML_UNSUPPORTED_ELEMENT = (
    "<?xml version='1.0'?>"
    "<bpmn:definitions xmlns:bpmn='http://www.omg.org/spec/BPMN/20100524/MODEL'>"
    "<bpmn:process id='Process_1'>"
    "<bpmn:startEvent id='Start_1'/>"
    "<bpmn:parallelGateway id='Parallel_1'/>"
    "<bpmn:endEvent id='End_1'/>"
    "<bpmn:sequenceFlow id='Flow_1' sourceRef='Start_1' targetRef='Parallel_1'/>"
    "<bpmn:sequenceFlow id='Flow_2' sourceRef='Parallel_1' targetRef='End_1'/>"
    "</bpmn:process>"
    "</bpmn:definitions>"
)


class TestSmqProcessInstance(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")
        cls.employee = cls.env["res.users"].create(
            {
                "name": "Employé Instance Test",
                "login": "smq_bpmn_instance_employee_test",
                "email": "smq_bpmn_instance_employee_test@example.com",
                "groups_id": [(6, 0, [cls.env.ref("smq_quality.group_smq_employee").id])],
            }
        )
        cls.writer = cls.env["res.users"].create(
            {
                "name": "Rédacteur Instance Test",
                "login": "smq_bpmn_instance_writer_test",
                "email": "smq_bpmn_instance_writer_test@example.com",
                "groups_id": [
                    (6, 0, [cls.env.ref("base.group_user").id, cls.env.ref("smq_quality.group_smq_writer").id])
                ],
            }
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Responsable Qualité Instance Test",
                "login": "smq_bpmn_instance_manager_test",
                "email": "smq_bpmn_instance_manager_test@example.com",
                "groups_id": [
                    (
                        6, 0,
                        [cls.env.ref("base.group_user").id, cls.env.ref("smq_quality.group_smq_quality_manager").id],
                    )
                ],
            }
        )
        cls.process = cls.env["smq.process"].with_user(cls.admin).create(
            {"code": "PROC-INSTANCE-TEST", "name": "Processus test instance"}
        )
        cls.model_smq_process_version = cls.env.ref("smq_bpmn.model_smq_process_version")

    def setUp(self):
        super().setUp()
        self.env = self.env(user=self.admin)

    def _new_version(self, version="V1", **vals):
        values = {"process_id": self.process.id, "version": version}
        values.update(vals)
        return self.env["smq.process.version"].create(values)

    def _effective_version(self, version="V1", **vals):
        v = self._new_version(version, **vals)
        v.action_submit_review()
        v.action_approve()
        v.action_make_effective()
        return v

    # ------------------------------------------------------------------
    # A. Démarrage
    # ------------------------------------------------------------------

    def test_a1_cannot_start_non_effective_version(self):
        version = self._new_version("VA1", bpmn_xml=_XML_START_TO_END)
        with self.assertRaises(UserError):
            version.action_start_instance()

    def test_a2_start_creates_instance_at_start_element(self):
        version = self._effective_version("VA2", bpmn_xml=_XML_LINEAR_WITH_USER_TASK)
        instance = version.action_start_instance()
        self.assertEqual(instance.process_version_id, version)
        self.assertEqual(instance.state, "running")

    def test_a3_viewer_cannot_start(self):
        version = self._effective_version("VA3", bpmn_xml=_XML_LINEAR_WITH_USER_TASK)
        with self.assertRaises(UserError):
            version.with_user(self.employee).action_start_instance()

    def test_a4_writer_can_start(self):
        version = self._effective_version("VA4", bpmn_xml=_XML_LINEAR_WITH_USER_TASK)
        instance = version.with_user(self.writer).action_start_instance()
        self.assertTrue(instance)

    def test_a5_requires_unique_start_event(self):
        version = self._effective_version("VA5", bpmn_xml=_XML_NO_START)
        with self.assertRaises(UserError):
            version.action_start_instance()

    def test_a6_unsupported_element_blocks_start(self):
        version = self._effective_version("VA6", bpmn_xml=_XML_UNSUPPORTED_ELEMENT)
        with self.assertRaises(UserError):
            version.action_start_instance()

    # ------------------------------------------------------------------
    # B. Avancement automatique
    # ------------------------------------------------------------------

    def test_b1_auto_advances_through_service_task_stops_at_user_task(self):
        version = self._effective_version("VB1", bpmn_xml=_XML_LINEAR_WITH_USER_TASK)
        instance = version.action_start_instance()
        self.assertEqual(instance.current_element_id, "User_1")
        self.assertEqual(instance.state, "running")

    def test_b2_trivial_start_to_end_completes_immediately(self):
        version = self._effective_version("VB2", bpmn_xml=_XML_START_TO_END)
        instance = version.action_start_instance()
        self.assertEqual(instance.state, "completed")
        self.assertEqual(instance.current_element_id, "End_1")
        self.assertTrue(instance.end_date)

    # ------------------------------------------------------------------
    # C. Avancement manuel / passerelles
    # ------------------------------------------------------------------

    def test_c1_advance_single_outgoing_moves_forward(self):
        version = self._effective_version("VC1", bpmn_xml=_XML_LINEAR_WITH_USER_TASK)
        instance = version.action_start_instance()
        instance.action_advance()
        self.assertEqual(instance.state, "completed")

    def test_c2_gateway_without_choice_raises(self):
        version = self._effective_version("VC2", bpmn_xml=_XML_WITH_GATEWAY)
        instance = version.action_start_instance()
        instance.action_advance()  # User_1 -> Gateway_1
        with self.assertRaises(UserError):
            instance.action_advance()

    def test_c3_gateway_with_valid_choice_follows_branch(self):
        version = self._effective_version("VC3", bpmn_xml=_XML_WITH_GATEWAY)
        instance = version.action_start_instance()
        instance.action_advance()  # -> Gateway_1
        instance.action_advance(chosen_flow_id="Flow_4")  # incomplète -> User_B
        self.assertEqual(instance.current_element_id, "User_B")

    def test_c4_invalid_branch_choice_raises(self):
        version = self._effective_version("VC4", bpmn_xml=_XML_WITH_GATEWAY)
        instance = version.action_start_instance()
        instance.action_advance()
        with self.assertRaises(UserError):
            instance.action_advance(chosen_flow_id="Flow_DOES_NOT_EXIST")

    def test_c5_cannot_advance_completed_instance(self):
        version = self._effective_version("VC5", bpmn_xml=_XML_START_TO_END)
        instance = version.action_start_instance()
        self.assertEqual(instance.state, "completed")
        with self.assertRaises(UserError):
            instance.action_advance()

    def test_c6_get_pending_branches_labels(self):
        version = self._effective_version("VC6", bpmn_xml=_XML_WITH_GATEWAY)
        instance = version.action_start_instance()
        instance.action_advance()
        branches = dict(instance.get_pending_branches())
        self.assertEqual(branches["Flow_3"], "fondée")
        self.assertEqual(branches["Flow_4"], "incomplète")

    def test_c7_viewer_cannot_advance(self):
        version = self._effective_version("VC7", bpmn_xml=_XML_LINEAR_WITH_USER_TASK)
        instance = version.action_start_instance()
        with self.assertRaises(UserError):
            instance.with_user(self.employee).action_advance()

    # ------------------------------------------------------------------
    # D. Exécution du mapping à l'arrivée
    # ------------------------------------------------------------------

    def test_d1_mapping_action_executes_on_arrival(self):
        target_version = self._new_version("VD1-TARGET")
        self.assertEqual(target_version.state, "draft")

        # Le mapping doit être créé pendant que la version-diagramme est
        # encore en brouillon : _check_version_editable() bloque toute
        # création/modification de mapping une fois la version non-draft.
        version = self._new_version("VD1", bpmn_xml=_XML_LINEAR_WITH_USER_TASK)
        self.env["smq.bpmn.task.mapping"].create(
            {
                "process_version_id": version.id,
                "bpmn_element_id": "Service_1",
                "odoo_model_id": self.model_smq_process_version.id,
                "odoo_method": "action_submit_review",
            }
        )
        version.action_submit_review()
        version.action_approve()
        version.action_make_effective()

        instance = version.action_start_instance(
            res_model_id=self.model_smq_process_version.id, res_id=target_version.id
        )
        self.assertEqual(target_version.state, "review")
        self.assertEqual(instance.current_element_id, "User_1")

    def test_d2_mapping_skipped_when_model_mismatches_instance_res_model(self):
        target_version = self._new_version("VD2-TARGET")
        other_model = self.env.ref("smq_quality.model_smq_process")

        version = self._new_version("VD2", bpmn_xml=_XML_LINEAR_WITH_USER_TASK)
        self.env["smq.bpmn.task.mapping"].create(
            {
                "process_version_id": version.id,
                "bpmn_element_id": "Service_1",
                "odoo_model_id": self.model_smq_process_version.id,
                "odoo_method": "action_submit_review",
            }
        )
        version.action_submit_review()
        version.action_approve()
        version.action_make_effective()

        # res_model_id volontairement différent du modèle du mapping.
        version.action_start_instance(res_model_id=other_model.id, res_id=self.process.id)
        self.assertEqual(target_version.state, "draft")

    def test_d3_no_mapping_does_not_crash(self):
        version = self._effective_version("VD3", bpmn_xml=_XML_LINEAR_WITH_USER_TASK)
        instance = version.action_start_instance()
        self.assertEqual(instance.current_element_id, "User_1")

    # ------------------------------------------------------------------
    # E. Annulation
    # ------------------------------------------------------------------

    def test_e1_manager_can_cancel(self):
        version = self._effective_version("VE1", bpmn_xml=_XML_LINEAR_WITH_USER_TASK)
        instance = version.action_start_instance()
        instance.with_user(self.manager).action_cancel()
        self.assertEqual(instance.state, "cancelled")
        self.assertTrue(instance.end_date)

    def test_e2_writer_cannot_cancel(self):
        version = self._effective_version("VE2", bpmn_xml=_XML_LINEAR_WITH_USER_TASK)
        instance = version.action_start_instance()
        with self.assertRaises(UserError):
            instance.with_user(self.writer).action_cancel()

    def test_e3_cannot_cancel_completed_instance(self):
        version = self._effective_version("VE3", bpmn_xml=_XML_START_TO_END)
        instance = version.action_start_instance()
        with self.assertRaises(UserError):
            instance.with_user(self.manager).action_cancel()

    # ------------------------------------------------------------------
    # F. Assistant "Avancer"
    # ------------------------------------------------------------------

    def test_f1_wizard_advances_single_branch(self):
        version = self._effective_version("VF1", bpmn_xml=_XML_LINEAR_WITH_USER_TASK)
        instance = version.action_start_instance()
        wizard = self.env["smq.process.instance.advance.wizard"].with_context(
            default_instance_id=instance.id
        ).create({"instance_id": instance.id})
        wizard.action_confirm()
        self.assertEqual(instance.state, "completed")

    def test_f2_wizard_selection_lists_branches(self):
        version = self._effective_version("VF2", bpmn_xml=_XML_WITH_GATEWAY)
        instance = version.action_start_instance()
        instance.action_advance()
        wizard = self.env["smq.process.instance.advance.wizard"].with_context(
            default_instance_id=instance.id
        ).new({"instance_id": instance.id})
        options = dict(wizard._selection_branches())
        self.assertIn("Flow_3", options)
        self.assertIn("Flow_4", options)
