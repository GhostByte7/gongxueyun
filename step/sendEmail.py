import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

from manager.ConfigManager import ConfigManager


import logging

def send_email(title, content):
    try:
        to_emails = ConfigManager.get("smtp", "to")
        smtp_host = ConfigManager.get("smtp", "host")
        smtp_port = ConfigManager.get("smtp", "port")
        smtp_username = ConfigManager.get("smtp", "username")
        smtp_password = ConfigManager.get("smtp", "password")
        
        logging.info(f"准备发送邮件到: {to_emails}")
        logging.info(f"SMTP配置: host={smtp_host}, port={smtp_port}, username={smtp_username}")

        for to_email in to_emails:
            # 设置 MIMEText 对象
            message = MIMEText(content, 'plain', 'utf-8')
            message['Subject'] = Header(title, 'utf-8')
            from_header = Header(ConfigManager.get("smtp", "from"), 'utf-8')
            message['From'] = formataddr((str(from_header), smtp_username))
            message['To'] = to_email

            # 连接到 SMTP 服务器
            logging.info(f"正在连接到 SMTP 服务器: {smtp_host}:{smtp_port}")
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
            logging.info(f"SMTP服务器连接成功: {smtp_host}:{smtp_port}")
            
            # 登录到邮箱账户
            logging.info(f"正在登录邮箱: {smtp_username}")
            server.login(smtp_username, smtp_password)
            logging.info("邮箱登录成功")
            
            # 发送邮件
            logging.info(f"正在发送邮件到: {to_email}")
            server.sendmail(smtp_username, to_email, message.as_string())
            logging.info(f"邮件发送成功到: {to_email}")
            
            # 关闭连接
            server.quit()
            logging.info("SMTP连接已关闭")
            
    except Exception as e:
        logging.error(f"发送邮件失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise
