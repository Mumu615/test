import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.config import settings
import logging
import asyncio

logger = logging.getLogger(__name__)

async def send_verification_code(email: str, code: str) -> bool:
    """异步发送邮件（在后台线程中运行）"""
    def _send():
        try:
            # 检查邮件配置是否完整
            if not all([settings.EMAIL_ADDRESS, settings.EMAIL_PASSWORD, settings.SMTP_SERVER]):
                logger.warning("邮件配置缺失，跳过发送")
                return False
                
            logger.info(f"开始发送邮件到 {email}")
            logger.info(f"SMTP服务器: {settings.SMTP_SERVER}:{settings.SMTP_PORT}")
            logger.info(f"发件人邮箱: {settings.EMAIL_ADDRESS}")
            
            msg = MIMEMultipart()
            msg["From"] = settings.EMAIL_ADDRESS
            msg["To"] = email
            msg["Subject"] = "验证码"

            body = f"您的验证码是：{code}，5分钟内有效。"
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # 连接SMTP服务器
            logger.info("正在连接SMTP服务器...")
            server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
            
            # 启用调试模式
            server.set_debuglevel(1)
            
            # 启动TLS加密
            logger.info("启动TLS加密...")
            server.starttls()
            
            # 登录
            logger.info("正在登录...")
            server.login(settings.EMAIL_ADDRESS, settings.EMAIL_PASSWORD)
            
            # 发送邮件
            logger.info("正在发送邮件...")
            text = msg.as_string()
            server.sendmail(settings.EMAIL_ADDRESS, email, text)
            
            # 关闭连接
            server.quit()
            logger.info("邮件发送成功")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP认证失败: {e}")
            logger.error("请检查邮箱地址和授权码是否正确")
            return False
        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP连接失败: {e}")
            logger.error("无法连接到SMTP服务器，请检查网络连接和服务器地址")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP错误: {e}")
            return False
        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
            return False

    # 在线程池中运行阻塞的 SMTP 操作
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send)


# 为保持向后兼容，创建一个别名
send_verification_code_async = send_verification_code
