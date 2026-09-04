from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class WeeklyPerformanceChart(QWidget):
    """Dependency-free premium area chart used by the executive overview."""

    def __init__(self) -> None:
        super().__init__(objectName="weeklyPerformanceChart")
        self._values = (0, 0, 0, 0, 0, 0, 0)
        self._labels = ("—",) * 7
        self.setMinimumHeight(125)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("Desempenho semanal das oportunidades")

    def set_values(self, values: Iterable[int]) -> None:
        cleaned = tuple(max(0, int(value)) for value in values)
        self._values = cleaned or (0,)
        self.update()

    def set_series(self, values: Iterable[int], labels: Iterable[str]) -> None:
        self._values = tuple(max(0, int(value)) for value in values) or (0,)
        cleaned_labels = tuple(str(label)[:8] for label in labels)
        self._labels = cleaned_labels if len(cleaned_labels) == len(self._values) else ("—",) * len(self._values)
        self.setAccessibleDescription(
            ", ".join(f"{label}: {value}" for label, value in zip(self._labels, self._values, strict=True))
        )
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect().adjusted(12, 10, -12, -22)
        painter.setPen(QPen(QColor("#21304A"), 1))
        for row in range(4):
            y = area.top() + row * area.height() / 3
            painter.drawLine(area.left(), int(y), area.right(), int(y))
        maximum = max(max(self._values), 1)
        step = area.width() / max(len(self._values) - 1, 1)
        points = [
            QPointF(area.left() + index * step, area.bottom() - value / maximum * area.height())
            for index, value in enumerate(self._values)
        ]
        line = QPainterPath(points[0])
        for index in range(1, len(points)):
            previous = points[index - 1]
            current = points[index]
            midpoint = (previous.x() + current.x()) / 2
            line.cubicTo(midpoint, previous.y(), midpoint, current.y(), current.x(), current.y())
        fill = QPainterPath(line)
        fill.lineTo(points[-1].x(), area.bottom())
        fill.lineTo(points[0].x(), area.bottom())
        fill.closeSubpath()
        gradient = QLinearGradient(0, area.top(), 0, area.bottom())
        gradient.setColorAt(0, QColor(124, 92, 255, 125))
        gradient.setColorAt(1, QColor(71, 55, 160, 8))
        painter.fillPath(fill, gradient)
        painter.setPen(QPen(QColor("#9A72FF"), 2))
        painter.drawPath(line)
        painter.setPen(QColor("#687896"))
        for index in range(len(self._values)):
            painter.drawText(
                QRectF(area.left() + index * step - 10, area.bottom() + 6, 20, 14),
                Qt.AlignmentFlag.AlignCenter,
                self._labels[index] if index < len(self._labels) else "—",
            )


class FunnelDonut(QWidget):
    def __init__(self) -> None:
        super().__init__(objectName="funnelDonut")
        self._values = (0, 0, 0, 0, 0, 0)
        self._colors = ("#7C5CFF", "#38A4FF", "#43D697", "#F2B84B")
        self.setMinimumSize(120, 120)
        self.setAccessibleName("Distribuição percentual do funil")

    def set_values(self, values: Iterable[int]) -> None:
        cleaned = tuple(max(0, int(value)) for value in values)
        self._values = cleaned or (1,)
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height()) - 18
        ring = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        total = max(sum(self._values), 1)
        start = 90 * 16
        pen = QPen()
        pen.setWidth(max(10, side // 9))
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        for index, value in enumerate(self._values):
            span = -round(value / total * 360 * 16)
            pen.setColor(QColor(self._colors[index % len(self._colors)]))
            painter.setPen(pen)
            painter.drawArc(ring.adjusted(pen.width() / 2, pen.width() / 2,
                                          -pen.width() / 2, -pen.width() / 2), start, span)
            start += span
