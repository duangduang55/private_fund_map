-- 添加 super_admin 角色
-- 将 role 从 2 级（admin/member）扩展为 3 级（super_admin/admin/member）
-- 并将现有 admin 升级为 super_admin

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
  CHECK (role IN ('super_admin', 'admin', 'member'));

-- 升级现有 admin 账号为 super_admin
UPDATE users SET role = 'super_admin' WHERE role = 'admin';
