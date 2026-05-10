# Analyses

这个目录用于保存可重复的大样本分析产物。

和其他输出目录的区别：

- `outputs/runs/`
  - 原始 pipeline 分阶段产物
- `outputs/reviews/`
  - 给人工筛查的 shortlist、图片和表
- `outputs/sites/`
  - 可浏览的网站
- `outputs/reports/`
  - 面向结论汇报的 Markdown / JSON / 幻灯片等
- `outputs/analyses/`
  - 面向研究问题本身的结构化分析结果

推荐结构：

```text
outputs/analyses/<analysis_id>/
  <analysis_family>/
    tables/
    figures/
    metadata/
```
