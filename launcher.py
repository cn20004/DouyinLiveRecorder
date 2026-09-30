"""Windows desktop launcher, configuration editor and historical CSV exporter."""
import csv
from pathlib import Path
import sqlite3
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox
import webbrowser

ROOT = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
VERSION = 'v1.1.0'

def self_test():
    required = ['DouyinLiveRecorder-Core.exe', 'runtime/node.exe', 'runtime/dyhub/dist/index.js',
                'config/config.ini', 'ffmpeg/ffmpeg.exe']
    missing = [name for name in required if not (ROOT / name).is_file()]
    if not list((ROOT / 'runtime/browsers').glob('chromium-*/chrome-win*/chrome.exe')):
        missing.append('Chromium browser')
    if missing:
        print('Missing: ' + ', '.join(missing)); return 1
    print('Windows package self-test OK'); return 0

if '--self-test' in sys.argv:
    raise SystemExit(self_test())

app = tk.Tk()
app.title('郑老师魔改版 · 抖音直播录制 ' + VERSION)
app.geometry('740x540')
process = None
status = tk.StringVar(value='请填写直播间地址，每行一个；保存后点击“开始录制”。')
tk.Label(app, text='郑老师魔改版 ' + VERSION, font=('Microsoft YaHei', 20, 'bold')).pack(pady=12)
tk.Label(app, text='录像 · 配置防丢失 · 评论采集 · 人数历史 · CSV导出').pack()
text = tk.Text(app, height=12, font=('Consolas', 11))
text.pack(fill='both', expand=True, padx=16, pady=12)
url_file = ROOT / 'config/URL_config.ini'
if url_file.exists(): text.insert('1.0', url_file.read_text(encoding='utf-8-sig'))

def save():
    from src.utils import atomic_write_text
    value = text.get('1.0', 'end').strip()
    if not value:
        messagebox.showwarning('未填写地址', '请填写至少一个直播地址。'); return False
    atomic_write_text(url_file, value + '\n')
    status.set('直播间地址已保存，保留上一份备份。'); return True

def start():
    global process
    if process and process.poll() is None:
        status.set('录制程序已在运行。'); return
    if not save(): return
    exe = ROOT / 'DouyinLiveRecorder-Core.exe'
    if not exe.exists(): messagebox.showerror('文件缺失', '请解压整个压缩包，不能单独拷贝EXE。'); return
    process = subprocess.Popen([str(exe)], cwd=str(ROOT), creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
    status.set('录制窗口已启动；直播开播后自动启动评论采集。')

def export():
    import configparser
    config = configparser.RawConfigParser(); config.read(ROOT / 'config/config.ini', encoding='utf-8-sig')
    db = Path(config.get('录制设置', '抖音评论数据库路径', fallback='data/douyin_live.db'))
    if not db.is_absolute(): db = ROOT / db
    if not db.exists(): messagebox.showinfo('暂无数据', '尚未收到采集数据。开播并连接成功后会生成数据库。'); return
    dest = ROOT / 'exports'; dest.mkdir(exist_ok=True)
    try:
        with sqlite3.connect(f'{db.as_uri()}?mode=ro', uri=True) as conn:
            for name in ['douyin_events', 'douyin_room_stats', 'douyin_monitor_sessions']:
                cursor = conn.execute('SELECT * FROM ' + name)
                with open(dest / (name + '.csv'), 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f); writer.writerow([v[0] for v in cursor.description]); writer.writerows(cursor)
        webbrowser.open(dest.as_uri()); status.set('历史评论、人数及采集状态已导出到 exports 文件夹。')
    except Exception as err: messagebox.showerror('导出失败', str(err))

buttons = tk.Frame(app); buttons.pack(pady=8)
for label, action in [('保存地址', save), ('开始录制', start), ('实时数据', lambda:webbrowser.open('http://127.0.0.1:8757')), ('导出历史CSV', export), ('录制文件', lambda:webbrowser.open((ROOT/'downloads').as_uri())), ('设置', lambda:webbrowser.open((ROOT/'config/config.ini').as_uri()))]:
    tk.Button(buttons, text=label, command=action, padx=8).pack(side='left', padx=3)
tk.Label(app, textvariable=status, wraplength=710).pack(pady=10)
tk.Label(app, text='历史指开始监听后保存的数据；平台验证或网络故障会在录制窗口和日志中显示。', fg='#555555').pack(pady=4)
app.mainloop()
