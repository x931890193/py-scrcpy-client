import os
import sys

import PySide6
dirname = os.path.dirname(PySide6.__file__)

plugin_path = os.path.join(dirname, 'plugins', 'platforms')
try:
    sys._MEIPASS
    plugin_path = os.path.join('.', 'plugins', 'platforms')
except:
    pass

os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path

from scrcpy_ui import main


if __name__ == '__main__':
    main.run()