import csv
import importlib.util
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FILE = PROJECT_ROOT / "finetune" / "convert.py"
SPEC = importlib.util.spec_from_file_location("convert", FILE)
convert = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(convert)


def write_csv(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def base_row():
    return {"question_id": "q1", "question": "What is here?", "answer0": "a0",
            "answer1": "", "answer2": "", "answer3": ""}


def test_008(tmp_path):
    # 测试用例008：llava模式生成图像标签和字符串编号
    source, output = tmp_path / "a.csv", tmp_path / "out" / "a.json"
    write_csv(source, list(base_row()), [base_row()])
    convert.convert_csv(source, output, "llava")
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data[0]["id"] == "0" and "<image>" in data[0]["conversations"][0]["value"]


def test_009(tmp_path):
    # 测试用例009：qwen模式生成视频标签且不生成编号
    source, output = tmp_path / "a.csv", tmp_path / "a.json"
    write_csv(source, list(base_row()), [base_row()])
    convert.convert_csv(source, output, "qwen")
    data = json.loads(output.read_text(encoding="utf-8"))[0]
    assert "<video>" in data["conversations"][0]["value"] and "id" not in data


def test_010(tmp_path):
    # 测试用例010：internvl模式逐行生成合法JSONL
    source, output = tmp_path / "a.csv", tmp_path / "a.jsonl"
    write_csv(source, list(base_row()), [base_row()])
    convert.convert_csv(source, output, "internvl")
    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["id"] == 0


def test_011(tmp_path):
    # 测试用例011：四个非空答案全部转换为空间记录
    source, output = tmp_path / "a.csv", tmp_path / "a.json"
    row = base_row()
    row.update(answer1="a1", answer2="a2", answer3="a3")
    write_csv(source, list(row), [row])
    convert.convert_csv(source, output, "qwen")
    assert len(json.loads(output.read_text(encoding="utf-8"))) == 4


def test_012(tmp_path):
    # 测试用例012：空答案和空白答案不产生记录
    source, output = tmp_path / "a.csv", tmp_path / "a.json"
    row = base_row()
    row.update(answer0=" ", answer1="", answer2="  ", answer3="ok")
    write_csv(source, list(row), [row])
    convert.convert_csv(source, output, "qwen")
    assert len(json.loads(output.read_text(encoding="utf-8"))) == 1


def test_013(tmp_path):
    # 测试用例013：特殊字符和中文答案保持原文
    source, output = tmp_path / "a.csv", tmp_path / "a.json"
    row = base_row()
    row["answer0"] = "中文、引号\"和换行"
    write_csv(source, list(row), [row])
    convert.convert_csv(source, output, "qwen")
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data[0]["conversations"][1]["value"] == row["answer0"]


def test_014(tmp_path):
    # 测试用例014：输出目录不存在时自动创建
    source, output = tmp_path / "a.csv", tmp_path / "new" / "deep" / "a.json"
    write_csv(source, list(base_row()), [base_row()])
    convert.convert_csv(source, output, "qwen")
    assert output.exists()


def test_015(tmp_path):
    # 测试用例015：空CSV能够生成空JSON数组
    source, output = tmp_path / "a.csv", tmp_path / "a.json"
    write_csv(source, list(base_row()), [])
    convert.convert_csv(source, output, "qwen")
    assert json.loads(output.read_text(encoding="utf-8")) == []
