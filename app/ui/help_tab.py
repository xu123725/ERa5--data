"""帮助页：ERA5 绘图帮助文档（Markdown 渲染 + 左侧目录导航）。"""

import re
import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


def resource_path(relative: str) -> Path:
    """兼容 PyInstaller 打包后的资源路径（_MEIPASS）。"""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent)
    return Path(base) / relative


class HelpTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_document()

    # ---------- UI ----------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(10)

        title = QLabel("绘图帮助文档")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        # 目录搜索
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索目录…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search)
        layout.addWidget(self.search_edit)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # 左侧目录
        self.toc = QListWidget()
        self.toc.setFixedWidth(210)
        self.toc.itemClicked.connect(self._on_toc_clicked)
        splitter.addWidget(self.toc)

        # 右侧文档内容
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self._open_link)
        self.browser.verticalScrollBar().valueChanged.connect(self._on_scroll)
        splitter.addWidget(self.browser)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([210, 860])
        layout.addWidget(splitter, 1)

    # ---------- 文档加载 ----------
    def _load_document(self):
        text = self._read_markdown()
        self.browser.setMarkdown(text)
        self._build_toc(text)

    def _read_markdown(self) -> str:
        """读取帮助文档：优先打包资源目录，其次项目根目录。"""
        candidates = [
            resource_path("app/resources/help.md"),
            Path(__file__).resolve().parent.parent.parent / "ERA5再分析资料绘图帮助文档.md",
            resource_path("help.md"),
        ]
        for path in candidates:
            if path.exists():
                return path.read_text(encoding="utf-8")
        return "# 帮助文档\n\n未找到帮助文档文件，请检查 app/resources/help.md 是否存在。"

    def _build_toc(self, text: str):
        """解析 Markdown 二级/三级标题，生成左侧目录。"""
        self.toc.clear()
        # 按行解析标题（支持带链接的标题，如 ## 1. [xxx](url)）
        for line in text.splitlines():
            m = re.match(r"^(#{2,3})\s+(.+)$", line.strip())
            if not m:
                continue
            level, heading = m.group(1), m.group(2).strip()
            # 去掉标题内的 Markdown 链接标记，仅保留显示文本
            plain = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", heading)
            item = QListWidgetItem(plain)
            indent = "" if len(level) == 2 else "    "
            item.setText(f"{indent}{plain}")
            font = QFont()
            font.setBold(len(level) == 2)
            item.setFont(font)
            item.setData(Qt.UserRole, plain)
            self.toc.addItem(item)

    # ---------- 交互 ----------
    def _on_search(self, text: str):
        """按关键字过滤左侧目录项（不匹配的隐藏）。"""
        query = text.strip().lower()
        for i in range(self.toc.count()):
            item = self.toc.item(i)
            target = (item.data(Qt.UserRole) or "").lower()
            item.setHidden(bool(query) and query not in target)

    def _on_scroll(self, _value):
        """右侧滚动时，根据当前视口顶部的标题高亮左侧目录项。"""
        doc = self.browser.document()
        layout = doc.documentLayout()
        top = self.browser.verticalScrollBar().value()
        block = doc.begin()
        best = None
        while block.isValid():
            if block.blockFormat().headingLevel() >= 2:
                rect = layout.blockBoundingRect(block)
                if rect.top() <= top + 12:
                    best = block.text().strip()
                else:
                    break
            block = block.next()
        if not best:
            return
        for i in range(self.toc.count()):
            item = self.toc.item(i)
            target = item.data(Qt.UserRole)
            if target and (best == target or best.endswith(target) or target.endswith(best)):
                self.toc.setCurrentRow(i)
                break

    def _on_toc_clicked(self, item):
        """点击目录：定位到对应标题在文档中的位置。"""
        target = item.data(Qt.UserRole)
        if not target:
            return
        doc = self.browser.document()
        # 逐块查找标题文本（含可能的编号前缀，如 "## 1. xxx"）
        block = doc.begin()
        while block.isValid():
            text = block.text().strip()
            if text == target or text.endswith(target) or target.endswith(text):
                cursor = doc.find(target)
                if not cursor.isNull():
                    self.browser.setTextCursor(cursor)
                    self.browser.ensureCursorVisible()
                    return
            block = block.next()

    def _open_link(self, url: QUrl):
        """点击文档内链接时用系统浏览器打开。"""
        if url.isValid():
            QDesktopServices.openUrl(url)
