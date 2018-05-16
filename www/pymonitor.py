#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import os, sys, time, subprocess

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def log(s):
    print('[Monitor] %s' % s)

class MyFileSystemEventHander(FileSystemEventHandler):

    def __init__(self, fn):
        super(MyFileSystemEventHander, self).__init__()
        self.kill = fn

    def on_any_event(self, event):
        if event.src_path.endswith('.py'):
            log('Python source file changed: %s' % event.src_path)
            self.kill()

command = ['echo', 'ok']

def kill_process():
    process = subprocess.Popen("ps aux|grep -v grep|grep www-data|awk '{print $2}'", stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=True)
    process=process.stdout.read()
    if process:
        process=str(int(process))
        log('Kill process [%s]...' % process)
        process=subprocess.Popen("kill "+process, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=True)
        process.wait()
        log('Process ended with code  %s.' % process.returncode)
        process=None

def start_watch(path, callback):
    observer = Observer()
    observer.schedule(MyFileSystemEventHander(kill_process), path, recursive=True)
    observer.start()
    process = subprocess.Popen("ps aux|grep -v grep|grep www-data|awk '{print $2}'", stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=True)
    process=int(process.stdout.read())
    log('Watching directory %s...' % path)
    log('Watching pid %s...' % process)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    argv = sys.argv[1:]
    if not argv:
        print('Usage: ./pymonitor your-script.py')
        exit(0)
    if argv[0] != 'python3':
        argv.insert(0, 'python3')
    command = argv
    path = os.path.abspath('.')
    start_watch(path, None)