import logging
import os
import sys

from manager.ConfigManager import ConfigManager
from step.clockIn import clock_in
from step.fetchPlan import fetch_plan
from step.login import login
from manager.UserInfoManager import UserInfoManager
from step.sendEmail import send_email
from util.HelperFunctions import mask_sensitive

# ======================
# 日志配置
# ======================
log_file = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "main.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),  # 写入日志文件
        logging.StreamHandler(sys.stdout)  # 控制台输出
    ]
)


def execute_tasks():
    # 登录
    isLogin = login()
    if not isLogin:
        logging.warning("登录失败")
        return
    logging.info(f"用户数据：{mask_sensitive(UserInfoManager.load())}")
    logging.info(f"用户类型：{UserInfoManager.get('roleKey')}")
    if UserInfoManager.get("userType") != "student":
        logging.warning("当前用户不是学生，结束执行打卡任务")
        return
    # 获取打卡信息
    hasPlan = fetch_plan()
    if not hasPlan:
        logging.warning("未获取到打卡信息")
        return
    # 执行打卡
    str = clock_in()
    logging.info(str)
    # 发送邮件通知
    if ConfigManager.get("smtp", "enable"):
        try:
            send_email(str["title"], str["content"])
            logging.info("邮件发送成功")
        except Exception as e:
            logging.error(f"邮件发送失败: {e}")
            # 邮件发送失败不影响打卡流程


if __name__ == '__main__':
    execute_tasks()
