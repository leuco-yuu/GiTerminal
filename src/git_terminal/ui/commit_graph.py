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
        self.theme_mode = "dark"
        self.set_theme("dark")

    def set_theme(self, mode: str = "dark") -> None:
        self.theme_mode = mode
        self.setBackgroundBrush(QBrush(QColor("#ffffff" if mode == "light" else "#1e1e1e")))

    def wheelEvent(self, event):  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
        else:
            # The directed graph canvas stays visually fixed on normal wheel events.
            # Only Ctrl+wheel zooms; the detail list owns its own small scrollbars.
            event.accept()

    def select_commit(self, commit_hash: str) -> None:
        self.selected_hash = commit_hash
        for h, node in self.node_items.items():
            node.set_selected(h == commit_hash)
        self.commitSelected.emit(commit_hash)

    def set_commits(self, commits: Iterable[GraphCommit]) -> None:
        commits = list(commits)
        had_items = bool(self.node_items)
        previous_transform = self.transform()
        previous_center = self.mapToScene(self.viewport().rect().center())
        previous_selected = self.selected_hash
        self.scene_obj.clear()
        self.node_items.clear()
        if not commits:
            self.selected_hash = ""
            text = self.scene_obj.addText("没有提交历史。打开一个 Git 仓库后点击刷新。")
            text.setDefaultTextColor(QColor("#94a3b8"))
            return

        # The raw git log arrives newest -> oldest. Draw oldest on the left and
        # newest on the right, Mermaid LR style, so arrows are old -> new.
        draw_order = list(reversed(commits))
        positions, lanes = self._layout_positions(draw_order)
        max_lane = max(lanes.values(), default=0)
        self._draw_lane_backgrounds(max_lane, len(draw_order))

        # Parent -> child, i.e. old commit -> new commit.
        for commit in draw_order:
            if commit.hash not in positions:
                continue
            child_x, child_y = positions[commit.hash]
            lane = lanes.get(commit.hash, 0)
            color = QColor(LANE_COLORS[lane % len(LANE_COLORS)])
            for parent in commit.parents:
                if parent in positions:
                    parent_x, parent_y = positions[parent]
                    self._add_edge(QPointF(parent_x, parent_y), QPointF(child_x, child_y), color)

        for commit in draw_order:
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
        if previous_selected in self.node_items:
            self.selected_hash = previous_selected
            for h, node in self.node_items.items():
                node.set_selected(h == previous_selected)
        else:
            self.selected_hash = ""
        if had_items:
            self.setTransform(previous_transform)
            self.centerOn(previous_center)
        else:
            self.fitInView(self.scene_obj.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _layout_positions(self, commits: List[GraphCommit]) -> Tuple[Dict[str, tuple[float, float]], Dict[str, int]]:
        # Commits are oldest -> newest. Lay them out horizontally: time flows
        # left-to-right, lanes stack vertically like a compact Mermaid LR graph.
        column_width = 128.0
        lane_height = 74.0
        x_origin = 64.0
        y_origin = 58.0
        positions: Dict[str, tuple[float, float]] = {}
        lanes: Dict[str, int] = {}
        next_lane = 0
        child_counts: Dict[str, int] = {}

        for col, commit in enumerate(commits):
            lane = None
            if commit.parents:
                first_parent = commit.parents[0]
                if first_parent in lanes:
                    used_children = child_counts.get(first_parent, 0)
                    if used_children == 0:
                        lane = lanes[first_parent]
                    else:
                        lane = next_lane
                        next_lane += 1
                    child_counts[first_parent] = used_children + 1

            if lane is None:
                lane = next_lane
                next_lane += 1

            lanes[commit.hash] = lane
            positions[commit.hash] = (x_origin + col * column_width, y_origin + lane * lane_height)

        return positions, lanes

    def _draw_lane_backgrounds(self, max_lane: int, cols: int) -> None:
        column_width = 128.0
        lane_height = 74.0
        width = max(520.0, cols * column_width + 120)
        for lane in range(max_lane + 1):
            y = 58.0 + lane * lane_height
            color = QColor(LANE_COLORS[lane % len(LANE_COLORS)])
            color.setAlpha(14 if self.theme_mode == "dark" else 24)
            rect = QGraphicsRectItem(24, y - 27, width, 54)
            rect.setBrush(QBrush(color))
            border = QColor(color)
            border.setAlpha(34 if self.theme_mode == "dark" else 55)
            rect.setPen(QPen(border, 1))
            rect.setZValue(-10)
            self.scene_obj.addItem(rect)

    def _add_edge(self, start: QPointF, end: QPointF, color: QColor) -> None:
        # Straight old -> new edge. Start/end are node centers.
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = max(1.0, (dx * dx + dy * dy) ** 0.5)
        ux, uy = dx / length, dy / length
        line_start = QPointF(start.x() + ux * 18.0, start.y() + uy * 18.0)
        line_end = QPointF(end.x() - ux * 18.0, end.y() - uy * 18.0)

        path = QPainterPath(line_start)
        path.lineTo(line_end)
        edge = QGraphicsPathItem(path)
        edge_color = QColor(color)
        edge_color.setAlpha(220)
        edge.setPen(QPen(edge_color, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        edge.setZValue(1)
        self.scene_obj.addItem(edge)

        arrow_tip = line_end
        base = QPointF(arrow_tip.x() - ux * 11.0, arrow_tip.y() - uy * 11.0)
        px, py = -uy, ux
        p1 = QPointF(base.x() + px * 5.8, base.y() + py * 5.8)
        p2 = QPointF(base.x() - px * 5.8, base.y() - py * 5.8)
        arrow = QGraphicsPolygonItem(QPolygonF([arrow_tip, p1, p2]))
        arrow.setBrush(QBrush(edge_color))
        arrow.setPen(QPen(edge_color, 1))
        arrow.setZValue(2)
        self.scene_obj.addItem(arrow)

    def _add_commit_label(self, commit: GraphCommit, x: float, y: float, color: QColor) -> None:
        label_x = x - 34
        label_y = y + 20
        # Keep node text compact: date only. Details are shown in the side panel.
        label_color = "#1f2937" if self.theme_mode == "light" else "#d4d4d4"
        display_date = commit.date
        if len(display_date) >= 16 and display_date[4] == "-":
            display_date = display_date[5:]
        html = f"<span style='color:{label_color}; font-weight:700'>{display_date}</span>"
        text = QGraphicsTextItem()
        font = QFont("Segoe UI", 9)
        text.setFont(font)
        text.setHtml(html)
        text.setPos(label_x, label_y)
        text.setToolTip(commit.tooltip)
        text.setZValue(12)
        self.scene_obj.addItem(text)

        bounds = text.boundingRect().adjusted(-8, -3, 8, 3)
        bg = QGraphicsRectItem(bounds)
        bg.setPos(label_x, label_y)
        bg.setBrush(QBrush(QColor(255, 255, 255, 225) if self.theme_mode == "light" else QColor(37, 37, 38, 220)))
        bg.setPen(QPen(QColor(209, 213, 219, 220) if self.theme_mode == "light" else QColor(68, 68, 68, 190), 1))
        bg.setZValue(11)
        self.scene_obj.addItem(bg)

        branch_name = self._branch_label(commit.refs)
        if branch_name:
            tag_x = x + 24
            tag_y = y - 34
            callout = QPainterPath(QPointF(x + 9, y - 9))
            callout.lineTo(QPointF(tag_x, tag_y + 10))
            callout_item = QGraphicsPathItem(callout)
            call_color = QColor(color)
            call_color.setAlpha(180)
            callout_item.setPen(QPen(call_color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            callout_item.setZValue(9)
            self.scene_obj.addItem(callout_item)

            tag = QGraphicsTextItem()
            tag.setFont(QFont("Segoe UI", 8))
            safe = branch_name.replace("<", "&lt;").replace(">", "&gt;")
            tag.setHtml(f"<span style='color:white; font-weight:700'>{safe}</span>")
            tag.setPos(tag_x, tag_y)
            tag.setToolTip(commit.tooltip)
            tag.setZValue(14)
            self.scene_obj.addItem(tag)
            tb = tag.boundingRect().adjusted(-7, -3, 7, 3)
            tag_bg = QGraphicsRectItem(tb)
            tag_bg.setPos(tag_x, tag_y)
            fill = QColor(color)
            fill.setAlpha(215)
            tag_bg.setBrush(QBrush(fill))
            tag_bg.setPen(QPen(QColor("#ffffff"), 0.8))
            tag_bg.setZValue(13)
            self.scene_obj.addItem(tag_bg)

    def _branch_label(self, refs: str) -> str:
        if not refs:
            return ""
        names = [r.strip() for r in refs.split(",") if r.strip()]
        cleaned = []
        for name in names:
            name = name.replace("HEAD ->", "").strip()
            if name == "HEAD":
                continue
            # Prefer human branch/tag names over remote bookkeeping.
            cleaned.append(name)
        if not cleaned:
            return ""
        label = cleaned[0]
        if len(label) > 28:
            label = label[:25] + "…"
        return label
