-- -----------------------------------------------------
-- Schema: test2
-- -----------------------------------------------------
-- 创建数据库（如果不存在）并使用
-- -----------------------------------------------------
CREATE DATABASE IF NOT EXISTS test2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE test2;
-- -----------------------------------------------------
-- Table: users
-- 功能: 存储用户的核心认证信息
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    status TINYINT DEFAULT 1 COMMENT '1:正常, 2:禁用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
-- 插入初始管理员账户（如果不存在）
INSERT INTO users (id, username, email, password, status) 
SELECT 1, 'admin', 'admin@qq.com', '$2y$12$Vu82CyfZGLHwcHZJsKjmAegmFmun3LARte83SpNd/Naih.K7krniy', 1
WHERE NOT EXISTS (SELECT 1 FROM users WHERE id = 1);
-- 重置自增ID，避免与手动插入的ID冲突
SET @max_id = (SELECT IFNULL(MAX(id), 0) FROM users);
SET @new_auto_increment = @max_id + 1;
SET @sql = CONCAT('ALTER TABLE users AUTO_INCREMENT = ', @new_auto_increment);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
-- 为常用查询字段创建索引（UNIQUE约束会自动创建索引，显式声明更清晰）
-- 如果索引不存在则创建
SET @index_exists = (SELECT COUNT(*) FROM information_schema.statistics 
                     WHERE table_schema = DATABASE() AND table_name = 'users' AND index_name = 'idx_users_username');
