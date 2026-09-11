# 模块一自动化测试

本目录包含视频切分、训练数据格式转换和评估指标计算三个模块的自动化测试，共 33 条测试用例。

## 环境要求

- Python 3.9 或更高版本
- pip

## 安装测试环境

以下命令均在仓库根目录执行：

```bash
python3 -m venv .venv-module1
source .venv-module1/bin/activate
python -m pip install --upgrade pip
python -m pip install -r test_module1/requirements.txt
```

Windows PowerShell 使用以下命令激活虚拟环境：

```powershell
.venv-module1\Scripts\Activate.ps1
```

## 运行全部测试

```bash
python -m pytest test_module1 -v
```

## 运行单个测试文件

```bash
python -m pytest test_module1/test_video_split.py -v
python -m pytest test_module1/test_convert.py -v
python -m pytest test_module1/test_eval.py -v
```

测试使用 `tmp_path` 和模拟对象隔离临时文件、视频读写等外部操作，不需要下载数据集或准备真实视频文件。

当前被测版本中，用例 024、025 和 026 用于暴露评分范围校验及不安全解析相关缺陷；对应代码修复前，这些用例会显示为失败。
