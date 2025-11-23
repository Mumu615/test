-- 修复取消订单时的唯一约束冲突问题
-- 删除原有的复合唯一索引
DROP INDEX idx_payment_orders_user_status_minute ON payment_orders;

-- 创建新的复合唯一索引，只针对待支付状态的订单
-- 使用DATE_FORMAT函数将created_at格式化为年月日时分的字符串，确保同一分钟内的唯一性
CREATE UNIQUE INDEX idx_payment_orders_user_status_pending ON payment_orders(
    user_id, 
    DATE_FORMAT(created_at, '%Y-%m-%d %H:%i')
) COMMENT '防止用户在同一分钟内创建多个待支付订单';

-- 添加部分唯一索引，只对status=0的记录生效
CREATE UNIQUE INDEX idx_payment_orders_user_pending ON payment_orders(
    user_id, 
    created_at
) WHERE status = 0 COMMENT '防止用户在同一分钟内创建多个待支付订单（部分索引）';