# 模块二 AI 辅助测试

本目录包含 20 条由 AI 辅助设计并经人工审核的自动化测试，重点验证评估结果解析、异常评分处理和跨轮次缓存隔离。测试全部使用临时文件与 Mock，不会调用真实评分接口。

## 环境配置

在仓库根目录执行：

```bash
python3 -m venv .venv-module2
source .venv-module2/bin/activate
python -m pip install -r test_module2_ai/requirements.txt
```

Windows PowerShell 使用：

```powershell
.venv-module2\Scripts\Activate.ps1
python -m pip install -r test_module2_ai/requirements.txt
```

## 一键运行

```bash
python -m pytest test_module1 test_module2_ai -v
```

只运行模块二：

```bash
python -m pytest test_module2_ai -v
```

## 测试范围

- JSONL 预测文件的安全解析与字段校验
- 评分范围、非数字值和非有限值处理
- 问题编号、题型及空结果的输入鲁棒性
- 评分缓存命名、命中、失效和本轮结果隔离
- 评分接口超时参数及返回内容规范化

主缺陷 D2-001 为评估缓存状态污染。旧实现只按文件名判断缓存是否存在，并遍历结果目录汇总所有 JSON，因此修改预测内容或减少问题后，旧评分仍可能进入新一轮指标。修复后，程序比较缓存中的完整问答输入，仅汇总当前预测集合对应的有效缓存。