SET @sql = IF(@index_exists = 0, 'CREATE INDEX idx_users_username ON users(username)', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @index_exists = (SELECT COUNT(*) FROM information_schema.statistics 
                     WHERE table_schema = DATABASE() AND table_name = 'users' AND index_name = 'idx_users_email');
SET @sql = IF(@index_exists = 0, 'CREATE INDEX idx_users_email ON users(email)', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
-- -----------------------------------------------------
-- Table: user_profiles
-- 功能: 存储用户的资产、权益和状态，与users表一对一关系
-- (采纳了您的建议，将积分和权益信息分离)
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id BIGINT PRIMARY KEY,
    credits INT NOT NULL DEFAULT 0 COMMENT '当前积分余额',
    free_model1_usages INT NOT NULL DEFAULT 5 COMMENT '模型一的剩余免费使用次数',
    free_model2_usages INT NOT NULL DEFAULT 3 COMMENT '模型二的剩余免费使用次数',
    membership_type TINYINT NOT NULL DEFAULT 0 COMMENT '会员类型: 0-普通, 1-高级, 2-专业',
    membership_expires_at DATETIME NULL COMMENT '会员到期时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户档案与权益表';
-- 为管理员用户创建初始档案（如果不存在）
INSERT INTO user_profiles (user_id, credits, membership_type) 
SELECT 1, 1000, 2 
WHERE NOT EXISTS (SELECT 1 FROM user_profiles WHERE user_id = 1); -- 假设管理员有1000积分，是专业会员
-- -----------------------------------------------------
-- Table: credit_transactions
-- 功能: 记录所有积分的变动流水，用于审计和对账
-- (结合了流水表的设计，增强了系统的健壮性和可追溯性)
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS credit_transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    amount INT NOT NULL COMMENT '积分变动数量，正数为增加，负数为消耗',
    balance_after INT NOT NULL COMMENT '变动后的余额',
    source VARCHAR(50) NOT NULL COMMENT '积分来源/消耗原因，如: drawing_generation, purchase, daily_bonus',
    source_id BIGINT NULL COMMENT '关联的业务ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_credit_transactions_user_id (user_id),
    INDEX idx_credit_transactions_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='积分流水记录表';
-- 为userid为7的用户插入10条模拟积分变化数据

-- 1. 每日登录奖励 (+50积分)
INSERT INTO credit_transactions (user_id, amount, balance_after, source, source_id)
SELECT 7, 50, (SELECT credits FROM user_profiles WHERE user_id = 7) + 50, 'daily_bonus', NULL;

-- 更新用户积分余额
UPDATE user_profiles SET credits = credits + 50 WHERE user_id = 7;

-- 2. 生成图片消耗 (-20积分)
INSERT INTO credit_transactions (user_id, amount, balance_after, source, source_id)
SELECT 7, -20, (SELECT credits FROM user_profiles WHERE user_id = 7) - 20, 'drawing_generation', 101;

-- 更新用户积分余额
UPDATE user_profiles SET credits = credits - 20 WHERE user_id = 7;

-- 3. 购买会员 (+0积分，记录会员购买行为)
INSERT INTO credit_transactions (user_id, amount, balance_after, source, source_id)
SELECT 7, 0, (SELECT credits FROM user_profiles WHERE user_id = 7), 'purchase', 201;

-- 4. 每日登录奖励 (+50积分)
INSERT INTO credit_transactions (user_id, amount, balance_after, source, source_id)
SELECT 7, 50, (SELECT credits FROM user_profiles WHERE user_id = 7) + 50, 'daily_bonus', NULL;

-- 更新用户积分余额
UPDATE user_profiles SET credits = credits + 50 WHERE user_id = 7;

-- 5. 生成图片消耗 (-30积分)
INSERT INTO credit_transactions (user_id, amount, balance_after, source, source_id)
SELECT 7, -30, (SELECT credits FROM user_profiles WHERE user_id = 7) - 30, 'drawing_generation', 102;

-- 更新用户积分余额
UPDATE user_profiles SET credits = credits - 30 WHERE user_id = 7;

-- 6. 推荐奖励 (+100积分)
INSERT INTO credit_transactions (user_id, amount, balance_after, source, source_id)
SELECT 7, 100, (SELECT credits FROM user_profiles WHERE user_id = 7) + 100, 'referral_bonus', 301;

-- 更新用户积分余额
UPDATE user_profiles SET credits = credits + 100 WHERE user_id = 7;

-- 7. 生成图片消耗 (-25积分)
INSERT INTO credit_transactions (user_id, amount, balance_after, source, source_id)
SELECT 7, -25, (SELECT credits FROM user_profiles WHERE user_id = 7) - 25, 'drawing_generation', 103;

-- 更新用户积分余额
UPDATE user_profiles SET credits = credits - 25 WHERE user_id = 7;

-- 8. 系统补偿 (+200积分)
INSERT INTO credit_transactions (user_id, amount, balance_after, source, source_id)
SELECT 7, 200, (SELECT credits FROM user_profiles WHERE user_id = 7) + 200, 'system_compensation', 401;

-- 更新用户积分余额
UPDATE user_profiles SET credits = credits + 200 WHERE user_id = 7;

-- 9. 生成图片消耗 (-40积分)
INSERT INTO credit_transactions (user_id, amount, balance_after, source, source_id)
SELECT 7, -40, (SELECT credits FROM user_profiles WHERE user_id = 7) - 40, 'drawing_generation', 104;

-- 更新用户积分余额
UPDATE user_profiles SET credits = credits - 40 WHERE user_id = 7;

-- 10. 每日登录奖励 (+50积分)
INSERT INTO credit_transactions (user_id, amount, balance_after, source, source_id)
SELECT 7, 50, (SELECT credits FROM user_profiles WHERE user_id = 7) + 50, 'daily_bonus', NULL;

-- 更新用户积分余额
UPDATE user_profiles SET credits = credits + 50 WHERE user_id = 7;
-- -----------------------------------------------------

-- Table: payment_orders

-- 功能: 存储用户的支付订单信息，对接第三方支付平台ZPAY

-- -----------------------------------------------------

CREATE TABLE IF NOT EXISTS payment_orders (

id BIGINT AUTO_INCREMENT PRIMARY KEY,

user_id BIGINT NOT NULL COMMENT '用户ID，关联users表',

out_trade_no VARCHAR(64) NOT NULL UNIQUE COMMENT '商户订单号，系统内唯一',
pid VARCHAR(32) NOT NULL COMMENT '商户ID',

cid VARCHAR(32) NULL COMMENT '支付渠道ID（可选）',

type ENUM('alipay', 'wxpay') NOT NULL COMMENT '支付方式: alipay-支付宝, wxpay-微信支付',

notify_url VARCHAR(255) NOT NULL COMMENT '服务器异步通知地址',

name VARCHAR(127) NOT NULL COMMENT '商品名称',

money DECIMAL(10,2) NOT NULL COMMENT '订单金额，单位：元',

clientip VARCHAR(45) NOT NULL COMMENT '用户发起支付的IP地址',

param TEXT NULL COMMENT '业务扩展参数，支付后原样返回，用于关联具体业务',

sign VARCHAR(32) NOT NULL COMMENT '请求时的签名字符串',

sign_type VARCHAR(10) DEFAULT 'MD5' COMMENT '签名类型',

trade_no VARCHAR(64) NULL COMMENT 'ZPAY内部订单号（支付成功后返回）',

status TINYINT NOT NULL DEFAULT 0 COMMENT '订单状态: 0-待支付, 1-支付成功, 2-已关闭',

trade_status VARCHAR(32) NULL COMMENT '第三方支付状态，如TRADE_SUCCESS',

buyer VARCHAR(100) NULL COMMENT '支付者账号',

addtime DATETIME NULL COMMENT '创建订单时间（来自ZPAY）',

endtime DATETIME NULL COMMENT '完成交易时间（来自ZPAY）',

created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

INDEX idx_payment_orders_user_id (user_id),

INDEX idx_payment_orders_out_trade_no (out_trade_no),

INDEX idx_payment_orders_trade_no (trade_no),

INDEX idx_payment_orders_status (status)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支付订单表';
INSERT INTO payment_orders (
    user_id, 
    out_trade_no, 
    pid, 
    type, 
    notify_url, 
    name, 
    money, 
    clientip, 
    sign, 
    status,
    created_at,
    updated_at
) VALUES (
    1, 
    'ORD20231028001', 
    'MERCHANT001', 
    'alipay', 
    'https://your-domain.com/api/payment/notify', 
    '积分充值', 
    100.00, 
    '192.168.1.100', 
    'abc123def456', 
    1,
    NOW(),
    NOW()
);-- 添加多个测试支付订单
INSERT INTO payment_orders (user_id, out_trade_no, pid, type, notify_url, name, money, clientip, sign, status, created_at, updated_at) VALUES
(1, 'ORD20231028002', 'MERCHANT001', 'wxpay', 'https://your-domain.com/api/payment/notify', '会员升级', 299.00, '192.168.1.101', 'def456abc789', 1, NOW(), NOW()),
(7, 'ORD20231028003', 'MERCHANT001', 'alipay', 'https://your-domain.com/api/payment/notify', '积分充值', 50.00, '192.168.1.102', 'ghi789jkl012', 0, NOW(), NOW()),
(7, 'ORD20231028004', 'MERCHANT001', 'wxpay', 'https://your-domain.com/api/payment/notify', '积分充值', 200.00, '192.168.1.103', 'mno345pqr678', 1, NOW(), NOW()),
(1, 'ORD20231028005', 'MERCHANT001', 'alipay', 'https://your-domain.com/api/payment/notify', '会员升级', 299.00, '192.168.1.104', 'stu901vwx234', 2, NOW(), NOW());
-- -----------------------------------------------------
-- Table: image_generation_tasks
-- 功能: 存储用户提交的所有图像生成任务
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS image_generation_tasks (
    id VARCHAR(50) PRIMARY KEY COMMENT '任务唯一ID，业务生成',
    user_id BIGINT NOT NULL COMMENT '提交任务的用户ID',
    model VARCHAR(50) NOT NULL COMMENT '使用的模型名称，如sdxl、midjourney等',
    prompt TEXT NOT NULL COMMENT '用户输入的生成提示词',
    size VARCHAR(20) NOT NULL COMMENT '生成图片尺寸，如1024x768',
    status ENUM('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED') DEFAULT 'PENDING' COMMENT '任务状态：待处理、处理中、成功、失败',
    image_url VARCHAR(500) COMMENT '生成图片的访问地址',
    error_message TEXT COMMENT '失败时的错误信息',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '任务创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '任务最后更新时间',
    credits_used INT NOT NULL COMMENT '本次任务消耗的积分数',
    reference_images JSON COMMENT '用户上传的参考图信息，JSON格式',
    meta_data JSON COMMENT '扩展字段，存储其他业务元数据',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_image_tasks_user_id (user_id),
    INDEX idx_image_tasks_status (status),
    INDEX idx_image_tasks_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='图像生成任务表';