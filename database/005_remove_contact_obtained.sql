-- 移除 visit_feedback 表中冗余的 contact_obtained 字段
-- has_business_card 和 has_contact_info 已覆盖其语义

ALTER TABLE visit_feedback DROP COLUMN IF EXISTS contact_obtained;
