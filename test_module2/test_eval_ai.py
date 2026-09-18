import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FILE = PROJECT_ROOT / "eval.py"
SPEC = importlib.util.spec_from_file_location("eval_module_ai", FILE)
eval_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eval_module)


def write_metric_inputs(tmp_path, results, question_ids=None, types=None, nested=False):
    """Write a CSV + results fixture and return the generated metrics payload."""
    question_ids = question_ids or ["q1", "q2"]
    types = types or ["scene", "action"]
    csv_path = tmp_path / "test.csv"
    json_path = tmp_path / "results.json"
    output_path = tmp_path / "nested" / "metrics.json" if nested else tmp_path / "metrics.json"

    pd.DataFrame({"question_id": question_ids, "type": types}).to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(results), encoding="utf-8")
    eval_module.calculate_metrics(csv_path, json_path, output_path)
    return output_path, json.loads(output_path.read_text(encoding="utf-8"))


def qa(pred="answer"):
    """Return a representative QA object used across cache and scoring tests."""
    return {
        "q": "What is ahead?",
        "a0": "a door",
        "a1": "",
        "a2": "",
        "a3": "",
        "type": "navigation",
        "pred": pred,
    }


def write_cache_result(tmp_path, question_id, payload):
    """Persist a synthetic cached result using the production filename convention."""
    result_path = tmp_path / eval_module.result_filename(question_id)
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    return result_path


def test_ai_201_loads_valid_jsonl(tmp_path):
    path = tmp_path / "pred.jsonl"
    path.write_text('{"question_id":"q1","pred":"door"}\n', encoding="utf-8")
    assert eval_module.load_predictions(path) == [{"question_id": "q1", "pred": "door"}]


def test_ai_202_ignores_blank_jsonl_lines(tmp_path):
    path = tmp_path / "pred.jsonl"
    path.write_text('\n  \n{"question_id":"q1","pred":"door"}\n', encoding="utf-8")
    assert len(eval_module.load_predictions(path)) == 1


def test_ai_203_rejects_python_expression_in_prediction_file(tmp_path):
    path = tmp_path / "pred.jsonl"
    path.write_text('__import__("os").getcwd()\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        eval_module.load_predictions(path)


def test_ai_204_rejects_non_object_prediction(tmp_path):
    path = tmp_path / "pred.jsonl"
    path.write_text('["q1", "door"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        eval_module.load_predictions(path)


def test_ai_205_rejects_prediction_without_required_fields(tmp_path):
    path = tmp_path / "pred.jsonl"
    path.write_text('{"question_id":"q1"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="question_id and pred"):
        eval_module.load_predictions(path)


def test_ai_206_clamps_score_above_upper_bound():
    assert eval_module.normalize_score(6) == 5.0


def test_ai_207_clamps_score_below_lower_bound():
    assert eval_module.normalize_score(-1) == 0.0


def test_ai_208_maps_non_numeric_score_to_zero():
    assert eval_module.normalize_score("bad") == 0.0


def test_ai_209_maps_nan_score_to_zero():
    assert eval_module.normalize_score(float("nan")) == 0.0


def test_ai_210_maps_infinite_score_to_zero():
    assert eval_module.normalize_score(float("inf")) == 0.0


def test_ai_211_normalizes_prediction_whitespace_and_case(tmp_path):
    _, result = write_metric_inputs(tmp_path, {"q1": [{"pred": " YES ", "score": 4}]})
    assert result["scene"]["accuracy"] == 1.0


def test_ai_212_skips_empty_result_entries(tmp_path):
    _, result = write_metric_inputs(tmp_path, {"q1": []})
    assert result["total"]["total"] == 0


def test_ai_213_matches_numeric_question_ids_as_strings(tmp_path):
    _, result = write_metric_inputs(
        tmp_path,
        {"101": [{"pred": "yes", "score": 5}]},
        question_ids=[101, 102],
    )
    assert result["scene"]["total"] == 1


def test_ai_214_skips_question_with_missing_type(tmp_path):
    _, result = write_metric_inputs(
        tmp_path,
        {"q1": [{"pred": "yes", "score": 5}]},
        types=[None, "action"],
    )
    assert result["total"]["total"] == 0


def test_ai_215_creates_metrics_output_directory(tmp_path):
    output_path, _ = write_metric_inputs(tmp_path, {}, nested=True)
    assert output_path.exists()


def test_ai_216_generates_path_safe_cache_filename():
    filename = eval_module.result_filename("../../outside/q.1")
    assert filename.endswith(".json") and "/" not in filename and ".." not in filename


def test_ai_217_accepts_cache_for_identical_input(tmp_path):
    current = qa()
    result_path = write_cache_result(tmp_path, "q1", [{"pred": "yes", "score": 5}, current])
    assert eval_module.cache_matches(result_path, current)


def test_ai_218_invalidates_cache_when_prediction_changes(tmp_path):
    result_path = write_cache_result(tmp_path, "q1", [{"pred": "yes", "score": 5}, qa("old")])
    assert not eval_module.cache_matches(result_path, qa("new"))


def test_ai_219_collects_only_current_run_results(tmp_path):
    current = {"q.1": qa()}
    expected_path = write_cache_result(tmp_path, "q.1", [{"pred": "yes", "score": 5}, current["q.1"]])
    (tmp_path / "stale.json").write_text(json.dumps([{"pred": "yes", "score": 5}, qa("stale")]), encoding="utf-8")
    combined = eval_module.collect_results(tmp_path, current)
    assert list(combined) == ["q.1"]
    assert list(combined["q.1"]) == [{"pred": "yes", "score": 5}, current["q.1"]]
    assert expected_path.exists()


def test_ai_220_scores_with_timeout_and_normalizes_response(tmp_path):
    response = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": '```json\n{"pred":" YES ","score":6}\n```'}}]
    }
    with patch.object(eval_module.requests, "post", return_value=response) as request:
        eval_module.GPT_Score("q1", qa(), tmp_path)

    response.raise_for_status.assert_called_once_with()
    assert request.call_args.kwargs["timeout"] == 30
    output = json.loads((tmp_path / eval_module.result_filename("q1")).read_text(encoding="utf-8"))
    assert output[0] == {"pred": "yes", "score": 5.0}
