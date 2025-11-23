-- 添加 role 列到 users 表
ALTER TABLE users ADD COLUMN role ENUM('USER', 'ADMIN', 'SUPER_ADMIN') BINARY CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT 'USER' NOT NULL AFTER password;

-- 更新现有管理员用户的角色
UPDATE users SET role = 'ADMIN' WHERE username = 'admin';

-- 确保所有角色值都是大写
UPDATE users SET role = 'USER' WHERE role = 'user';
UPDATE users SET role = 'ADMIN' WHERE role = 'admin';
UPDATE users SET role = 'SUPER_ADMIN' WHERE role = 'super_admin';