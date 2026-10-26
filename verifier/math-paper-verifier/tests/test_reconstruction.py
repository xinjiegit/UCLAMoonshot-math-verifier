"""Regression checks for evidence gates and local staging, without model calls."""
import copy
import json
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "run"))
import reconstruction as r


def fixture_result(outcome="supported"):
    value = {
        "schema_version": "reconstruction-result.v1", "target_id": "T1",
        "outcome": outcome, "claimed_result": "The determinant is -1.",
        "computed_result": "-1", "source_agreement": "not_checked",
        "convention_match": "demonstrated", "construction_match": "demonstrated",
        "conventions": [{"name": "orientation", "definition": "Ordered standard basis (e1,e2).",
                         "locator": "paper.txt, line 1"}],
        "derivation": [{"step": "1", "statement": "The transposition matrix has determinant -1.",
                        "justification": "det([[0,1],[1,0]]) = 0*0 - 1*1."}],
        "model_identification": "The linear map in the claim exchanges the two stated basis vectors.",
        "calculation": {"method": "analytic", "expression": "0*0-1*1", "result": "-1"},
        "consequence": "The claimed local determinant agrees with this computation.",
        "consequence_status": "established", "unresolved": [], "evidence": [],
    }
    if outcome == "unresolved":
        value.update(computed_result="", convention_match="unresolved", construction_match="unresolved",
                     conventions=[], derivation=[], model_identification="",
                     calculation={"method": "not_performed", "expression": "", "result": ""},
                     consequence="The claim remains unverified.",
                     unresolved=[{"kind": "convention", "detail": "The source orientation is unspecified."}])
    return value


class ReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.paper = self.root / "source.tex"
        self.paper.write_text("The orientation uses (e1,e2); exchange e1 and e2.\n")
        self.reference = self.root / "reference.md"
        self.reference.write_text("det([[a,b],[c,d]])=ad-bc.\n")
        self.plan_run = r.prepare_plan(self.paper, self.root / "planner", "Critical determinants", [self.reference])
        self.plan = {
            "schema_version": "reconstruction-plan.v1", "scope": "Critical determinants",
            "selection_status": "complete", "limitations": [], "targets": [{
                "target_id": "T1", "location": "Line 1", "claim": "The determinant is -1.",
                "prerequisites": ["The ordered basis is (e1,e2)."],
                "downstream_use": "Determines whether the map reverses orientation.",
                "selection_reason": "The orientation argument depends on this sign.",
            }],
        }
        (self.plan_run / "plan.json").write_bytes(r.dump(self.plan))
        self.pair = r.prepare_pair(self.plan_run, "T1", self.root / "pair")

    def tearDown(self):
        self.temp.cleanup()

    def write_results(self, a="supported", b="supported"):
        for side, outcome in [("a", a), ("b", b)]:
            (self.pair / side / "result.json").write_bytes(r.dump(fixture_result(outcome)))

    def test_materials_identical_but_prompts_are_separate(self):
        a = self.pair / "a" / "input"
        b = self.pair / "b" / "input"
        self.assertEqual({p.name: p.read_bytes() for p in a.iterdir()},
                         {p.name: p.read_bytes() for p in b.iterdir()})
        self.assertEqual((a / "reference-001.md").read_bytes(), self.reference.read_bytes())
        self.assertIn(str(self.pair / "a" / "result.json"), (self.pair / "a" / "worker-prompt.txt").read_text())
        prompts = [(self.pair / side / "worker-prompt.txt").read_text().replace(
            str(self.pair / side), "WORKER") for side in ("a", "b")]
        self.assertEqual(prompts[0], prompts[1])

    def test_reconstruction_cli_and_unsupported_kind(self):
        command = [sys.executable, str(r.ROOT / "run/reconstruction.py"), "prepare-plan",
                   "--paper", str(self.paper), "--scope", "Critical determinants"]
        out = self.root / "cli-plan"
        prepared = subprocess.run(command + ["--out", str(out), "--audit-kind", "reconstruction"],
                                  capture_output=True, text=True)
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertEqual(r.check_inputs(out, "plan")["audit_kind"], "reconstruction")
        unsupported = self.root / "unsupported"
        rejected = subprocess.run(command + ["--out", str(unsupported), "--audit-kind", "central"],
                                  capture_output=True, text=True)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse(unsupported.exists())

    def test_rejects_another_audit_kind_in_manifest(self):
        path = self.pair / "input-manifest.json"
        value = r.read_json(path)
        value["audit_kind"] = "central"
        path.chmod(0o644)
        path.write_bytes(r.dump(value))
        with self.assertRaisesRegex(ValueError, "unsupported audit kind"):
            r.check_pair(self.pair)

    def test_native_refuter_stays_manuscript_only(self):
        out = self.root / "refuter"
        prepared = subprocess.run([
            sys.executable, str(r.ROOT / "run/run_native.py"), "prepare", "--provider", "codex",
            "--paper", str(self.paper), "--pass", "refuter", "--out", str(out)
        ], capture_output=True, text=True)
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertEqual((out / f"input/paper{self.paper.suffix}").read_bytes(), self.paper.read_bytes())
        self.assertFalse(list((out / "input").glob("reference*")))
        prompt = (out / "worker-prompt.txt").read_text()
        self.assertNotIn(str(self.reference), prompt)
        self.assertNotIn(str(self.plan_run), prompt)
        self.assertIn((r.ROOT / "references/refuter-pass.txt").read_text().strip(), prompt)

    def test_valid_supported_pair_is_only_a_candidate(self):
        self.write_results()
        result = r.check_pair(self.pair)
        self.assertEqual(result["status"], "candidate_supported")
        self.assertTrue(result["requires_mathematical_reconciliation"])
        self.assertFalse(result["transcript_available"])

    def test_valid_unresolved_pair(self):
        self.write_results("unresolved", "unresolved")
        self.assertEqual(r.check_pair(self.pair)["status"], "unresolved")

    def test_pair_disagreement(self):
        self.write_results("supported", "contradicted")
        self.assertEqual(r.check_pair(self.pair)["status"], "disputed")

    def test_agreeing_defect_is_only_candidate(self):
        self.write_results("contradicted", "contradicted")
        self.assertEqual(r.check_pair(self.pair)["status"], "candidate_defect")

    def test_one_result_does_not_complete_pair(self):
        (self.pair / "a" / "result.json").write_bytes(r.dump(fixture_result()))
        result = r.check_pair(self.pair)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["missing_workers"], ["b"])

    def test_citation_only_false_closure(self):
        value = fixture_result()
        value["source_agreement"] = "matched"
        value["calculation"] = {"method": "not_performed", "expression": "", "result": ""}
        with self.assertRaisesRegex(ValueError, "citation agreement"):
            r.validate_result(value, "T1", self.pair / "a")

    def test_missing_model_mapping(self):
        value = fixture_result()
        value["model_identification"] = ""
        with self.assertRaisesRegex(ValueError, "model identification"):
            r.validate_result(value, "T1", self.pair / "a")

    def test_original_input_changed(self):
        self.write_results()
        self.paper.write_text("Changed paper.\n")
        with self.assertRaisesRegex(ValueError, "original input changed"):
            r.check_pair(self.pair)

    def test_staged_input_changed(self):
        self.write_results()
        path = self.pair / "a" / "input" / "paper.txt"
        path.chmod(0o644)
        path.write_text("Different material")
        with self.assertRaisesRegex(ValueError, "staged input changed"):
            r.check_pair(self.pair)

    def test_upstream_plan_changed(self):
        self.write_results()
        (self.plan_run / "plan.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "upstream plan input changed"):
            r.check_pair(self.pair)

    def test_wrong_target(self):
        with self.assertRaisesRegex(ValueError, "target_id"):
            r.validate_result(fixture_result(), "T2", self.pair / "a")

    def test_plan_and_pair_do_not_clobber(self):
        with self.assertRaisesRegex(ValueError, "fresh"):
            r.prepare_plan(self.paper, self.plan_run, "Critical determinants", [])
        with self.assertRaisesRegex(ValueError, "fresh"):
            r.prepare_pair(self.plan_run, "T1", self.pair)

    def test_unresolved_requires_explanation(self):
        value = fixture_result("unresolved")
        value["unresolved"] = []
        with self.assertRaisesRegex(ValueError, "explanation"):
            r.validate_result(value, "T1", self.pair / "a")

    def test_local_defect_can_have_unknown_downstream_scope(self):
        value = fixture_result("contradicted")
        value["consequence_status"] = "unresolved"
        value["unresolved"] = [{"kind": "downstream", "detail": "Other arguments might avoid this defective step."}]
        r.validate_result(value, "T1", self.pair / "a")
        value["unresolved"][0]["kind"] = "construction"
        with self.assertRaisesRegex(ValueError, "local mathematical uncertainties"):
            r.validate_result(value, "T1", self.pair / "a")

    def test_evidence_escape_and_symlink(self):
        value = fixture_result()
        for path in ("../source.tex", "/etc/passwd", "evidence/../../source.tex", "evidence/../input/paper.txt"):
            value["evidence"] = [{"path": path, "description": "artifact"}]
            with self.assertRaises(ValueError):
                r.validate_result(value, "T1", self.pair / "a")
        evidence = self.pair / "a" / "evidence"
        evidence.mkdir()
        (evidence / "link.txt").symlink_to(self.paper)
        value["evidence"] = [{"path": "evidence/link.txt", "description": "artifact"}]
        with self.assertRaisesRegex(ValueError, "symlink"):
            r.validate_result(value, "T1", self.pair / "a")

    def test_evidence_hash_and_missing_file(self):
        value = fixture_result()
        value["evidence"] = [{"path": "evidence/matrix.txt", "description": "matrix"}]
        with self.assertRaisesRegex(ValueError, "missing evidence"):
            r.validate_result(value, "T1", self.pair / "a")
        evidence = self.pair / "a" / "evidence"
        evidence.mkdir()
        (evidence / "matrix.txt").write_text("[[0,1],[1,0]]")
        value["evidence"][0]["sha256"] = "incorrect"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            r.validate_result(value, "T1", self.pair / "a")

    def test_symlink_result_and_staged_directory(self):
        (self.root / "outside.json").write_bytes(r.dump(fixture_result()))
        (self.pair / "a" / "result.json").symlink_to(self.root / "outside.json")
        with self.assertRaisesRegex(ValueError, "symlink"):
            r.check_pair(self.pair)

    def test_plan_rejects_verdict_and_duplicate_targets(self):
        plan = copy.deepcopy(self.plan)
        plan["targets"][0]["verdict"] = "wrong"
        with self.assertRaisesRegex(ValueError, "unexpected fields"):
            r.validate_plan(plan)
        plan = copy.deepcopy(self.plan)
        plan["targets"] *= 2
        with self.assertRaisesRegex(ValueError, "duplicate"):
            r.validate_plan(plan)

    def test_partial_plan_requires_limitation(self):
        plan = copy.deepcopy(self.plan)
        plan["selection_status"] = "partial"
        with self.assertRaisesRegex(ValueError, "limitation"):
            r.validate_plan(plan)

    def create_review(self):
        self.write_results()
        evidence = self.pair / "a" / "evidence"
        evidence.mkdir()
        (evidence / "calculation.py").write_text("raise RuntimeError('must never be executed')\n")
        value = fixture_result()
        value["evidence"] = [{"path": "evidence/calculation.py", "description": "Independent calculation code"}]
        (self.pair / "a" / "result.json").write_bytes(r.dump(value))
        review = r.prepare_review(self.pair, self.root / "review")
        value = {
            "schema_version": "reconstruction-review.v1", "target_id": "T1", "status": "supported",
            "result_a_sha256": r.sha((review / "a" / "result.json").read_bytes()),
            "result_b_sha256": r.sha((review / "b" / "result.json").read_bytes()),
            "rationale": "Both derivations use the stated orientation and evaluate the determinant.",
            "checked_steps": ["Checked the ordered basis and recomputed 0*0-1*1=-1."],
            "unresolved_checks": [], "consequence": "The local determinant equals the claimed -1.",
        }
        (review / "review.json").write_bytes(r.dump(value))
        return review, value

    def test_review_stages_evidence_and_binds_results(self):
        review, value = self.create_review()
        self.assertEqual((review / "a" / "evidence" / "calculation.py").read_bytes(),
                         (self.pair / "a" / "evidence" / "calculation.py").read_bytes())
        result = r.check_review(review)
        self.assertEqual(result["status"], "structurally_valid")
        self.assertFalse(result["mathematical_correctness_established_by_validator"])
        value["result_a_sha256"] = "other"
        (review / "review.json").write_bytes(r.dump(value))
        with self.assertRaisesRegex(ValueError, "different worker"):
            r.check_review(review)

    def test_review_rechecks_generated_evidence(self):
        review, _ = self.create_review()
        (self.pair / "a" / "evidence" / "calculation.py").write_text("changed")
        with self.assertRaisesRegex(ValueError, "upstream plan input changed"):
            r.check_review(review)

    def test_review_does_not_complete_missing_or_unexplained_review(self):
        review, value = self.create_review()
        (review / "review.json").unlink()
        self.assertEqual(r.check_review(review)["status"], "incomplete")
        value["checked_steps"] = []
        (review / "review.json").write_bytes(r.dump(value))
        with self.assertRaisesRegex(ValueError, "checked steps"):
            r.check_review(review)
        value["status"] = "unresolved"
        (review / "review.json").write_bytes(r.dump(value))
        with self.assertRaisesRegex(ValueError, "explanation"):
            r.check_review(review)
        value["unresolved_checks"] = ["Cannot determine the intended ordered basis."]
        (review / "review.json").write_bytes(r.dump(value))
        self.assertEqual(r.check_review(review)["review_status"], "unresolved")

    def test_review_requires_complete_pair_and_fresh_directory(self):
        with self.assertRaisesRegex(ValueError, "both worker"):
            r.prepare_review(self.pair, self.root / "review")
        review, _ = self.create_review()
        with self.assertRaisesRegex(ValueError, "fresh"):
            r.prepare_review(self.pair, review)

    def test_untracked_input_evidence_is_rejected(self):
        self.write_results()
        (self.pair / "a" / "input" / "new.txt").write_text("Not an input snapshot.")
        value = fixture_result()
        value["evidence"] = [{"path": "input/new.txt", "description": "artifact"}]
        (self.pair / "a" / "result.json").write_bytes(r.dump(value))
        with self.assertRaisesRegex(ValueError, "hashed input snapshot"):
            r.check_pair(self.pair)


if __name__ == "__main__":
    unittest.main()
