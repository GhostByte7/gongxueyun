# -*- coding: utf-8 -*-
"""
工学云自动打卡 - 可视化管理界面
双击运行，填写账号密码，点击"保存配置"即可使用。
"""
import json
import logging
import os
import queue
import sys
import threading
import time
import traceback
from datetime import datetime
from tkinter import (
    Tk, Frame, Label, Button, Entry, Text, Scrollbar,
    ttk, messagebox, StringVar, BooleanVar, IntVar,
    VERTICAL, END, NORMAL, DISABLED,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from manager.ConfigManager import ConfigManager
from manager.UserInfoManager import UserInfoManager
from util.HelperFunctions import mask_sensitive


class QueueHandler(logging.Handler):
    """将 logging 输出重定向到 GUI 日志窗口"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("工学云自动打卡")
        self.root.geometry("960x720")
        self.root.minsize(860, 600)

        self.log_queue = queue.Queue()
        self._setup_logging()

        self.scheduler_running = False
        self.scheduler_thread = None

        self._build_ui()
        self.root.after(200, self._poll_log_queue)
        self._update_time_display()

        # 首次运行检测
        if not self._config_exists():
            self.root.after(500, self._show_first_run_guide)

        logging.info("程序已启动，请先填写账号密码后点击「保存配置」")

    # ==================== 日志 ====================
    def _setup_logging(self):
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.log")
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        root_logger.addHandler(fh)
        qh = QueueHandler(self.log_queue)
        qh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        root_logger.addHandler(qh)

    def _poll_log_queue(self):
        while True:
            try:
                record = self.log_queue.get_nowait()
                self.log_text.config(state=NORMAL)
                self.log_text.insert(END, record + "\n")
                self.log_text.see(END)
                self.log_text.config(state=DISABLED)
            except queue.Empty:
                break
        self.root.after(200, self._poll_log_queue)

    def _update_time_display(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=f"当前时间: {now}")
        self.root.after(1000, self._update_time_display)

    # ==================== 首次运行 ====================
    def _config_exists(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if not os.path.exists(config_path):
            return False
        phone = ConfigManager.get("user", "phone", default="")
        if not phone or phone == "请输入手机号":
            return False
        return True

    def _show_first_run_guide(self):
        messagebox.showinfo(
            "欢迎使用",
            "欢迎使用工学云自动打卡！\n\n"
            "首次使用请按以下步骤操作：\n"
            "1. 在「用户账号」标签页填写手机号和密码\n"
            "2. 在「上班打卡」「下班打卡」页设置时间和地址\n"
            "3. 点击底部「保存配置」按钮\n"
            "4. 点击「测试登录」验证账号密码是否正确\n"
            "5. 一切就绪后，点击「定时模式」启动自动打卡\n\n"
            "所有数据仅保存在本地，不会上传到任何服务器。"
        )

    # ==================== UI 布局 ====================
    def _build_ui(self):
        # 顶栏
        top_bar = Frame(self.root, bg="#2c3e50", height=40)
        top_bar.pack(fill="x")
        self.time_label = Label(top_bar, text="", fg="white", bg="#2c3e50", font=("微软雅黑", 12))
        self.time_label.pack(side="left", padx=15, pady=8)
        self.status_label = Label(top_bar, text="● 就绪", fg="#2ecc71", bg="#2c3e50", font=("微软雅黑", 11))
        self.status_label.pack(side="right", padx=15, pady=8)

        # 主区域
        main_pane = ttk.PanedWindow(self.root, orient="horizontal")
        main_pane.pack(fill="both", expand=True, padx=5, pady=5)

        left = Frame(main_pane)
        main_pane.add(left, weight=1)
        right = Frame(main_pane)
        main_pane.add(right, weight=1)

        self._build_config_panel(left)
        self._build_log_panel(right)

        # 底栏
        bottom = Frame(self.root, bg="#ecf0f1", height=50)
        bottom.pack(fill="x")

        Button(bottom, text="  上班打卡  ", bg="#3498db", fg="white",
               font=("微软雅黑", 10), command=self._manual_clockin,
               width=12).pack(side="left", padx=10, pady=8)
        Button(bottom, text="  下班打卡  ", bg="#9b59b6", fg="white",
               font=("微软雅黑", 10), command=self._manual_clockoff,
               width=12).pack(side="left", padx=5, pady=8)
        Button(bottom, text="  定时模式  ", bg="#27ae60", fg="white",
               font=("微软雅黑", 10), command=self._toggle_scheduler,
               width=12).pack(side="left", padx=5, pady=8)

        self.scheduler_btn_text = Label(bottom, text="", bg="#ecf0f1", font=("微软雅黑", 9), fg="#7f8c8d")
        self.scheduler_btn_text.pack(side="left", padx=5)

        Button(bottom, text="  保存配置  ", bg="#e67e22", fg="white",
               font=("微软雅黑", 10, "bold"), command=self._save_config,
               width=12).pack(side="right", padx=10, pady=8)

    def _build_config_panel(self, parent):
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)
        self._build_account_tab(notebook)
        self._build_clockin_tab(notebook)
        self._build_clockoff_tab(notebook)
        self._build_smtp_tab(notebook)

    # ==================== 用户账号标签页 ====================
    def _build_account_tab(self, notebook):
        frame = Frame(notebook, padx=15, pady=15)
        notebook.add(frame, text="  用户账号  ")

        self.phone_var = StringVar(value=ConfigManager.get("user", "phone", default=""))
        self.pass_var = StringVar(value=ConfigManager.get("user", "password", default=""))
        self.device_var = StringVar(value=ConfigManager.get("device", default=""))

        Label(frame, text="手机号:", font=("微软雅黑", 11)).grid(row=0, column=0, sticky="e", pady=6, padx=(0, 10))
        Entry(frame, textvariable=self.phone_var, font=("微软雅黑", 11), width=28).grid(row=0, column=1, sticky="w")

        Label(frame, text="密码:", font=("微软雅黑", 11)).grid(row=1, column=0, sticky="e", pady=6, padx=(0, 10))
        Entry(frame, textvariable=self.pass_var, font=("微软雅黑", 11), width=28, show="*").grid(row=1, column=1, sticky="w")

        Label(frame, text="设备:", font=("微软雅黑", 11)).grid(row=2, column=0, sticky="e", pady=6, padx=(0, 10))
        Entry(frame, textvariable=self.device_var, font=("微软雅黑", 10), width=36).grid(row=2, column=1, sticky="w")

        Label(frame, text="登录状态:", font=("微软雅黑", 11)).grid(row=4, column=0, sticky="e", pady=10, padx=(0, 10))
        self.login_status = Label(frame, text="未测试", fg="#95a5a6", font=("微软雅黑", 11))
        self.login_status.grid(row=4, column=1, sticky="w")

        ttk.Separator(frame, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)

        Button(frame, text="  测试登录  ", bg="#3498db", fg="white", font=("微软雅黑", 10),
               command=self._test_login, width=12).grid(row=6, column=1, sticky="w")
        Label(frame, text="（保存配置后点击测试）", font=("微软雅黑", 9), fg="#7f8c8d").grid(
            row=6, column=1, sticky="w", padx=(105, 0))

    # ==================== 上班打卡标签页 ====================
    def _build_clockin_tab(self, notebook):
        frame = Frame(notebook, padx=15, pady=15)
        notebook.add(frame, text="  上班打卡  ")

        self.ci_mode = StringVar(value=ConfigManager.get("clockIn", "mode", default="everyday"))
        Label(frame, text="打卡模式:", font=("微软雅黑", 11)).grid(row=0, column=0, sticky="ne", pady=4, padx=(0, 10))
        mf = Frame(frame)
        mf.grid(row=0, column=1, sticky="w")
        for text, val in [("法定工作日", "weekday"), ("每天", "everyday"), ("自定义周几", "customize")]:
            ttk.Radiobutton(mf, text=text, variable=self.ci_mode, value=val).pack(anchor="w")

        self.ci_time = StringVar(value=ConfigManager.get("clockIn", "time", "start", default="08:50"))
        Label(frame, text="打卡时间:", font=("微软雅黑", 11)).grid(row=1, column=0, sticky="e", pady=6, padx=(0, 10))
        Entry(frame, textvariable=self.ci_time, font=("微软雅黑", 11), width=10).grid(row=1, column=1, sticky="w")
        Label(frame, text="格式 HH:MM，例如 08:50", font=("微软雅黑", 9), fg="#7f8c8d").grid(
            row=1, column=1, sticky="w", padx=(95, 0))

        self.ci_float = IntVar(value=ConfigManager.get("clockIn", "time", "float", default=5))
        Label(frame, text="随机浮动:", font=("微软雅黑", 11)).grid(row=2, column=0, sticky="e", pady=6, padx=(0, 10))
        Entry(frame, textvariable=self.ci_float, font=("微软雅黑", 11), width=10).grid(row=2, column=1, sticky="w")
        Label(frame, text="分钟（避免被检测为机器人，0=不浮动）", font=("微软雅黑", 9), fg="#7f8c8d").grid(
            row=2, column=1, sticky="w", padx=(95, 0))

        self.ci_holiday = BooleanVar(value=ConfigManager.get("clockIn", "holidaysClockIn", default=False))
        ttk.Checkbutton(frame, text="法定节假日也打卡", variable=self.ci_holiday).grid(
            row=3, column=1, sticky="w", pady=4)

        self.ci_addr = StringVar(value=ConfigManager.get("clockIn", "location", "address", default=""))
        Label(frame, text="打卡地址:", font=("微软雅黑", 11)).grid(row=4, column=0, sticky="e", pady=6, padx=(0, 10))
        Entry(frame, textvariable=self.ci_addr, font=("微软雅黑", 11), width=36).grid(row=4, column=1, sticky="w")

        self.ci_lat = StringVar(value=ConfigManager.get("clockIn", "location", "latitude", default=""))
        self.ci_lng = StringVar(value=ConfigManager.get("clockIn", "location", "longitude", default=""))
        Label(frame, text="经纬度:", font=("微软雅黑", 11)).grid(row=5, column=0, sticky="e", pady=6, padx=(0, 10))
        ll = Frame(frame)
        ll.grid(row=5, column=1, sticky="w")
        Entry(ll, textvariable=self.ci_lat, font=("微软雅黑", 10), width=16).pack(side="left")
        Label(ll, text="  ,  ", font=("微软雅黑", 10)).pack(side="left")
        Entry(ll, textvariable=self.ci_lng, font=("微软雅黑", 10), width=16).pack(side="left")

    # ==================== 下班打卡标签页 ====================
    def _build_clockoff_tab(self, notebook):
        frame = Frame(notebook, padx=15, pady=15)
        notebook.add(frame, text="  下班打卡  ")

        self.co_mode = StringVar(value=ConfigManager.get("clockInOff", "mode", default="everyday"))
        Label(frame, text="打卡模式:", font=("微软雅黑", 11)).grid(row=0, column=0, sticky="ne", pady=4, padx=(0, 10))
        mf = Frame(frame)
        mf.grid(row=0, column=1, sticky="w")
        for text, val in [("法定工作日", "weekday"), ("每天", "everyday"), ("自定义周几", "customize")]:
            ttk.Radiobutton(mf, text=text, variable=self.co_mode, value=val).pack(anchor="w")

        self.co_time = StringVar(value=ConfigManager.get("clockInOff", "time", "start", default="18:00"))
        Label(frame, text="打卡时间:", font=("微软雅黑", 11)).grid(row=1, column=0, sticky="e", pady=6, padx=(0, 10))
        Entry(frame, textvariable=self.co_time, font=("微软雅黑", 11), width=10).grid(row=1, column=1, sticky="w")
        Label(frame, text="格式 HH:MM，例如 18:00", font=("微软雅黑", 9), fg="#7f8c8d").grid(
            row=1, column=1, sticky="w", padx=(95, 0))

        self.co_float = IntVar(value=ConfigManager.get("clockInOff", "time", "float", default=5))
        Label(frame, text="随机浮动:", font=("微软雅黑", 11)).grid(row=2, column=0, sticky="e", pady=6, padx=(0, 10))
        Entry(frame, textvariable=self.co_float, font=("微软雅黑", 11), width=10).grid(row=2, column=1, sticky="w")
        Label(frame, text="分钟（避免被检测为机器人，0=不浮动）", font=("微软雅黑", 9), fg="#7f8c8d").grid(
            row=2, column=1, sticky="w", padx=(95, 0))

        self.co_holiday = BooleanVar(value=ConfigManager.get("clockInOff", "holidaysClockIn", default=False))
        ttk.Checkbutton(frame, text="法定节假日也打卡", variable=self.co_holiday).grid(
            row=3, column=1, sticky="w", pady=4)

        self.co_addr = StringVar(value=ConfigManager.get("clockInOff", "location", "address", default=""))
        Label(frame, text="打卡地址:", font=("微软雅黑", 11)).grid(row=4, column=0, sticky="e", pady=6, padx=(0, 10))
        Entry(frame, textvariable=self.co_addr, font=("微软雅黑", 11), width=36).grid(row=4, column=1, sticky="w")

        self.co_lat = StringVar(value=ConfigManager.get("clockInOff", "location", "latitude", default=""))
        self.co_lng = StringVar(value=ConfigManager.get("clockInOff", "location", "longitude", default=""))
        Label(frame, text="经纬度:", font=("微软雅黑", 11)).grid(row=5, column=0, sticky="e", pady=6, padx=(0, 10))
        ll = Frame(frame)
        ll.grid(row=5, column=1, sticky="w")
        Entry(ll, textvariable=self.co_lat, font=("微软雅黑", 10), width=16).pack(side="left")
        Label(ll, text="  ,  ", font=("微软雅黑", 10)).pack(side="left")
        Entry(ll, textvariable=self.co_lng, font=("微软雅黑", 10), width=16).pack(side="left")

    # ==================== 邮件通知标签页 ====================
    def _build_smtp_tab(self, notebook):
        frame = Frame(notebook, padx=15, pady=15)
        notebook.add(frame, text="  邮件通知  ")

        self.smtp_enable = BooleanVar(value=ConfigManager.get("smtp", "enable", default=False))
        ttk.Checkbutton(frame, text="启用邮件通知（打卡结果发送到邮箱）", variable=self.smtp_enable).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        fields = [
            ("SMTP 服务器:", "smtp.qq.com"),
            ("端口:", "465"),
            ("发件邮箱:", ""),
            ("授权码:", ""),
            ("发件人名称:", "打卡通知"),
            ("收件人:", ""),
        ]
        keys = ["host", "port", "username", "password", "from", "to"]
        self.smtp_vars = {}

        for i, ((label, default), key) in enumerate(zip(fields, keys)):
            val = ConfigManager.get("smtp", key, default=default)
            if key == "to":
                val = ",".join(val) if isinstance(val, list) else val
            self.smtp_vars[key] = StringVar(value=str(val))
            Label(frame, text=label, font=("微软雅黑", 11)).grid(
                row=i + 1, column=0, sticky="e", pady=4, padx=(0, 10))
            show = "*" if key == "password" else ""
            Entry(frame, textvariable=self.smtp_vars[key], font=("微软雅黑", 10),
                  width=30, show=show).grid(row=i + 1, column=1, sticky="w")
            if key == "password":
                Label(frame, text="（QQ邮箱在设置→账户→POP3/SMTP 中获取）",
                      font=("微软雅黑", 8), fg="#7f8c8d").grid(
                    row=i + 1, column=1, sticky="w", padx=(195, 0))

    # ==================== 日志面板 ====================
    def _build_log_panel(self, parent):
        Label(parent, text="运行日志", font=("微软雅黑", 11, "bold")).pack(anchor="w")
        lf = Frame(parent)
        lf.pack(fill="both", expand=True, pady=5)
        self.log_text = Text(lf, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4",
                             insertbackground="white", wrap="word", state=DISABLED)
        sb = Scrollbar(lf, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        Label(parent, text="执行结果", font=("微软雅黑", 11, "bold")).pack(anchor="w", pady=(8, 0))
        self.result_text = Text(parent, font=("微软雅黑", 10), height=4, wrap="word",
                                bg="#f8f9fa", fg="#2c3e50")
        self.result_text.pack(fill="x")
        self.result_text.insert("1.0", "暂无任务执行")
        self.result_text.config(state=DISABLED)

    # ==================== 后台任务 ====================
    def _run_async(self, func, name):
        def wrap():
            self.root.after(0, lambda: self.status_label.config(text=f"● {name} 执行中...", fg="#f39c12"))
            try:
                result = func()
                if isinstance(result, dict):
                    self.root.after(0, self._show_result, result)
            except Exception as e:
                logging.error(f"{name}失败: {e}")
                self.root.after(0, self._show_result, {"title": "错误", "content": str(e)})
            self.root.after(0, lambda: self.status_label.config(text="● 就绪", fg="#2ecc71"))
        threading.Thread(target=wrap, daemon=True).start()

    def _show_result(self, result):
        self.result_text.config(state=NORMAL)
        self.result_text.delete("1.0", END)
        self.result_text.insert("1.0", f"【{result.get('title', '')}】\n{result.get('content', '')}")
        self.result_text.config(state=DISABLED)

    # ==================== 手动打卡 ====================
    def _ensure_config_saved(self):
        phone = ConfigManager.get("user", "phone", default="")
        if not phone or phone == "请输入手机号":
            msg = "尚未配置账号密码。\n\n请先在「用户账号」标签页填写手机号和密码，然后点击「保存配置」。"
            messagebox.showwarning("未配置", msg)
            return False
        return True

    def _do_checkin(self):
        from step.login import login
        from step.fetchPlan import fetch_plan
        from step.clockIn import clock_in

        if not self._ensure_config_saved():
            return {"title": "失败", "content": "未配置账号密码"}

        isLogin = login()
        if not isLogin:
            return {"title": "失败", "content": "登录失败，请检查账号密码是否正确"}

        if UserInfoManager.get("userType") != "student":
            return {"title": "失败", "content": "当前用户不是学生"}

        fetch_plan()
        return clock_in()

    def _manual_clockin(self):
        logging.info(">>> 手动上班打卡 <<<")
        self._run_async(self._do_checkin, "上班打卡")

    def _manual_clockoff(self):
        if datetime.now().hour < 12:
            if not messagebox.askokcancel("提示",
                    "当前是上午，系统会根据时间自动判断打卡类型。\n"
                    "上午执行将自动作为「上班打卡」，确定继续吗？"):
                return
        logging.info(">>> 手动下班打卡 <<<")
        self._run_async(self._do_checkin, "下班打卡")

    # ==================== 登录测试 ====================
    def _test_login(self):
        self._save_config(silent=True)
        if not self._ensure_config_saved():
            return
        self._run_async(self._do_test_login, "登录测试")

    def _do_test_login(self):
        from step.login import login
        success = login()
        if success:
            self.root.after(0, lambda: self.login_status.config(text="已登录 ✓", fg="#27ae60"))
            token = UserInfoManager.get_token() or ""
            return {"title": "登录成功", "content": f"账号验证通过\n{mask_sensitive({'phone': ConfigManager.get('user', 'phone')})}"}
        else:
            self.root.after(0, lambda: self.login_status.config(text="登录失败 ✗", fg="#e74c3c"))
            return {"title": "登录失败", "content": "请检查手机号和密码是否正确"}

    # ==================== 定时模式 ====================
    def _toggle_scheduler(self):
        if self.scheduler_running:
            self.scheduler_running = False
            self.status_label.config(text="● 定时模式已停止", fg="#e74c3c")
            self.scheduler_btn_text.config(text="已停止")
            logging.info("定时模式已停止")
        else:
            self._save_config(silent=True)
            if not self._ensure_config_saved():
                return
            self.scheduler_running = True
            self.status_label.config(text="● 定时模式运行中", fg="#2ecc71")
            self.scheduler_btn_text.config(text="运行中，保持窗口开启")
            logging.info("定时模式已启动")
            self._start_scheduler()
            messagebox.showinfo("定时模式",
                                "定时模式已启动！\n\n"
                                "系统将在每天凌晨自动调度打卡任务。\n"
                                "打卡时间会加入随机浮动。\n"
                                "保持此窗口打开即可，最小化到后台也没问题。")

    def _start_scheduler(self):
        import gc, random, schedule

        def loop():
            self._daily_schedule(schedule, random)
            last_date = datetime.now().date()
            while self.scheduler_running:
                try:
                    schedule.run_pending()
                    today = datetime.now().date()
                    if today != last_date:
                        self._daily_schedule(schedule, random)
                        last_date = today
                    gc.collect()
                    time.sleep(60)
                except Exception as e:
                    logging.error(f"调度异常: {e}")
                    time.sleep(60)

        threading.Thread(target=loop, daemon=True).start()

    def _daily_schedule(self, schedule, random):
        schedule.clear()

        def should(ck):
            if ConfigManager.get(ck, "holidaysClockIn"):
                return True
            mode = ConfigManager.get(ck, "mode")
            if mode == "everyday":
                return True
            if mode == "weekday":
                from util.HelperFunctions import is_workday_realtime
                return is_workday_realtime()
            if mode == "customize":
                days = ConfigManager.get(ck, "customDays", default=[])
                return (datetime.today().weekday() + 1) in days
            return False

        def gentime(ck):
            fm = ConfigManager.get(ck, "time", "float", default=1)
            rm = random.randint(0, fm)
            ts = ConfigManager.get(ck, "time", "start", default="09:00")
            ct = datetime.strptime(ts, "%H:%M")
            h, m = ct.hour, ct.minute + rm
            if m >= 60:
                h += 1
                m -= 60
            return datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)

        def run(tag):
            logging.info(f">>> 定时{tag}打卡触发 <<<")
            from main import execute_tasks
            try:
                execute_tasks()
            except Exception as e:
                logging.error(f"定时{tag}打卡异常: {e}")

        if should("clockIn"):
            t = gentime("clockIn")
            logging.info(f"今日上班计划: {t.strftime('%H:%M')}")
            schedule.every().day.at(t.strftime("%H:%M")).do(lambda: run("上班"))
        else:
            logging.info("今日不打上班卡")

        if should("clockInOff"):
            t = gentime("clockInOff")
            logging.info(f"今日下班计划: {t.strftime('%H:%M')}")
            schedule.every().day.at(t.strftime("%H:%M")).do(lambda: run("下班"))
        else:
            logging.info("今日不打下班卡")

    # ==================== 保存配置 ====================
    def _save_config(self, silent=False):
        try:
            config = {
                "user": {
                    "phone": self.phone_var.get(),
                    "password": self.pass_var.get(),
                },
                "device": self.device_var.get(),
                "clockIn": {
                    "mode": self.ci_mode.get(),
                    "holidaysClockIn": self.ci_holiday.get(),
                    "customDays": [1, 2, 3, 4, 5],
                    "time": {"start": self.ci_time.get(), "float": self.ci_float.get()},
                    "location": {
                        "address": self.ci_addr.get(),
                        "latitude": self.ci_lat.get(),
                        "longitude": self.ci_lng.get(),
                        "province": "", "city": "", "area": "",
                    },
                },
                "clockInOff": {
                    "mode": self.co_mode.get(),
                    "holidaysClockIn": self.co_holiday.get(),
                    "customDays": [1, 2, 3, 4, 5],
                    "time": {"start": self.co_time.get(), "float": self.co_float.get()},
                    "location": {
                        "address": self.co_addr.get(),
                        "latitude": self.co_lat.get(),
                        "longitude": self.co_lng.get(),
                        "province": "", "city": "", "area": "",
                    },
                },
                "smtp": {
                    "enable": self.smtp_enable.get(),
                    "host": self.smtp_vars["host"].get(),
                    "port": int(self.smtp_vars["port"].get()),
                    "username": self.smtp_vars["username"].get(),
                    "password": self.smtp_vars["password"].get(),
                    "from": self.smtp_vars["from"].get(),
                    "to": [e.strip() for e in self.smtp_vars["to"].get().split(",") if e.strip()],
                },
            }

            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"config": config}, f, ensure_ascii=False, indent=2)

            ConfigManager._config_cache = config

            if not silent:
                logging.info("配置已保存")
                messagebox.showinfo("保存成功", f"配置已保存。\n\n文件位置：{config_path}")
        except Exception as e:
            logging.error(f"保存失败: {e}")
            if not silent:
                messagebox.showerror("保存失败", str(e))


def main():
    root = Tk()
    style = ttk.Style()
    style.theme_use("clam")

    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
