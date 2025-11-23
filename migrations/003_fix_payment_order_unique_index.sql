-- 修复支付订单唯一索引问题
-- 当前问题：用户不能有多个相同状态的订单（包括已关闭状态）
-- 业务需求：用户可以有多个已关闭状态的订单，但不能有多个待支付状态的订单

-- 1. 删除现有的唯一索引
DROP INDEX idx_payment_orders_user_status ON payment_orders;

-- 2. 添加一个计算列，对于待支付订单(status=0)设置为0，其他设置为唯一ID
-- 这样可以确保每个用户只能有一个待支付订单
ALTER TABLE payment_orders ADD COLUMN unique_pending_flag INT NOT NULL DEFAULT 0;
UPDATE payment_orders SET unique_pending_flag = 0 WHERE status = 0;
UPDATE payment_orders SET unique_pending_flag = id WHERE status != 0;

-- 3. 创建新的唯一索引，只针对待支付状态的订单
CREATE UNIQUE INDEX idx_payment_orders_user_pending ON payment_orders(
    user_id, 
    unique_pending_flag
) COMMENT '防止用户创建多个待支付订单';

-- 4. 添加普通索引，优化查询性能
CREATE INDEX idx_payment_orders_user_status ON payment_orders(
    user_id, status
) COMMENT '优化用户订单查询';