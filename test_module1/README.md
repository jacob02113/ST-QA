# 模块一自动化测试

本目录包含视频切分、训练数据格式转换和评估指标计算三个模块的自动化测试，共 33 条测试用例。

## 环境要求

- Python 3.9 或更高版本
- pip

## 统一测试环境

模块一和模块二共用根目录的 `requirements-test.txt` 和 `.venv-test`。以下命令均在仓库根目录执行：

```bash
python3 -m venv .venv-test
source .venv-test/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-test.txt
```

Windows PowerShell 使用以下命令激活虚拟环境：

```powershell
.venv-test\Scripts\Activate.ps1
```

## 运行模块一和模块二

```bash
python -m pytest test_module1 test_module2 -v
```

## 运行单个测试文件

```bash
python -m pytest test_module1/test_video_split.py -v
python -m pytest test_module1/test_convert.py -v
python -m pytest test_module1/test_eval.py -v
```

只运行模块一：

```bash
python -m pytest test_module1 -v
```
## 测试说明

测试使用 `tmp_path` 和模拟对象隔离临时文件、视频读写等外部操作，不需要下载数据集或准备真实视频文件。

当前被测版本中，用例 007 用于暴露缺少 `question_id` 时校验时序不当的缺陷，用例 024、025 和 026 用于暴露评分范围校验及不安全解析相关缺陷；对应代码修复前，这些用例会显示为失败。
