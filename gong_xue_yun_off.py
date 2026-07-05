import gc
import logging
import random
import time
from datetime import datetime

import schedule  # pip install schedule

from main import execute_tasks
from manager.ConfigManager import ConfigManager
from util.HelperFunctions import is_workday_realtime

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def should_run_today_off() -> bool:
    """
    根据下班打卡配置判断今日是否需要执行任务。
    支持三种模式：weekday（法定工作日）、everyday（每天）、customize（自定义）。
    """
    # 如果开启了法定工作日打卡，则每天都要执行任务
    if ConfigManager.get("clockInOff", "holidaysClockIn"):
        return True

    mode = ConfigManager.get("clockInOff", "mode")

    # 1. 法定工作日模式
    if mode == "weekday":
        return is_workday_realtime()

    # 2. 每天执行
    if mode == "everyday":
        return True

    # 3. 自定义模式
    if mode == "customize":
        custom_days = ConfigManager.get("clockInOff", "customDays", default=[])
        today = datetime.today().weekday() + 1  # 1=星期一, 7=星期天
        return today in custom_days

    # 其他情况，默认不执行
    return False


def generate_random_time_off() -> datetime:
    """
    生成一个随机的下班打卡时间

    该函数根据配置文件中的下班打卡时间范围，生成一个在指定时间基础上增加随机分钟数的打卡时间。
    随机分钟数的上限由配置决定，最终返回今天的具体打卡时间点。

    Returns:
        datetime: 今天的一个datetime对象，表示计划打卡的具体时间（秒和微秒都设为0）
    """
    # 生成一个随机分钟数
    float_minute = ConfigManager.get("clockInOff", "time", "float", default=1)
    random_minutes = random.randint(0, float_minute)

    # 获取配置的下班打卡时间
    start_time_str = ConfigManager.get("clockInOff", "time", "start", default="18:00")
    config_time = datetime.strptime(start_time_str, "%H:%M")

    # 获取小时和分钟
    hour = config_time.hour
    minute = config_time.minute + random_minutes

    # 处理分钟进位
    if minute >= 60:
        hour += 1
        minute -= 60

    # 返回计划打卡时间
    return datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)


def schedule_tasks():
    """为今天设置下班打卡计划任务"""
    schedule.clear()

    if should_run_today_off():
        execution_time = generate_random_time_off()
        logging.info(
            f"\n-------------今日计划下班打卡时间: {execution_time.strftime('%H:%M')}-------------\n")
        schedule.every().day.at(execution_time.strftime("%H:%M")).do(run_off)
    else:
        logging.info("\n-------------今日不下班打卡-------------\n")


def run_off():
    """执行下班打卡任务的主函数"""
    print("开始执行今日下班打卡任务")
    execute_tasks()


if __name__ == "__main__":
    logging.info("════════════════  自动下班打卡功能启动  ════════════════")

    # 打印模式信息
    mode = ConfigManager.get("clockInOff", "mode")
    mode_names = {"weekday": "【法定工作日】", "everyday": "【每天】", "customize": "【自定义】"}
    logging.info(f"下班打卡模式为{mode_names.get(mode, '【未知】')}\n")

    # 启动时立即为今天调度任务
    schedule_tasks()
    last_date = datetime.now().date()

    while True:
        current_time = datetime.now().strftime("%H:%M")
        logging.info(f"当前时间：{current_time}")
        gc.collect()

        # 检测日期变更（跨天），重新调度
        today = datetime.now().date()
        if today != last_date:
            logging.info("检测到日期变更，重新调度打卡任务")
            schedule_tasks()
            last_date = today

        schedule.run_pending()
        time.sleep(60)
