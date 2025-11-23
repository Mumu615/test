-- 创建新的复合唯一索引
-- 使用DATE_FORMAT函数将created_at格式化为年月日时分的字符串，确保同一分钟内的唯一性
CREATE UNIQUE INDEX idx_payment_orders_user_status_minute ON payment_orders(
    user_id, 
    status, 
    DATE_FORMAT(created_at, '%Y-%m-%d %H:%i')
) COMMENT '防止用户在同一分钟内创建多个相同状态的订单';