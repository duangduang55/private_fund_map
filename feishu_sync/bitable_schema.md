# 飞书多维表格 → n8n → Postgres 同步方案

## 飞书多维表格字段设计

| # | 字段名 | 类型 | 必填 | 映射到 Postgres | 备注 |
|---|--------|------|------|----------------|------|
| 1 | **机构名称** | 文本 | 是 | `visit_plans.org_name` | |
| 2 | **登记编号 (reg_num)** | 文本 | 否 | `visit_plans.reg_num` | 不填时 n8n 自动从 ts_quant_db 按名称匹配 |
| 3 | **拜访日期** | 日期 | 是 | `visit_plans.planned_date` / `visit_feedback.visit_date` | 实际拜访日期 |
| 4 | **拜访人** | 文本 | 是 | `visit_plans.visitor_name` / `visit_feedback.visitor_name` | 谁去的 |
| 5 | **拜访状态** | 单选 | 是 | `visit_feedback.visit_status` | 选项：成功/未见到/已搬迁/地址有误/其他 |
| 6 | **沟通摘要** | 多行文本 | 否 | `visit_feedback.summary` | 简要总结 |
| 7 | **沟通详情** | 多行文本 | 否 | `visit_feedback.communication_detail` | 详细沟通内容 |
| 8 | **是否有名片** | 复选框 | 否 | `visit_feedback.has_business_card` | |
| 9 | **跟进建议** | 多行文本 | 否 | `visit_feedback.follow_up_suggestions` | |
| 11 | **标签** | 多选 | 否 | `visit_feedback.tags` | 自定义标签 |
| 12 | **办公地址** | 文本 | 否 | `visit_plans.office_address` | n8n 自动从 ts_quant_db 补全 |
| 13 | **管理规模** | 文本 | 否 | `visit_plans.org_aum` | n8n 自动补全 |
| 14 | **提交人** | 创建人 | 自动 | — | 飞书自动记录 |
| 15 | **同步状态** | 单选 | 自动 | — | 选项：未同步/已同步/失败，默认"未同步" |
| 16 | **同步日志** | 多行文本 | 自动 | — | n8n 写入同步结果 |

## 工作流程

```
         飞书表单                       飞书 Open API                      本地 Postgres
同事 ──────────→ 飞书多维表格 ────→  n8n 定时轮询  ──────────→  fund_map_db
                   ↑                   每 5 分钟                        ↑
                   │                                                     │
             自动创建（无代码）          查同步状态=未同步 → 处理        INSERT visit_plans
                   │                  → 标记已同步                     INSERT visit_feedback
                                                                      SELECT ts_quant_db 补全数据
```

## 同步规则（n8n 逻辑）

1. 查询所有 `同步状态 = "未同步"` 的记录
2. 对每条记录：
   a. 如果 `登记编号` 为空，从 `ts_quant_db.private_fund_list` 按 `org_name` 模糊匹配
   b. 从 `ts_quant_db.private_fund_list` 补全 `office_address`、`org_aum` 等
   c. 写入 `visit_plans`（status='completed'，user_id=飞书同步专用账号）
   d. 写入 `visit_feedback`（关联 visit_plan_id）
   e. 标记 `同步状态 = "已同步"`，写入 `同步日志`
3. 出错时标记 `同步状态 = "失败"`，记录错误信息到 `同步日志`
