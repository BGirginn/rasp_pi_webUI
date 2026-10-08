import { useEffect, useState } from 'react';
import { useDashboard } from '../contexts/DashboardContext';
import { useTheme } from '../contexts/ThemeContext';
import { WidgetWrapper } from './WidgetWrapper';
import { WidgetRenderer } from './WidgetRenderer';
import { AddWidgetButton } from './AddWidgetButton';
export function DashboardGrid() {
    const { widgets, moveWidget } = useDashboard();
    const { isEditMode, isDarkMode } = useTheme();
    const getColumnCount = () => {
        if (typeof window === 'undefined') {
            return 4;
        }
        if (window.innerWidth < 768) {
            return 1;
        }
        if (window.innerWidth < 1280) {
            return 2;
        }
        return 4;
    };
    const [columns, setColumns] = useState(getColumnCount);

    useEffect(() => {
        const handleResize = () => setColumns(getColumnCount());
        handleResize();
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

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
        const cellWidth = rect.width / columns;
        const cellHeight = 250; // approximate row height
        const col = Math.floor(x / cellWidth);
        const row = Math.floor(y / cellHeight);
        moveWidget(widgetId, { row: Math.max(0, row), col: Math.max(0, Math.min(columns - 1, col)) });
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
    return (<div className="dashboard-grid space-y-6">
      <div className="grid gap-4 md:gap-6 auto-rows-[220px] md:auto-rows-[240px]" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }} onDrop={handleDrop} onDragOver={handleDragOver}>
        {sortedWidgets.map((widget) => (<WidgetWrapper key={widget.id} widget={widget} columns={columns}>
            <WidgetRenderer widget={widget}/>
          </WidgetWrapper>))}
      </div>

      {isEditMode && <AddWidgetButton />}
    </div>);
}
