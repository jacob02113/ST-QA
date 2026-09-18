# 模块二 AI 辅助测试

本目录包含 20 条由 AI 辅助设计并经人工审核的自动化测试，覆盖评估结果解析、异常分值处理以及跨轮次缓存隔离等关键场景。测试全部基于临时文件和 Mock 实现，不会调用真实评分接口。

## 统一测试环境

模块一和模块二共用仓库根目录下的 `requirements-test.txt` 和 `.venv-test`。在仓库根目录执行：

```bash
python3 -m venv .venv-test
source .venv-test/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-test.txt
```

在 Windows PowerShell 中使用：

```powershell
.venv-test\Scripts\Activate.ps1
python -m pip install -r requirements-test.txt
```

## 一键运行

运行模块一和模块二：

```bash
python -m pytest test_module1 test_module2 -v
```

仅运行模块二：

```bash
python -m pytest test_module2 -v
```

## 测试范围

- JSONL 预测文件的安全解析与字段校验
- 分数上下限、非数字值以及非有限值的规范化处理
- 问题编号、题型和空结果的输入鲁棒性验证
- 评分缓存命名、命中、失效和本轮结果隔离
- 评分接口超时参数与返回内容统一规范化

## 关键缺陷说明

主缺陷 D2-001 为评估缓存状态污染。旧实现仅按文件名判断缓存是否存在，并遍历结果目录汇总所有 JSON，因此在修改预测内容或减少题目数量后，旧评分仍可能混入新一轮指标。修复后，程序会对比缓存中的完整问答输入，仅汇总当前预测集合对应的有效缓存项，确保指标结果与本轮数据保持一致。
