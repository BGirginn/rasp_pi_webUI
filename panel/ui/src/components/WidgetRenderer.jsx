import { CPUWidget } from './widgets/CPUWidget';
import { MemoryWidget } from './widgets/MemoryWidget';
import { DiskWidget } from './widgets/DiskWidget';
import { TemperatureWidget } from './widgets/TemperatureWidget';
import { PerformanceWidget } from './widgets/PerformanceWidget';
import { NetworkWidget } from './widgets/NetworkWidget';
import { ProcessesWidget } from './widgets/ProcessesWidget';
import { SystemInfoWidget } from './widgets/SystemInfoWidget';
export function WidgetRenderer({ widget }) {
    const { type, variant, width, height } = widget;
    switch (type) {
        case 'cpu':
            return <CPUWidget variant={variant} width={width} height={height}/>;
        case 'memory':
            return <MemoryWidget variant={variant} width={width} height={height}/>;
        case 'disk':
            return <DiskWidget variant={variant} width={width} height={height}/>;
        case 'temperature':
            return <TemperatureWidget variant={variant} width={width} height={height}/>;
        case 'performance':
            return <PerformanceWidget variant={variant} width={width} height={height}/>;
        case 'network':
            return <NetworkWidget variant={variant} width={width} height={height}/>;
        case 'processes':
            return <ProcessesWidget variant={variant} width={width} height={height}/>;
        case 'system-info':
            return <SystemInfoWidget variant={variant} width={width} height={height}/>;
        default:
            return null;
    }
}
