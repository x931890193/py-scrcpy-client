import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from typing import Optional
import numpy as np
from PySide6.QtCore import Signal, QThread
from adbutils import adb, adb_path
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPixmap, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

import scrcpy
from legend.legend import Legend
from .ui_main import Ui_MainWindow

if not QApplication.instance():
    app = QApplication([])
else:
    app = QApplication.instance()


class ClientThread(QThread):
    def __init__(self, parent, client):
        QThread.__init__(self, parent)
        self.client = client

    def __del__(self):
        self.wait()

    def run(self):
        while True:
            self.client.start()
            break
        print('ClientThread exit')


class MainWindow(QMainWindow):
    fixe_sn = '---'
    signal_running = Signal(np.ndarray)

    def __init__(self, max_width: Optional[int]):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.max_width = max_width
        self.device = None
        self.client = None
        self.legend = None

        # Setup devices
        self.devices = self.list_devices()
        self.alive = True

        # Bind controllers
        self.ui.button_home.clicked.connect(self.on_click_home)
        self.ui.button_run.clicked.connect(self.on_click_run)
        self.ui.button_back.clicked.connect(self.on_click_back)

        # Bind config
        self.ui.combo_device.currentTextChanged.connect(self.choose_device)
        self.ui.flip.stateChanged.connect(self.on_flip)

        # Bind mouse event
        self.ui.label.mousePressEvent = self.on_mouse_event(scrcpy.ACTION_DOWN)
        self.ui.label.mouseMoveEvent = self.on_mouse_event(scrcpy.ACTION_MOVE)
        self.ui.label.mouseReleaseEvent = self.on_mouse_event(scrcpy.ACTION_UP)

        # Keyboard event
        self.keyPressEvent = self.on_key_event(scrcpy.ACTION_DOWN)
        self.keyReleaseEvent = self.on_key_event(scrcpy.ACTION_UP)

        self.signal_running.connect(self.run)

        self.running = False
        self.q = queue.Queue(maxsize=1)
        threading.Thread(target=self.listen_device, daemon=True).start()
        threading.Thread(target=self.reconnect_off_line, daemon=True).start()

    def choose_device(self, device):
        # Ensure text
        self.ui.combo_device.setCurrentText(device)
        # Restart service
        if getattr(self, "client", None):
            self.running = False
            self.client.remove_listener(scrcpy.EVENT_INIT, self.on_init)
            self.client.remove_listener(scrcpy.EVENT_FRAME, self.on_frame)
            self.client.stop()
            self.ui.button_run.setText("RUN")
            self.on_init()
            self.client = None
        if device != self.fixe_sn:
            self.device = adb.device(serial=self.ui.combo_device.currentText())
            # Setup client
            self.client = scrcpy.Client(
                device=self.device,
                flip=self.ui.flip.isChecked(),
                bitrate=1000000000,
                encoder_name=None,
            )
            self.client.add_listener(scrcpy.EVENT_INIT, self.on_init)
            self.client.add_listener(scrcpy.EVENT_FRAME, self.on_frame)
            self.client.device = adb.device(serial=device)
            # 这里很神奇～～～～ 这块时阻塞的 但是UI并没有卡住😊
            self.client.start()
        else:
            self.ui.label.setText('<html><head/><body><p><span style=" font-size:20pt;">Wait Connect....</span></p></body></html>')

    def list_devices(self):
        self.ui.combo_device.clear()
        self.ui.combo_device.addItem(self.fixe_sn)
        items = [i.serial for i in adb.device_list()]
        items = sorted(items)
        self.ui.combo_device.addItems(items)
        return items

    def reconnect_off_line(self):
        while self.alive:
            time.sleep(2)
            try:
                to_reconnect_devices = []
                path = adb_path()
                try:
                    sys._MEIPASS
                    path = os.path.join('adbutils', 'binaries', 'adb.exe')
                except:
                    pass
                encoding = 'utf-8'
                if sys.platform == 'win32':
                    encoding = 'gbk'
                res = subprocess.Popen('{} devices -l'.format(path),
                                       shell=True,
                                       stdout=subprocess.PIPE,
                                       encoding=encoding
                                       )
                try:
                    res, _ = res.communicate(timeout=3)
                except Exception as e:
                    traceback.print_exc()
                    continue

                for line in res.split('\n'):
                    line = line.strip()
                    if line.startswith('emulator') or not line:
                        continue
                    if 'offline' in line:
                        res_list = line.split(' ')
                        device_sn = res_list[0]
                        to_reconnect_devices.append(device_sn)
                for device_sn in to_reconnect_devices:
                    subprocess.Popen('{} disconnect {}'.format(path, device_sn), shell=True)
                    subprocess.Popen('{} connect {}'.format(path, device_sn), shell=True)
            except Exception as e:
                traceback.print_exc()
                continue

    def listen_device(self):
        while self.alive:
            to_insert = set()
            exist_sn_map = {}
            now_sn = set()
            for index in range(self.ui.combo_device.count()):
                sn = self.ui.combo_device.itemText(index)
                exist_sn_map[sn] = index

            for i in adb.device_list():
                try:
                    sn = i.serial
                    index = self.ui.combo_device.findText(sn)
                    now_sn.add(sn)
                    if index >= 0:
                        continue
                    else:
                        to_insert.add(sn)
                except:
                    continue
            to_delete_sn = set(exist_sn_map.keys()) - now_sn
            for sn in to_delete_sn:
                if sn == self.fixe_sn:
                    continue
                index = exist_sn_map[sn]
                self.ui.combo_device.removeItem(index)
            self.ui.combo_device.addItems(to_insert)
            time.sleep(1)

    def on_flip(self, _):
        if not getattr(self, "client", None) or not self.client.alive or self.client.device.serial != self.ui.combo_device.currentText():
            return
        self.client.flip = self.ui.flip.isChecked()

    def on_click_home(self):
        self.client.control.keycode(scrcpy.KEYCODE_HOME, scrcpy.ACTION_DOWN)
        self.client.control.keycode(scrcpy.KEYCODE_HOME, scrcpy.ACTION_UP)

    def on_click_run(self):
        if not getattr(self, "client", None) or not self.client.alive or self.client.device.serial != self.ui.combo_device.currentText():
            return
        if self.ui.button_run.text() == 'RUN':
            self.running = True
            self.legend = Legend(self)
            threading.Thread(target=self.legend.run, daemon=True).start()
            self.ui.button_run.setText("STOP")
        else:
            self.running = False
            self.ui.button_run.setText("RUN")
        self.on_init()

    def on_click_back(self):
        self.client.control.back_or_turn_screen_on(scrcpy.ACTION_DOWN)
        self.client.control.back_or_turn_screen_on(scrcpy.ACTION_UP)

    def on_mouse_event(self, action=scrcpy.ACTION_DOWN):
        def handler(evt: QMouseEvent):
            if not getattr(self, 'client', None) or not self.client.alive or self.client.device.serial != self.ui.combo_device.currentText():
                return
            focused_widget = QApplication.focusWidget()
            if focused_widget is not None:
                focused_widget.clearFocus()
            ratio = self.max_width / max(self.client.resolution)
            self.client.control.touch(
                evt.position().x() / ratio, evt.position().y() / ratio, action
            )
        return handler

    def on_key_event(self, action=scrcpy.ACTION_DOWN):
        def handler(evt: QKeyEvent):
            code = self.map_code(evt.key())
            if code != -1:
                self.client.control.keycode(code, action)

        return handler

    def map_code(self, code):
        """
        Map qt keycode ti android keycode

        Args:
            code: qt keycode
            android keycode, -1 if not founded
        """

        if code == -1:
            return -1
        if 48 <= code <= 57:
            return code - 48 + 7
        if 65 <= code <= 90:
            return code - 65 + 29
        if 97 <= code <= 122:
            return code - 97 + 29

        hard_code = {
            32: scrcpy.KEYCODE_SPACE,
            16777219: scrcpy.KEYCODE_DEL,
            16777248: scrcpy.KEYCODE_SHIFT_LEFT,
            16777220: scrcpy.KEYCODE_ENTER,
            16777217: scrcpy.KEYCODE_TAB,
            16777249: scrcpy.KEYCODE_CTRL_LEFT,
        }
        if code in hard_code:
            return hard_code[code]

        print(f"Unknown keycode: {code}")
        return -1

    def on_init(self):
        self.setWindowTitle(f"Serial: {self.client.device_name}" + ("  Running" if self.running else ""))

    def on_frame(self, frame):
        if not getattr(self, "client", None) or not self.client.alive or self.client.device.serial != self.ui.combo_device.currentText():
            return
        app.processEvents()
        if frame is not None:
            ratio = self.max_width / max(self.client.resolution)
            image = QImage(
                frame,
                frame.shape[1],
                frame.shape[0],
                frame.shape[1] * 3,
                QImage.Format_BGR888,
            )
            pix = QPixmap(image)
            pix.setDevicePixelRatio(1 / ratio)
            self.ui.label.setPixmap(pix)
            self.resize(1, 1)
            if self.running:
                self.signal_running.emit(frame)

    def run(self, frame):
        if self.q.full():
            self.q.get()
        else:
            self.q.put(frame)

    def closeEvent(self, _):
        self.client.stop()
        self.alive = False
        sys.exit(0)


def run():
    m = MainWindow(800)
    m.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
