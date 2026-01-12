import { useDashboard } from '../contexts/DashboardContext';
import { useTheme } from '../contexts/ThemeContext';
import { WidgetWrapper } from './WidgetWrapper';
import { WidgetRenderer } from './WidgetRenderer';
import { AddWidgetButton } from './AddWidgetButton';
export function DashboardGrid() {
    const { widgets, moveWidget } = useDashboard();
    const { isEditMode, isDarkMode } = useTheme();
    const handleDrop = (e) => {
        e.preventDefault();
        const widgetId = e.dataTransfer.getData('widgetId');
        if (!widgetId)
            return;
        // Calculate drop position based on grid
        const grid = e.currentTarget;
        const rect = grid.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const cellWidth = rect.width / 4;
        const cellHeight = 250; // approximate row height
        const col = Math.floor(x / cellWidth);
        const row = Math.floor(y / cellHeight);
        moveWidget(widgetId, { row: Math.max(0, row), col: Math.max(0, Math.min(3, col)) });
    };
    const handleDragOver = (e) => {
        e.preventDefault();
    };
    // Sort widgets by position
    const sortedWidgets = [...widgets].sort((a, b) => {
        if (a.position.row === b.position.row) {
            return a.position.col - b.position.col;
        }
        return a.position.row - b.position.row;
    });
    return (<div className="space-y-6">
      <div className="grid grid-cols-4 gap-6 auto-rows-[240px]" onDrop={handleDrop} onDragOver={handleDragOver}>
        {sortedWidgets.map((widget) => (<WidgetWrapper key={widget.id} widget={widget}>
            <WidgetRenderer widget={widget}/>
          </WidgetWrapper>))}
      </div>

      {isEditMode && <AddWidgetButton />}
    </div>);
}
