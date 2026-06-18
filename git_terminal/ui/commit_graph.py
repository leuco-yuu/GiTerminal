from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, sin
from typing import Dict, Iterable, List, Tuple

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
)

LANE_COLORS = [
    "#60a5fa",  # blue
    "#34d399",  # green
    "#f97316",  # orange
    "#c084fc",  # purple
    "#f472b6",  # pink
    "#facc15",  # yellow
    "#22d3ee",  # cyan
    "#fb7185",  # rose
]


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


class CommitNodeItem(QGraphicsObject):
    def __init__(self, commit: GraphCommit, graph: "CommitGraphView", x: float, y: float, color: str, radius: float = 12.0):
        super().__init__()
        self.commit = commit
        self.graph = graph
        self.radius = radius
        self.color = QColor(color)
        self.hover_progress = 0.0
        self.selected = False
        self.setPos(x, y)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)
        self.setToolTip(commit.tooltip)
        self.setZValue(20)
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(140)
        self.anim.valueChanged.connect(self._set_hover_progress)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 110))
        self.setGraphicsEffect(shadow)

    def boundingRect(self) -> QRectF:  # noqa: N802
        r = self.radius + 7
        return QRectF(-r, -r, r * 2, r * 2)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        progress = self.hover_progress
        node_radius = self.radius + progress * 2.5
        outer_radius = node_radius + (5 if self.selected else 3)

        # Selection/hover halo.
        halo = QColor(self.color)
        halo.setAlpha(80 if self.selected else int(35 + progress * 70))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(QPointF(0, 0), outer_radius, outer_radius)

        # Gradient body.
        grad = QRadialGradient(QPointF(-4, -5), node_radius * 1.7)
        light = QColor(self.color).lighter(145)
        dark = QColor(self.color).darker(130)
        grad.setColorAt(0.0, light)
        grad.setColorAt(0.72, self.color)
        grad.setColorAt(1.0, dark)
        painter.setBrush(QBrush(grad))
        border_width = 3.0 if self.selected else 2.2
        border = QColor("#f8fafc") if self.selected else QColor("#e5e7eb")
        painter.setPen(QPen(border, border_width))
        painter.drawEllipse(QPointF(0, 0), node_radius, node_radius)

        # Inner shine dot for depth.
        shine = QColor("#ffffff")
        shine.setAlpha(95)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(shine))
        painter.drawEllipse(QPointF(-4.2, -5.2), 3.0, 3.0)

    def _set_hover_progress(self, value) -> None:
        self.hover_progress = float(value)
        scale = 1.0 + self.hover_progress * 0.08
        self.setScale(scale)
        self.update()

    def animate_to(self, target: float) -> None:
        self.anim.stop()
        self.anim.setStartValue(self.hover_progress)
        self.anim.setEndValue(target)
        self.anim.start()

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self.animate_to(1.0 if selected else 0.0)
        self.update()

    def hoverEnterEvent(self, event):  # noqa: N802
        self.animate_to(1.0)
        self.graph.commitHovered.emit(self.commit.hash)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):  # noqa: N802
        if not self.selected:
            self.animate_to(0.0)
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
    commitHovered = pyqtSignal(str)
    commitActivated = pyqtSignal(str)
    commitContextRequested = pyqtSignal(str, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumWidth(80)
        self.selected_hash = ""
        self.node_items: Dict[str, CommitNodeItem] = {}
        self.setBackgroundBrush(QBrush(QColor("#020617")))

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
            node.set_selected(h == commit_hash)
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

        positions, lanes = self._layout_positions(commits)
        max_lane = max(lanes.values(), default=0)
        self._draw_lane_backgrounds(max_lane, len(commits))

        for commit in commits:
            if commit.hash not in positions:
                continue
            x1, y1 = positions[commit.hash]
            lane = lanes.get(commit.hash, 0)
            color = QColor(LANE_COLORS[lane % len(LANE_COLORS)])
            for parent in commit.parents:
                if parent in positions:
                    x2, y2 = positions[parent]
                    self._add_edge(QPointF(x1, y1), QPointF(x2, y2), color)

        for commit in commits:
            if commit.hash not in positions:
                continue
            x, y = positions[commit.hash]
            lane = lanes.get(commit.hash, 0)
            color = LANE_COLORS[lane % len(LANE_COLORS)]
            node = CommitNodeItem(commit, self, x, y, color)
            self.scene_obj.addItem(node)
            self.node_items[commit.hash] = node
            self._add_commit_label(commit, x, y, QColor(color))

        self.scene_obj.setSceneRect(self.scene_obj.itemsBoundingRect().adjusted(-80, -80, 320, 120))
        self.fitInView(self.scene_obj.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _layout_positions(self, commits: List[GraphCommit]) -> Tuple[Dict[str, tuple[float, float]], Dict[str, int]]:
        lane_width = 64.0
        row_height = 58.0
        x_origin = 56.0
        y_origin = 44.0
        active_lanes: List[str] = []
        positions: Dict[str, tuple[float, float]] = {}
        lanes: Dict[str, int] = {}

        for row, commit in enumerate(commits):
            if commit.hash in active_lanes:
                lane = active_lanes.index(commit.hash)
            else:
                lane = len(active_lanes)
                active_lanes.append(commit.hash)
            lanes[commit.hash] = lane
            positions[commit.hash] = (x_origin + lane * lane_width, y_origin + row * row_height)

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

        return positions, lanes

    def _draw_lane_backgrounds(self, max_lane: int, rows: int) -> None:
        lane_width = 64.0
        row_height = 58.0
        height = max(360.0, rows * row_height + 90)
        for lane in range(max_lane + 1):
            x = 56.0 + lane * lane_width
            color = QColor(LANE_COLORS[lane % len(LANE_COLORS)])
            color.setAlpha(22)
            rect = QGraphicsRectItem(x - 24, 12, 48, height)
            rect.setBrush(QBrush(color))
            rect.setPen(QPen(Qt.PenStyle.NoPen))
            rect.setZValue(-10)
            self.scene_obj.addItem(rect)

    def _add_edge(self, start: QPointF, end: QPointF, color: QColor) -> None:
        path = QPainterPath(start)
        mid_y = (start.y() + end.y()) / 2
        dx = max(18.0, abs(end.x() - start.x()) * 0.45)
        path.cubicTo(QPointF(start.x(), mid_y - dx * 0.15), QPointF(end.x(), mid_y + dx * 0.15), end)
        edge = QGraphicsPathItem(path)
        edge_color = QColor(color)
        edge_color.setAlpha(210)
        edge.setPen(QPen(edge_color, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        edge.setZValue(1)
        self.scene_obj.addItem(edge)

        angle = atan2(end.y() - start.y(), end.x() - start.x())
        arrow_size = 8.0
        arrow_tip = QPointF(end.x(), end.y() - 15)
        p1 = QPointF(arrow_tip.x() - arrow_size * cos(angle - 0.52), arrow_tip.y() - arrow_size * sin(angle - 0.52))
        p2 = QPointF(arrow_tip.x() - arrow_size * cos(angle + 0.52), arrow_tip.y() - arrow_size * sin(angle + 0.52))
        arrow = QGraphicsPolygonItem(QPolygonF([arrow_tip, p1, p2]))
        arrow.setBrush(QBrush(edge_color))
        arrow.setPen(QPen(edge_color, 1))
        arrow.setZValue(2)
        self.scene_obj.addItem(arrow)

    def _add_commit_label(self, commit: GraphCommit, x: float, y: float, color: QColor) -> None:
        label_x = x + 24
        label_y = y - 17
        # Keep graph nodes/labels compact. Details are shown in the side detail
        # panel on hover/click.
        refs = commit.refs.replace("<", "&lt;").replace(">", "&gt;")
        html = f"<span style='color:#e5e7eb; font-weight:700'>{commit.date}</span>"
        if refs:
            html += f" <span style='color:{color.name()}; font-weight:700'>●</span>"
        text = QGraphicsTextItem()
        font = QFont("Segoe UI", 9)
        text.setFont(font)
        text.setHtml(html)
        text.setPos(label_x, label_y)
        text.setToolTip(commit.tooltip)
        text.setZValue(12)
        self.scene_obj.addItem(text)

        # Soft label background capsule.
        bounds = text.boundingRect().adjusted(-8, -3, 8, 3)
        bg = QGraphicsRectItem(bounds)
        bg.setPos(label_x, label_y)
        bg.setBrush(QBrush(QColor(15, 23, 42, 210)))
        bg.setPen(QPen(QColor(51, 65, 85, 180), 1))
        bg.setZValue(11)
        self.scene_obj.addItem(bg)
