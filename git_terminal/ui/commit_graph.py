from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, sin
from typing import Dict, Iterable, List

from PyQt6.QtCore import QPoint, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QMenu,
)


@dataclass
class GraphCommit:
    hash: str
    parents: List[str]
    short_hash: str
    date: str
    author: str
    refs: str
    message: str

    @property
    def tooltip(self) -> str:
        parent_text = ", ".join(p[:8] for p in self.parents) if self.parents else "<root>"
        refs = self.refs or "-"
        return (
            f"commit: {self.short_hash}\n"
            f"refs: {refs}\n"
            f"author: {self.author}\n"
            f"date: {self.date}\n"
            f"parents: {parent_text}\n\n"
            f"{self.message}"
        )


class CommitNodeItem(QGraphicsEllipseItem):
    def __init__(self, commit: GraphCommit, graph: "CommitGraphView", x: float, y: float, radius: float = 9.0):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.commit = commit
        self.graph = graph
        self.radius = radius
        self.setPos(x, y)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self.setToolTip(commit.tooltip)
        self.normal_brush = QBrush(QColor("#60a5fa"))
        self.hover_brush = QBrush(QColor("#f97316"))
        self.selected_brush = QBrush(QColor("#22c55e"))
        self.setBrush(self.normal_brush)
        self.setPen(QPen(QColor("#e5e7eb"), 2))
        self.setZValue(10)

    def hoverEnterEvent(self, event):  # noqa: N802
        self.setBrush(self.hover_brush)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):  # noqa: N802
        if self.graph.selected_hash == self.commit.hash:
            self.setBrush(self.selected_brush)
        else:
            self.setBrush(self.normal_brush)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.graph.select_commit(self.commit.hash)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.graph.commitActivated.emit(self.commit.hash)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):  # noqa: N802
        self.graph.select_commit(self.commit.hash)
        self.graph.commitContextRequested.emit(self.commit.hash, event.screenPos())
        event.accept()


class CommitGraphView(QGraphicsView):
    commitSelected = pyqtSignal(str)
    commitActivated = pyqtSignal(str)
    commitContextRequested = pyqtSignal(str, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumWidth(80)
        self.selected_hash = ""
        self.node_items: Dict[str, CommitNodeItem] = {}

    def wheelEvent(self, event):  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def select_commit(self, commit_hash: str) -> None:
        self.selected_hash = commit_hash
        for h, node in self.node_items.items():
            node.setBrush(node.selected_brush if h == commit_hash else node.normal_brush)
        self.commitSelected.emit(commit_hash)

    def set_commits(self, commits: Iterable[GraphCommit]) -> None:
        commits = list(commits)
        self.scene_obj.clear()
        self.node_items.clear()
        self.selected_hash = ""
        if not commits:
            text = self.scene_obj.addText("没有提交历史。打开一个 Git 仓库后点击刷新。")
            text.setDefaultTextColor(QColor("#94a3b8"))
            return

        positions = self._layout_positions(commits)
        # Draw parent edges first.
        for commit in commits:
            if commit.hash not in positions:
                continue
            x1, y1 = positions[commit.hash]
            for parent in commit.parents:
                if parent in positions:
                    x2, y2 = positions[parent]
                    self._add_edge(QPointF(x1, y1), QPointF(x2, y2))

        for commit in commits:
            if commit.hash not in positions:
                continue
            x, y = positions[commit.hash]
            node = CommitNodeItem(commit, self, x, y)
            self.scene_obj.addItem(node)
            self.node_items[commit.hash] = node
            label_text = commit.short_hash
            if commit.refs:
                label_text += f"  {commit.refs}"
            label_text += f"  {commit.message[:80]}"
            label = QGraphicsTextItem(label_text)
            label.setDefaultTextColor(QColor("#cbd5e1"))
            label.setPos(x + 16, y - 13)
            label.setToolTip(commit.tooltip)
            self.scene_obj.addItem(label)

        self.scene_obj.setSceneRect(self.scene_obj.itemsBoundingRect().adjusted(-40, -40, 240, 80))
        self.fitInView(self.scene_obj.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _layout_positions(self, commits: List[GraphCommit]) -> Dict[str, tuple[float, float]]:
        lane_width = 42.0
        row_height = 44.0
        x_origin = 34.0
        y_origin = 28.0
        active_lanes: List[str] = []
        positions: Dict[str, tuple[float, float]] = {}

        for row, commit in enumerate(commits):
            if commit.hash in active_lanes:
                lane = active_lanes.index(commit.hash)
            else:
                lane = len(active_lanes)
                active_lanes.append(commit.hash)
            positions[commit.hash] = (x_origin + lane * lane_width, y_origin + row * row_height)

            # Replace current commit in the lane with first parent, and allocate
            # extra lanes for merge parents. This mirrors Git graph lane behavior.
            if commit.parents:
                active_lanes[lane] = commit.parents[0]
                insert_at = lane + 1
                for parent in commit.parents[1:]:
                    if parent not in active_lanes:
                        active_lanes.insert(insert_at, parent)
                        insert_at += 1
            else:
                if 0 <= lane < len(active_lanes):
                    active_lanes.pop(lane)

        return positions

    def _add_edge(self, start: QPointF, end: QPointF) -> None:
        path = QPainterPath(start)
        mid_y = (start.y() + end.y()) / 2
        path.cubicTo(QPointF(start.x(), mid_y), QPointF(end.x(), mid_y), end)
        edge = QGraphicsPathItem(path)
        edge.setPen(QPen(QColor("#64748b"), 2.0))
        edge.setZValue(1)
        self.scene_obj.addItem(edge)

        # Direction arrow near parent node.
        angle = atan2(end.y() - start.y(), end.x() - start.x())
        arrow_size = 7.0
        arrow_tip = QPointF(end.x(), end.y() - 10)
        p1 = QPointF(arrow_tip.x() - arrow_size * cos(angle - 0.55), arrow_tip.y() - arrow_size * sin(angle - 0.55))
        p2 = QPointF(arrow_tip.x() - arrow_size * cos(angle + 0.55), arrow_tip.y() - arrow_size * sin(angle + 0.55))
        arrow = QGraphicsPolygonItem(QPolygonF([arrow_tip, p1, p2]))
        arrow.setBrush(QBrush(QColor("#64748b")))
        arrow.setPen(QPen(QColor("#64748b"), 1))
        arrow.setZValue(2)
        self.scene_obj.addItem(arrow)
