"""通用后台任务线程（用于数据处理等一次性任务）。"""

from PySide6.QtCore import QThread, Signal


class FunctionWorker(QThread):
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._args = args

    def run(self):
        try:
            result = self._fn(*self._args)
            self.result_ready.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
