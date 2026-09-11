import importlib.util
import json
from pathlib import Path

import pandas as pd

FILE = Path(__file__).parent / "eval.py"
SPEC = importlib.util.spec_from_file_location("eval_module", FILE)
eval_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eval_module)


def run_metrics(tmp_path, predictions, types=None):
    types = types or ["scene", "action"]
    csv_path = tmp_path / "test.csv"
    json_path = tmp_path / "results.json"
    output_path = tmp_path / "metrics.json"
    pd.DataFrame({"question_id": ["q1", "q2"], "type": types}).to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(predictions), encoding="utf-8")
    eval_module.calculate_metrics(csv_path, json_path, output_path)
    return json.loads(output_path.read_text(encoding="utf-8"))


def test_016(tmp_path):
    # 测试用例016：正确预测计算准确率和平均分
    result = run_metrics(tmp_path, {"q1": [{"pred": "yes", "score": 5}]})
    assert result["scene"]["accuracy"] == 1.0


def test_017(tmp_path):
    # 测试用例017：未知问题编号被跳过
    result = run_metrics(tmp_path, {"qx": [{"pred": "yes", "score": 5}]})
    assert result["total"]["total"] == 0


def test_018(tmp_path):
    # 测试用例018：非标准预测文本按否处理
    result = run_metrics(tmp_path, {"q1": [{"pred": "maybe", "score": 2}]})
    assert result["scene"]["accuracy"] == 0.0


def test_019(tmp_path):
    # 测试用例019：预测文本大小写不影响yes判断
    result = run_metrics(tmp_path, {"q1": [{"pred": "YES", "score": 4}]})
    assert result["scene"]["accuracy"] == 1.0


def test_020(tmp_path):
    # 测试用例020：缺少预测项时统计结果仍可生成
    assert run_metrics(tmp_path, {})["total"]["total"] == 0


def test_021(tmp_path):
    # 测试用例021：零分预测能够参与平均分计算
    assert run_metrics(tmp_path, {"q1": [{"pred": "no", "score": 0}]})["scene"]["average_score"] == 0


def test_022(tmp_path):
    # 测试用例022：多个类型分别统计
    result = run_metrics(tmp_path, {"q1": [{"pred": "yes", "score": 5}], "q2": [{"pred": "no", "score": 1}]})
    assert result["scene"]["total"] == 1 and result["action"]["total"] == 1


def test_023(tmp_path):
    # 测试用例023：空结果生成total统计
    assert "total" in run_metrics(tmp_path, {})


def test_024(tmp_path):
    # 测试用例024：超过5分的结果应被拒绝
    assert run_metrics(tmp_path, {"q1": [{"pred": "yes", "score": 6}]})["scene"]["average_score"] <= 5


def test_025(tmp_path):
    # 测试用例025：负分结果应被拒绝
    assert run_metrics(tmp_path, {"q1": [{"pred": "no", "score": -1}]})["scene"]["average_score"] >= 0


def test_026():
    # 测试用例026：评估入口不应使用不安全的eval
    assert "eval(line.strip())" not in FILE.read_text(encoding="utf-8")


def test_027(tmp_path):
    # 测试用例027：浮点分数能够正确保留
    assert run_metrics(tmp_path, {"q1": [{"pred": "yes", "score": 3.5}]})["scene"]["average_score"] == 3.5


def test_028(tmp_path):
    # 测试用例028：未知类型仍应形成独立统计项
    result = run_metrics(tmp_path, {"q1": [{"pred": "yes", "score": 3}]}, ["new.type", "action"])
    assert "new.type" in result


def test_029(tmp_path):
    # 测试用例029：缺少score字段按零分处理
    assert run_metrics(tmp_path, {"q1": [{"pred": "yes"}]})["scene"]["average_score"] == 0


def test_030(tmp_path):
    # 测试用例030：空pred字段按否处理
    assert run_metrics(tmp_path, {"q1": [{"score": 2}]})["scene"]["accuracy"] == 0


def test_031(tmp_path):
    # 测试用例031：多个样本的平均分计算正确
    result = run_metrics(tmp_path, {"q1": [{"pred": "yes", "score": 4}], "q2": [{"pred": "yes", "score": 2}]})
    assert result["total"]["average_score"] == 3


def test_032(tmp_path):
    # 测试用例032：类型名称首尾空格和句点应规范化
    result = run_metrics(tmp_path, {"q1": [{"pred": "yes", "score": 2}]}, [" Scene. ", "action"])
    assert "scene" in result


def test_033(tmp_path):
    # 测试用例033：输出结果包含总体total字段
    assert run_metrics(tmp_path, {"q1": [{"pred": "yes", "score": 2}]})["total"]["total"] == 1
