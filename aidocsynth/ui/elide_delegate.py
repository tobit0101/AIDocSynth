from PySide6.QtWidgets import QStyledItemDelegate, QApplication, QStyle
from PySide6.QtCore import Qt

class ElideDelegate(QStyledItemDelegate):
    """A delegate that elides text from the left.

    This is useful for file paths, where the end of the path is more
    important than the beginning.
    """
    def paint(self, painter, option, index):
        # 1. Let the base class set up the option object with current state (font, colors, etc.)
        super().initStyleOption(option, index)

        # 2. Draw the item's background and selection state, but not the text.
        # PE_PanelItemViewItem is the primitive for the background of an item.
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, option.widget)

        # 3. Calculate the rectangle where the text should be drawn.
        text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, option, option.widget)
        original_text = option.text

        # 4. Elide the text if it's too wide for the available space.
        elided_text = option.fontMetrics.elidedText(
            original_text,
            Qt.ElideLeft,
            text_rect.width()
        )

        # 5. Draw the elided text manually.
        # The painter's pen is already set correctly by initStyleOption.
        painter.drawText(text_rect, option.displayAlignment, elided_text)
