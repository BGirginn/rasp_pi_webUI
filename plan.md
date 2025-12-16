# 🔌 Figma UI → Real-Time API Migration Rehberi

> **Proje Durumu:**
> - ✅ Backend API: Raspberry Pi üzerinde çalışıyor
> - ✅ Figma UI: Tasarım tamamlandı (mock data ile)
> - ⚠️ Mevcut GUI: Çalışıyor ama görsel olarak yetersiz
> - 🎯 Hedef: Figma tasarımını real-time API ile çalıştırmak

---

## � İçindekiler

1. [Proje Bilgileri](#-proje-bilgileri)
2. [Migration Planı](#-migration-planı)
   - [Adım 1: Envanter Çıkarma](#adım-1-envanter-çıkarma)
   - [Adım 2: Altyapı Kurulumu](#adım-2-altyapı-kurulumu)
   - [Adım 3: Type Definitions](#adım-3-type-definitions)
   - [Adım 4: Component Migration Stratejisi](#adım-4-component-migration-stratejisi)
   - [Adım 5: Test ve Rollback Stratejisi](#adım-5-test-ve-rollback-stratejisi)
3. [Yaygın Senaryolar ve Çözümleri](#-yaygın-senaryolar-ve-çözümleri-genişletilmiş)
   - [Senaryo 1: Tablo Verisi](#senaryo-1-tablo-verisi-devices-services-processes)
   - [Senaryo 2: Chart Data](#senaryo-2-chart-data-zaman-serisi-grafikleri)
   - [Senaryo 3: Service Control](#senaryo-3-service-control-startstop-actions)
   - [Senaryo 4: Real-Time Logs](#senaryo-4-real-time-logs-websocket-stream)
4. [Migration Checklist](#-komple-migration-checklist-detaylı)
5. [Yardımcı Araçlar ve Scripts](#️-yardımcı-araçlar-ve-scripts)
6. [Production Ready Checklist](#-production-ready-checklist)
7. [Eksik Implementasyonlar](#-eksik-implementasyonlar)
   - [API Service](#api-service---tam-implementasyon)
   - [Adapter'lar](#services-adapter)
   - [UI Components](#ui-components)
   - [Utility Functions](#utility-functions)
   - [Unit Test Örnekleri](#unit-test-örnekleri)
8. [Hızlı Başlangıç Kılavuzu](#-hızlı-başlangıç-kılavuzu)
9. [Sonuç](#-sonuç)

---

## �📋 Proje Bilgileri

> ⚠️ **NOT:** Aşağıdaki bilgileri kendi projenize göre güncelleyin.

### Backend API Bilgileri

```bash
# API Base URL (örnek)
API_BASE_URL=http://192.168.1.100:8000

# WebSocket URL (varsa)
WS_URL=ws://192.168.1.100:8000/ws
```

### Mevcut API Endpoint'leri

| Endpoint | Method | Açıklama | Response Örneği |
|----------|--------|----------|-----------------|
| `/api/telemetry/current` | GET | Anlık sistem metrikleri | `{ "cpu": { "usage": 45 }, "memory": { "percent": 72 } }` |
| `/api/telemetry/history` | GET | Geçmiş metrikler | `{ "telemetry": [...], "duration": "1h" }` |
| `/api/devices/list` | GET | Bağlı cihazlar | `{ "devices": { "usb": [...] }, "count": 3 }` |
| `/api/services/list` | GET | Sistem servisleri | `{ "services": [...], "count": 5 }` |
| `/api/logs/recent` | GET | Son loglar | `{ "logs": [...], "total": 100 }` |
| `/api/system/info` | GET | Sistem bilgisi | `{ "hostname": "...", "os": "..." }` |
| `/api/network/status` | GET | Ağ durumu | `{ "network": { "rx_bytes": ..., "tx_bytes": ... } }` |
| `/ws/telemetry` | WS | Canlı telemetry stream | `{ "cpu": ..., "memory": ... }` |
| `/ws/logs` | WS | Canlı log stream | `{ "level": "info", "message": "..." }` |

### Figma Proje Mock Data Dosyaları

```
figma_project/
├── src/
│   ├── data/
│   │   ├── mockData.ts          → Dashboard telemetry verileri
│   │   ├── mockDevices.ts       → USB/Bluetooth cihaz listesi
│   │   ├── mockServices.ts      → Sistem servisleri listesi
│   │   ├── mockLogs.ts          → Log kayıtları
│   │   └── mockCharts.ts        → Grafik zaman serisi verileri
│   └── ...
```

### Örnek API Response Formatları

**Telemetry Endpoint:**
```json
{
  "cpu": {
    "usage": 45.5,
    "temp": 65,
    "cores": [
      { "id": 0, "usage": 42 },
      { "id": 1, "usage": 48 }
    ],
    "load": [1.2, 1.5, 1.8]
  },
  "memory": {
    "used": 3145728000,
    "total": 4294967296,
    "percent": 73.2,
    "swap": { "used": 0, "total": 2147483648 }
  },
  "disk": {
    "used": 15032385536,
    "total": 31268536320,
    "percent": 48.1
  },
  "network": {
    "rx_bytes": 1234567890,
    "tx_bytes": 987654321
  },
  "uptime": 86400,
  "timestamp": "2024-12-16T10:30:00Z"
}
```

**Devices Endpoint:**
```json
{
  "devices": {
    "usb": [
      {
        "id": "usb-001",
        "name": "Kingston DataTraveler",
        "vendor": "Kingston",
        "product": "USB 3.0 Drive",
        "status": "connected",
        "path": "/dev/sda1",
        "size_bytes": 64424509440,
        "mount_point": "/media/usb1"
      }
    ],
    "bluetooth": [
      {
        "id": "bt-001",
        "name": "Wireless Mouse",
        "address": "00:1A:7D:DA:71:13",
        "connected": true,
        "type": "input"
      }
    ]
  },
  "count": 2
}
```

**Services Endpoint:**
```json
{
  "services": [
    {
      "id": "nginx",
      "name": "nginx",
      "status": "running",
      "enabled": true,
      "description": "A high performance web server"
    },
    {
      "id": "docker",
      "name": "docker",
      "status": "stopped",
      "enabled": false,
      "description": "Docker container runtime"
    }
  ],
  "count": 2
}
```

---

## 🚀 Migration Planı

### Adım 1: Envanter Çıkarma

#### 1.1: Figma Projesindeki Mock Data'ları Listele

```bash
# Figma proje dizininde çalıştır
cd /path/to/figma_project

# Mock data dosyalarını bul
find src -type f \( -name "*mock*" -o -name "*Mock*" \) 2>/dev/null

# Mock import'larını bul
grep -r "import.*mock" src --include="*.ts" --include="*.tsx" 2>/dev/null
```

#### 1.2: Her Mock Data İçin API Mapping Tablosu Oluştur

| Mock Data | Mock Format | API Endpoint | API Format | Adapter Gerekli |
|-----------|-------------|--------------|------------|-----------------|
| `mockDashboard` | `{ cpuUsage: 45 }` | `/api/telemetry` | `{ cpu: { usage: 45 } }` | ✅ Evet |
| `mockDevices` | `[{ id: 1, name: "USB" }]` | `/api/devices` | `{ devices: { usb: [...] } }` | ✅ Evet |
| _______________ | _______________ | _______________ | _______________ | ___ |

---

### Adım 2: Altyapı Kurulumu

#### 2.1: Gerekli Dosya Yapısı

```
src/
├── adapters/           # API → Mock format dönüştürücüler
│   ├── index.ts
│   ├── telemetry.adapter.ts
│   ├── devices.adapter.ts
│   └── services.adapter.ts
├── hooks/              # Real-time data hooks
│   ├── useRealtimeApi.ts
│   └── useWebSocket.ts
├── services/           # API iletişim katmanı
│   └── api.service.ts
├── types/              # TypeScript tanımları
│   └── api.types.ts
├── config/             # Konfigürasyon
│   ├── api.config.ts
│   └── features.config.ts
└── utils/              # Yardımcı fonksiyonlar
    ├── formatters.ts
    └── validators.ts
```

#### 2.2: Temel Konfigürasyon Dosyaları

**api.config.ts:**
```typescript
// src/config/api.config.ts
export const API_CONFIG = {
  // 🔴 GÜNCELLE: Kendi API URL'ini yaz
  BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  WS_URL: import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws',
  
  // Timeouts
  TIMEOUT: 10000,
  RETRY_COUNT: 3,
  RETRY_DELAY: 1000,
  
  // Polling intervals (ms)
  POLLING: {
    TELEMETRY: 5000,      // 5 saniye
    DEVICES: 10000,       // 10 saniye
    SERVICES: 10000,      // 10 saniye
    LOGS: 0,              // WebSocket kullan
  },
  
  // WebSocket
  WEBSOCKET_ENABLED: true,
  HEARTBEAT_INTERVAL: 30000,
};
```

**features.config.ts:**
```typescript
// src/config/features.config.ts
export const FEATURE_FLAGS = {
  // Development'ta mock, production'da real API
  USE_REAL_API: import.meta.env.VITE_USE_REAL_API === 'true',
  USE_WEBSOCKET: import.meta.env.VITE_WEBSOCKET_ENABLED === 'true',
  
  // Feature bazlı geçiş (kademeli migration için)
  FEATURES: {
    TELEMETRY: import.meta.env.VITE_USE_REAL_API === 'true',
    DEVICES: import.meta.env.VITE_USE_REAL_API === 'true',
    SERVICES: false,  // Henüz mock kullan
    LOGS: false,      // Henüz mock kullan
  }
};
```

**.env.example:**
```bash
# API Configuration
VITE_API_BASE_URL=http://192.168.1.100:8000
VITE_WS_URL=ws://192.168.1.100:8000/ws

# Feature Flags
VITE_USE_REAL_API=false
VITE_WEBSOCKET_ENABLED=false
```

---

### Adım 3: Type Definitions

#### 3.1: API Response Types

```typescript
// src/types/api.types.ts

// ====== TELEMETRY ======
export interface TelemetryResponse {
  cpu: {
    usage: number;
    temp: number;
    cores?: Array<{ id: number; usage: number }>;
    load?: number[];
  };
  memory: {
    used: number;
    total: number;
    percent: number;
    swap?: { used: number; total: number };
  };
  disk: {
    used: number;
    total: number;
    percent: number;
  };
  network: {
    rx_bytes: number;
    tx_bytes: number;
  };
  uptime: number;
  timestamp: string;
}

// ====== DEVICES ======
export interface USBDevice {
  id: string;
  name: string;
  vendor: string;
  product: string;
  status: 'connected' | 'disconnected';
  path: string;
  size_bytes?: number;
  mount_point?: string;
}

export interface BluetoothDevice {
  id: string;
  name: string;
  address: string;
  connected: boolean;
  type?: string;
}

export interface DevicesResponse {
  devices: {
    usb: USBDevice[];
    bluetooth?: BluetoothDevice[];
  };
  count: number;
}

// ====== SERVICES ======
export interface SystemService {
  id: string;
  name: string;
  status: 'running' | 'stopped' | 'failed';
  enabled: boolean;
  description?: string;
}

export interface ServicesResponse {
  services: SystemService[];
  count: number;
}

// ====== LOGS ======
export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
  source?: string;
}

export interface LogsResponse {
  logs: LogEntry[];
  total: number;
}

// ====== GENERIC ======
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ApiError;
}
```

#### 3.2: Mock Data Types (Figma formatı)

```typescript
// src/types/mock.types.ts

// Figma UI'ın beklediği formatlar
// 🔴 GÜNCELLE: Kendi Figma mock data formatlarını yaz

export interface MockTelemetry {
  cpuUsage: number;
  memoryUsage: number;
  diskUsage: number;
  temperature: number;
  timestamp: string;
}

export interface MockDevice {
  id: number;
  name: string;
  type: string;
  status: 'connected' | 'disconnected';
  icon?: string;
}

export interface MockService {
  name: string;
  status: 'running' | 'stopped';
  autostart: boolean;
}

export interface MockLog {
  id: number;
  timestamp: string;
  level: string;
  message: string;
}
```

---

### Adım 4: Component Migration Stratejisi

#### 4.1: Düşük Riskli Component'lerden Başla

**Öncelik Sırası:**
1. ✅ **Info Cards** (CPU, Memory, Disk) - Basit metrics
2. ✅ **Device Lists** - CRUD operasyonları yok
3. ⚠️ **Service Manager** - Start/Stop actions var
4. ⚠️ **Log Viewer** - Real-time stream gerekli
5. 🔴 **System Config** - Write operasyonları kritik

#### 4.2: Migration Template

```typescript
// BEFORE: Mock Data
import { mockData } from '../data/mockData';

function MyComponent() {
  const data = mockData;
  return <div>{data.value}</div>;
}

// ===============================================

// AFTER: Real-Time API
import { useRealtimeApi } from '../hooks/useRealtimeApi';
import { apiService } from '../services/api.service';
import { apiToMock } from '../adapters/myFeature.adapter';

function MyComponent() {
  const { data: apiData, loading, error } = useRealtimeApi(
    () => apiService.myFeature.get(),
    { refreshInterval: 5000 }
  );

  if (loading && !apiData) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  if (!apiData) return null;

  const data = apiToMock(apiData);
  return <div>{data.value}</div>;
}
```

### Adım 5: Test ve Rollback Stratejisi

#### 5.1: Feature Flag Pattern

```typescript
// src/config/features.config.ts
export const FEATURE_FLAGS = {
  USE_REAL_API_TELEMETRY: import.meta.env.VITE_USE_REAL_API === 'true',
  USE_REAL_API_DEVICES: import.meta.env.VITE_USE_REAL_API === 'true',
  USE_WEBSOCKET: import.meta.env.VITE_WEBSOCKET_ENABLED === 'true'
};

// Component içinde kullanım
import { FEATURE_FLAGS } from '../config/features.config';
import { mockData } from '../data/mockData';

function Dashboard() {
  // Feature flag ile mock/real arasında geçiş
  const useMockData = !FEATURE_FLAGS.USE_REAL_API_TELEMETRY;

  const { data: apiData } = useRealtimeApi(
    () => apiService.telemetry.getCurrent(),
    { 
      refreshInterval: 5000,
      enabled: !useMockData  // Mock mode'da API çağrılarını devre dışı bırak
    }
  );

  const data = useMockData ? mockData : (apiData ? apiToMock(apiData) : null);

  return <MetricsCard data={data} />;
}
```

#### 5.2: Environment Variables

```bash
# .env.development (mock data)
VITE_USE_REAL_API=false
VITE_API_BASE_URL=http://localhost:3000
VITE_WEBSOCKET_ENABLED=false

# .env.production (real API)
VITE_USE_REAL_API=true
VITE_API_BASE_URL=http://192.168.1.100:8000
VITE_WEBSOCKET_ENABLED=true
```

---

## 🔥 Yaygın Senaryolar ve Çözümleri (Genişletilmiş)

### Senaryo 1: Tablo Verisi (Devices, Services, Processes)

**Mock Data:**
```typescript
// src/data/mockDevices.ts
export const mockDevices = [
  { id: 1, name: "USB Drive", status: "connected", size: "64GB" },
  { id: 2, name: "Mouse", status: "connected", vendor: "Logitech" },
  { id: 3, name: "Keyboard", status: "disconnected", vendor: "Corsair" }
];
```

**API Response:**
```typescript
{
  devices: {
    usb: [
      {
        id: "usb-001",
        name: "Kingston DataTraveler",
        vendor: "Kingston",
        product: "USB 3.0 Drive",
        status: "connected",
        path: "/dev/sda1",
        size_bytes: 64424509440,
        mount_point: "/media/usb1"
      }
    ]
  },
  count: 1
}
```

**Kapsamlı Adapter:**
```typescript
// src/adapters/devices.adapter.ts

export interface MockDevice {
  id: number;
  name: string;
  status: 'connected' | 'disconnected';
  size?: string;
  vendor?: string;
  mountPoint?: string;
}

export function apiDevicesToMock(apiResponse: any): MockDevice[] {
  if (!apiResponse?.devices?.usb) return [];

  return apiResponse.devices.usb.map((device: any, index: number) => ({
    id: index + 1,
    name: device.product || device.name,
    status: device.status === 'connected' ? 'connected' : 'disconnected',
    size: device.size_bytes ? formatBytes(device.size_bytes) : undefined,
    vendor: device.vendor,
    mountPoint: device.mount_point
  }));
}

// Helper: bytes → human readable
function formatBytes(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }

  return `${size.toFixed(1)} ${units[unitIndex]}`;
}
```

**Component Migration:**
```typescript
// src/components/DevicesList.tsx

// BEFORE
import { mockDevices } from '../data/mockDevices';

function DevicesList() {
  const devices = mockDevices;
  
  return (
    <table>
      {devices.map(device => (
        <tr key={device.id}>
          <td>{device.name}</td>
          <td>{device.status}</td>
        </tr>
      ))}
    </table>
  );
}

// ===============================================

// AFTER
import { useRealtimeApi } from '../hooks/useRealtimeApi';
import { apiService } from '../services/api.service';
import { apiDevicesToMock } from '../adapters/devices.adapter';

function DevicesList() {
  const { data: apiData, loading, error, lastUpdate } = useRealtimeApi(
    () => apiService.devices.list(),
    { refreshInterval: 10000 }  // 10 saniyede bir güncelle
  );

  if (loading && !apiData) {
    return <TableSkeleton rows={3} />;
  }

  if (error) {
    return <ErrorBanner message={error} />;
  }

  const devices = apiData ? apiDevicesToMock(apiData) : [];

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2>Connected Devices ({devices.length})</h2>
        {lastUpdate && (
          <span className="text-sm text-gray-500">
            Last checked: {lastUpdate.toLocaleTimeString()}
          </span>
        )}
      </div>
      
      <table className="w-full">
        <thead>
          <tr>
            <th>Name</th>
            <th>Vendor</th>
            <th>Status</th>
            <th>Size</th>
            <th>Mount Point</th>
          </tr>
        </thead>
        <tbody>
          {devices.length === 0 ? (
            <tr>
              <td colSpan={5} className="text-center text-gray-500 py-8">
                No devices connected
              </td>
            </tr>
          ) : (
            devices.map(device => (
              <tr key={device.id}>
                <td>{device.name}</td>
                <td>{device.vendor || 'Unknown'}</td>
                <td>
                  <StatusBadge status={device.status} />
                </td>
                <td>{device.size || 'N/A'}</td>
                <td>{device.mountPoint || 'Not mounted'}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
```

### Senaryo 2: Chart Data (Zaman Serisi Grafikleri)

**Mock Data:**
```typescript
// src/data/mockCharts.ts
export const mockChartData = [
  { time: "10:00", cpu: 45, memory: 60, disk: 50 },
  { time: "10:05", cpu: 50, memory: 65, disk: 52 },
  { time: "10:10", cpu: 48, memory: 63, disk: 51 },
  { time: "10:15", cpu: 52, memory: 67, disk: 53 }
];
```

**API Response:**
```typescript
{
  telemetry: [
    {
      timestamp: "2024-12-16T10:00:00Z",
      cpu: { usage: 45, temp: 65 },
      memory: { percent: 60 },
      disk: { percent: 50 }
    },
    // ... more data points
  ],
  duration: "1h",
  interval: "5m"
}
```

**Chart Adapter:**
```typescript
// src/adapters/charts.adapter.ts

export interface MockChartDataPoint {
  time: string;
  cpu: number;
  memory: number;
  disk: number;
  temperature?: number;
}

export function apiChartToMock(apiResponse: any): MockChartDataPoint[] {
  if (!apiResponse?.telemetry) return [];

  return apiResponse.telemetry.map((point: any) => ({
    time: formatTimeForChart(point.timestamp),
    cpu: Math.round(point.cpu?.usage ?? 0),
    memory: Math.round(point.memory?.percent ?? 0),
    disk: Math.round(point.disk?.percent ?? 0),
    temperature: point.cpu?.temp ? Math.round(point.cpu.temp) : undefined
  }));
}

// Helper: ISO timestamp → chart format
function formatTimeForChart(isoString: string): string {
  const date = new Date(isoString);
  
  // Format: "10:05" veya "Dec 16 10:05"
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  
  return `${hours}:${minutes}`;
}

// Long format için: "Dec 16, 10:05"
export function formatTimeLong(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}
```

**Chart Component Migration:**
```typescript
// src/components/TelemetryChart.tsx
import React, { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { useRealtimeApi } from '../hooks/useRealtimeApi';
import { apiService } from '../services/api.service';
import { apiChartToMock } from '../adapters/charts.adapter';

interface TelemetryChartProps {
  duration?: '1h' | '6h' | '24h';
}

export function TelemetryChart({ duration = '1h' }: TelemetryChartProps) {
  // API call with selected duration
  const { data: apiData, loading, error } = useRealtimeApi(
    () => apiService.telemetry.getHistory({ duration }),
    { 
      refreshInterval: 30000,  // 30 saniyede bir güncelle
      enabled: true
    }
  );

  // Transform data
  const chartData = useMemo(() => {
    return apiData ? apiChartToMock(apiData) : [];
  }, [apiData]);

  if (loading && chartData.length === 0) {
    return <ChartSkeleton />;
  }

  if (error) {
    return (
      <div className="bg-red-50 p-4 rounded">
        <p className="text-red-800">Failed to load chart data: {error}</p>
      </div>
    );
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <div className="mb-4">
        <h3 className="text-lg font-semibold">System Metrics Over Time</h3>
        <p className="text-sm text-gray-500">
          Showing data for the last {duration}
          {loading && <span className="ml-2">• Updating...</span>}
        </p>
      </div>

      <LineChart width={800} height={400} data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis 
          dataKey="time" 
          label={{ value: 'Time', position: 'insideBottom', offset: -5 }}
        />
        <YAxis 
          label={{ value: 'Usage (%)', angle: -90, position: 'insideLeft' }}
          domain={[0, 100]}
        />
        <Tooltip 
          formatter={(value: number) => `${value}%`}
          labelFormatter={(label) => `Time: ${label}`}
        />
        <Legend />
        
        <Line 
          type="monotone" 
          dataKey="cpu" 
          stroke="#3b82f6" 
          name="CPU"
          strokeWidth={2}
          dot={false}
        />
        <Line 
          type="monotone" 
          dataKey="memory" 
          stroke="#10b981" 
          name="Memory"
          strokeWidth={2}
          dot={false}
        />
        <Line 
          type="monotone" 
          dataKey="disk" 
          stroke="#f59e0b" 
          name="Disk"
          strokeWidth={2}
          dot={false}
        />
        {chartData[0]?.temperature && (
          <Line 
            type="monotone" 
            dataKey="temperature" 
            stroke="#ef4444" 
            name="Temp (°C)"
            strokeWidth={2}
            dot={false}
            yAxisId="temp"
          />
        )}
      </LineChart>

      {chartData.length === 0 && (
        <div className="text-center text-gray-500 py-8">
          No data available for the selected time range
        </div>
      )}
    </div>
  );
}
```

### Senaryo 3: Service Control (Start/Stop Actions)

**Mock Data:**
```typescript
// src/data/mockServices.ts
export const mockServices = {
  nginx: { name: "Nginx", status: "running", autostart: true },
  docker: { name: "Docker", status: "stopped", autostart: false },
  ssh: { name: "SSH Server", status: "running", autostart: true }
};
```

**API Integration:**
```typescript
// src/components/ServiceManager.tsx
import { useRealtimeApi } from '../hooks/useRealtimeApi';
import { apiService } from '../services/api.service';
import { useState } from 'react';

export function ServiceManager() {
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Real-time service status
  const { data: services, loading, error, refresh } = useRealtimeApi(
    () => apiService.resources.list({ type: 'service' }),
    { refreshInterval: 10000 }
  );

  // Service control actions
  const handleServiceAction = async (
    serviceId: string, 
    action: 'start' | 'stop' | 'restart'
  ) => {
    setActionLoading(`${serviceId}-${action}`);
    
    try {
      await apiService.resources.control(serviceId, action);
      
      // Immediate refresh after action
      await refresh();
      
      // Success notification
      console.log(`Service ${serviceId} ${action}ed successfully`);
    } catch (err) {
      console.error(`Failed to ${action} service:`, err);
      // Error notification
    } finally {
      setActionLoading(null);
    }
  };

  if (loading && !services) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={refresh} />;
  }

  return (
    <div className="space-y-4">
      {services?.resources.map(service => (
        <div key={service.id} className="flex items-center justify-between p-4 border rounded">
          <div>
            <h4 className="font-medium">{service.name}</h4>
            <StatusBadge status={service.status} />
          </div>
          
          <div className="flex gap-2">
            {service.status !== 'running' && (
              <button
                onClick={() => handleServiceAction(service.id, 'start')}
                disabled={actionLoading === `${service.id}-start`}
                className="px-3 py-1 bg-green-500 text-white rounded"
              >
                {actionLoading === `${service.id}-start` ? 'Starting...' : 'Start'}
              </button>
            )}
            
            {service.status === 'running' && (
              <>
                <button
                  onClick={() => handleServiceAction(service.id, 'stop')}
                  disabled={actionLoading === `${service.id}-stop`}
                  className="px-3 py-1 bg-red-500 text-white rounded"
                >
                  {actionLoading === `${service.id}-stop` ? 'Stopping...' : 'Stop'}
                </button>
                
                <button
                  onClick={() => handleServiceAction(service.id, 'restart')}
                  disabled={actionLoading === `${service.id}-restart`}
                  className="px-3 py-1 bg-blue-500 text-white rounded"
                >
                  {actionLoading === `${service.id}-restart` ? 'Restarting...' : 'Restart'}
                </button>
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
```

### Senaryo 4: Real-Time Logs (WebSocket Stream)

**Mock Data:**
```typescript
// src/data/mockLogs.ts
export const mockLogs = [
  { id: 1, timestamp: "2024-12-16T10:30:00Z", level: "info", message: "System started" },
  { id: 2, timestamp: "2024-12-16T10:31:00Z", level: "warning", message: "High CPU usage" },
  { id: 3, timestamp: "2024-12-16T10:32:00Z", level: "error", message: "Failed to connect" }
];
```

**WebSocket Implementation:**
```typescript
// src/components/LogViewer.tsx
import React, { useState, useEffect, useRef } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { API_CONFIG } from '../config/api.config';

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
  source?: string;
}

export function LogViewer() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [maxLogs] = useState(100);  // Max logs to keep in memory
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // WebSocket connection for real-time logs
  const wsUrl = `ws://${API_CONFIG.BASE_URL.replace('http://', '')}/ws/logs`;
  
  const { data: newLog, isConnected, error } = useWebSocket<LogEntry>(wsUrl, {
    onMessage: (log) => {
      console.log('New log received:', log);
    },
    reconnectAttempts: 10
  });

  // Add new log to the list
  useEffect(() => {
    if (newLog) {
      setLogs(prev => {
        const updated = [newLog, ...prev];
        // Keep only last N logs
        return updated.slice(0, maxLogs);
      });
    }
  }, [newLog, maxLogs]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'error': return 'text-red-600 bg-red-50';
      case 'warning': return 'text-yellow-600 bg-yellow-50';
      case 'info': return 'text-blue-600 bg-blue-50';
      case 'debug': return 'text-gray-600 bg-gray-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold">System Logs</h2>
          <div className={`px-3 py-1 rounded-full text-sm ${
            isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
          }`}>
            {isConnected ? '🔴 LIVE' : 'Disconnected'}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm">Auto-scroll</span>
          </label>
          
          <button
            onClick={() => setLogs([])}
            className="px-3 py-1 text-sm bg-gray-200 rounded hover:bg-gray-300"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Error message */}
      {error && !isConnected && (
        <div className="p-4 bg-red-50 border-b border-red-200">
          <p className="text-red-800 text-sm">
            ❌ WebSocket connection failed. Logs may be delayed or unavailable.
          </p>
        </div>
      )}

      {/* Logs container */}
      <div className="flex-1 overflow-y-auto p-4 bg-gray-900 text-gray-100 font-mono text-sm">
        {logs.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            {isConnected ? 'Waiting for logs...' : 'Not connected to log stream'}
          </div>
        ) : (
          logs.map((log, index) => (
            <div 
              key={`${log.id}-${index}`} 
              className="py-1 hover:bg-gray-800 px-2 rounded"
            >
              <span className="text-gray-500">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className={`ml-3 px-2 py-0.5 rounded text-xs ${getLevelColor(log.level)}`}>
                {log.level.toUpperCase()}
              </span>
              {log.source && (
                <span className="ml-2 text-blue-400">[{log.source}]</span>
              )}
              <span className="ml-3">{log.message}</span>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>

      {/* Footer stats */}
      <div className="p-2 border-t bg-gray-50 text-xs text-gray-600">
        Showing {logs.length} / {maxLogs} logs
      </div>
    </div>
  );
}
```

---

## 📝 Komple Migration Checklist (Detaylı)

### Phase 1: Hazırlık ve Planlama
- [ ] Tüm mock data dosyalarını listele ve kategorize et
- [ ] Her mock data için API endpoint mapping tablosu oluştur
- [ ] Her feature için polling/WebSocket kararı ver
- [ ] Adapter dosya yapısını planla
- [ ] Feature flag sistemi kur
- [ ] Test environment hazırla

### Phase 2: Infrastructure Setup
- [ ] `useRealtimeApi` hook'unu implement et
- [ ] `useWebSocket` hook'unu implement et
- [ ] Error boundary component'leri oluştur
- [ ] Loading skeleton component'leri hazırla
- [ ] API service layer'ı güncelle
- [ ] Type definitions tamamla

### Phase 3: Adapter Development
- [ ] Telemetry adapter (cpu, memory, disk)
- [ ] Devices adapter (usb, bluetooth)
- [ ] Services adapter (system services)
- [ ] Logs adapter (real-time logs)
- [ ] Charts adapter (time series data)
- [ ] Network adapter (traffic stats)
- [ ] Her adapter için unit test yaz

### Phase 4: Component Migration (Öncelik Sırasına Göre)
- [ ] ✅ Dashboard cards (CPU, Memory, Disk)
  - [ ] Loading states
  - [ ] Error handling
  - [ ] Real-time updates
- [ ] ✅ Device list component
  - [ ] Polling setup
  - [ ] Empty states
  - [ ] Device actions (eject, mount)
- [ ] ⚠️ Service manager
  - [ ] Start/stop actions
  - [ ] Status updates
  - [ ] Confirmation dialogs
- [ ] ⚠️ Log viewer
  - [ ] WebSocket connection
  - [ ] Auto-scroll
  - [ ] Level filtering
- [ ] 🔴 System configuration
  - [ ] Read-only view first
  - [ ] Write operations
  - [ ] Validation

### Phase 5: Testing
- [ ] Unit tests for adapters
- [ ] Integration tests for hooks
- [ ] E2E tests for critical flows
- [ ] Performance testing (memory leaks)
- [ ] Connection loss scenarios
- [ ] API timeout handling
- [ ] Concurrent request handling

### Phase 6: Documentation
- [ ] API endpoint documentation
- [ ] Adapter usage examples
- [ ] Component migration guide
- [ ] Troubleshooting guide
- [ ] Performance optimization tips

### Phase 7: Deployment
- [ ] Staging environment test
- [ ] Feature flag gradual rollout
- [ ] Monitor error rates
- [ ] Performance metrics
- [ ] User feedback collection

---

## 🛠️ Yardımcı Araçlar ve Scripts

### 1. Mock Data Finder Script (Geliştirilmiş)

```bash
#!/bin/bash
# scripts/find-mock-data.sh

echo "🔍 Mock Data Analysis Report"
echo "======================================"
echo ""

# Find mock data files
echo "📁 Mock Data Files:"
find src -type f \( -name "*mock*" -o -name "*Mock*" \) | while read -r file; do
  lines=$(wc -l < "$file")
  echo "  - $file ($lines lines)"
done

echo ""
echo "📊 Mock Data Usage in Components:"
grep -r "import.*mock" src --include="*.tsx" --include="*.ts" | wc -l | xargs echo "  Total imports:"

echo ""
echo "📝 Component Breakdown:"
grep -r "import.*mock" src --include="*.tsx" --include="*.ts" | awk -F: '{print $1}' | sort | uniq -c | sort -rn

echo ""
echo "🎯 Top 5 Most Used Mock Data:"
grep -rh "mock[A-Z][a-zA-Z]*" src --include="*.tsx" --include="*.ts" -o | sort | uniq -c | sort -rn | head -5

echo ""
echo "✅ Analysis Complete!"
```

### 2. Component Dependency Analyzer

```bash
#!/bin/bash
# scripts/analyze-component.sh

if [ -z "$1" ]; then
  echo "Usage: ./analyze-component.sh <component-path>"
  exit 1
fi

COMPONENT=$1

echo "🔍 Analyzing: $COMPONENT"
echo "======================================"
echo ""

# Check if file exists
if [ ! -f "$COMPONENT" ]; then
  echo "❌ File not found: $COMPONENT"
  exit 1
fi

# Props interface
echo "📝 Props Definition:"
grep -A 10 "interface.*Props" "$COMPONENT" || echo "  No props interface found"

echo ""
echo "📦 Imports:"
grep "^import" "$COMPONENT"

echo ""
echo "🎭 Mock Data Usage:"
grep -i "mock" "$COMPONENT" || echo "  No mock data found"

echo ""
echo "🔗 API Service Calls:"
grep "apiService\." "$COMPONENT" || echo "  No API calls found"

echo ""
echo "🪝 Hooks Used:"
grep -o "use[A-Z][a-zA-Z]*" "$COMPONENT" | sort | uniq

echo ""
echo "✅ Analysis Complete!"
```

### 3. API Endpoint Tester

```bash
#!/bin/bash
# scripts/test-api.sh

API_BASE_URL="${1:-http://192.168.1.100:8000}"

echo "🧪 Testing API Endpoints"
echo "Base URL: $API_BASE_URL"
echo "======================================"
echo ""

# Test telemetry endpoint
echo "📊 Testing /api/telemetry/current..."
response=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/api/telemetry/current")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
  echo "  ✅ Success (200)"
  body=$(echo "$response" | sed '$d')
  echo "$body" | jq '.count' 2>/dev/null || echo "$body"
else
  echo "  ❌ Failed ($http_code)"
fi

echo ""
echo "✅ API Test Complete!"
```

### 4. Migration Progress Tracker

```typescript
// scripts/migration-progress.ts
import * as fs from 'fs';
import * as path from 'path';

interface MigrationStatus {
  component: string;
  status: 'not-started' | 'in-progress' | 'completed' | 'tested';
  mockDataUsed: string[];
  apiEndpoint?: string;
  notes?: string;
}

const migrationStatus: MigrationStatus[] = [
  {
    component: 'Dashboard.tsx',
    status: 'completed',
    mockDataUsed: ['mockDashboardData'],
    apiEndpoint: '/api/telemetry/current',
    notes: 'Using polling with 5s interval'
  },
  {
    component: 'DevicesList.tsx',
    status: 'in-progress',
    mockDataUsed: ['mockDevices'],
    apiEndpoint: '/api/devices/list',
    notes: 'Adapter needs refinement'
  },
  // Add more components...
];

function generateProgressReport() {
  const total = migrationStatus.length;
  const completed = migrationStatus.filter(s => s.status === 'completed').length;
  const inProgress = migrationStatus.filter(s => s.status === 'in-progress').length;
  const notStarted = migrationStatus.filter(s => s.status === 'not-started').length;
  
  console.log('📊 Migration Progress Report');
  console.log('='.repeat(50));
  console.log(`Total Components: ${total}`);
  console.log(`✅ Completed: ${completed} (${Math.round(completed/total*100)}%)`);
  console.log(`🔄 In Progress: ${inProgress}`);
  console.log(`⏳ Not Started: ${notStarted}`);
  console.log('');
  
  console.log('📝 Detailed Status:');
  migrationStatus.forEach(item => {
    const icon = {
      'completed': '✅',
      'in-progress': '🔄',
      'not-started': '⏳',
      'tested': '✔️'
    }[item.status];
    
    console.log(`${icon} ${item.component} - ${item.status}`);
    if (item.notes) console.log(`   Notes: ${item.notes}`);
  });
}

generateProgressReport();
```

---

## 🚀 Production Ready Checklist

### Performance Optimizations

#### 1. Memoization Strategy

```typescript
// src/hooks/useRealtimeApi.ts (optimized version)
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';

export function useRealtimeApi<T>(
  fetchFn: () => Promise<T>,
  options: UseRealtimeApiOptions = {}
) {
  // ... existing code ...
  
  // Memoize the transformed data to avoid unnecessary re-renders
  const memoizedData = useMemo(() => data, [JSON.stringify(data)]);
  
  return { 
    data: memoizedData, 
    loading, 
    error, 
    refresh, 
    lastUpdate,
    isStale 
  };
}
```

#### 2. Request Deduplication

```typescript
// src/services/api.service.ts
class ApiService {
  private pendingRequests: Map<string, Promise<any>> = new Map();
  
  async fetch<T>(endpoint: string): Promise<T> {
    // Check if request is already in progress
    if (this.pendingRequests.has(endpoint)) {
      return this.pendingRequests.get(endpoint)!;
    }
    
    // Create new request
    const request = fetch(`${API_CONFIG.BASE_URL}${endpoint}`)
      .then(res => res.json())
      .finally(() => {
        // Clean up after request completes
        this.pendingRequests.delete(endpoint);
      });
    
    this.pendingRequests.set(endpoint, request);
    return request;
  }
}
```

#### 3. Response Caching

```typescript
// src/utils/cache.ts
interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

class ResponseCache {
  private cache: Map<string, CacheEntry<any>> = new Map();
  
  set<T>(key: string, data: T, ttlSeconds: number = 60) {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl: ttlSeconds * 1000
    });
  }
  
  get<T>(key: string): T | null {
    const entry = this.cache.get(key);
    
    if (!entry) return null;
    
    // Check if cache is still valid
    const isValid = Date.now() - entry.timestamp < entry.ttl;
    
    if (!isValid) {
      this.cache.delete(key);
      return null;
    }
    
    return entry.data as T;
  }
  
  clear() {
    this.cache.clear();
  }
}

export const responseCache = new ResponseCache();
```

### Error Recovery Strategies

#### 1. Exponential Backoff

```typescript
// src/utils/retry.ts
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  let lastError: Error;
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      
      if (i < maxRetries - 1) {
        // Calculate delay with exponential backoff
        const delay = baseDelay * Math.pow(2, i);
        console.log(`Retry ${i + 1}/${maxRetries} after ${delay}ms`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  
  throw lastError!;
}

// Usage in hook
const { data } = useRealtimeApi(
  () => retryWithBackoff(() => apiService.telemetry.getCurrent()),
  { refreshInterval: 5000 }
);
```

#### 2. Circuit Breaker Pattern

```typescript
// src/utils/circuit-breaker.ts
class CircuitBreaker {
  private failures: number = 0;
  private lastFailureTime: number = 0;
  private state: 'closed' | 'open' | 'half-open' = 'closed';
  
  constructor(
    private threshold: number = 5,
    private timeout: number = 60000,  // 1 minute
    private resetTimeout: number = 30000  // 30 seconds
  ) {}
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'open') {
      // Check if we should try again
      if (Date.now() - this.lastFailureTime > this.resetTimeout) {
        this.state = 'half-open';
      } else {
        throw new Error('Circuit breaker is OPEN');
      }
    }
    
    try {
      const result = await fn();
      
      // Success - reset circuit breaker
      if (this.state === 'half-open') {
        this.state = 'closed';
        this.failures = 0;
      }
      
      return result;
    } catch (error) {
      this.failures++;
      this.lastFailureTime = Date.now();
      
      // Open circuit if threshold exceeded
      if (this.failures >= this.threshold) {
        this.state = 'open';
        console.warn('Circuit breaker opened due to repeated failures');
      }
      
      throw error;
    }
  }
  
  getState() {
    return this.state;
  }
}

export const apiCircuitBreaker = new CircuitBreaker();
```

### Monitoring and Debugging

#### 1. Request Logger

```typescript
// src/utils/request-logger.ts
interface RequestLog {
  endpoint: string;
  method: string;
  timestamp: Date;
  duration: number;
  status: number;
  error?: string;
}

class RequestLogger {
  private logs: RequestLog[] = [];
  private maxLogs: number = 100;
  
  log(entry: RequestLog) {
    this.logs.unshift(entry);
    
    // Keep only last N logs
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(0, this.maxLogs);
    }
    
    // Log to console in development
    if (import.meta.env.DEV) {
      const color = entry.error ? 'color: red' : 'color: green';
      console.log(
        `%c[API] ${entry.method} ${endpoint} - ${entry.duration}ms (${entry.status})`,
        color
      );
    }
  }
  
  getLogs() {
    return this.logs;
  }
  
  getStats() {
    const total = this.logs.length;
    const errors = this.logs.filter(l => l.error).length;
    const avgDuration = this.logs.reduce((sum, l) => sum + l.duration, 0) / total;
    
    return { total, errors, avgDuration: Math.round(avgDuration) };
  }
}

export const requestLogger = new RequestLogger();

// Usage in API service
async fetch(endpoint: string) {
  const startTime = Date.now();
  
  try {
    const response = await fetch(`${API_CONFIG.BASE_URL}${endpoint}`);
    const duration = Date.now() - startTime;
    
    requestLogger.log({
      endpoint,
      method: 'GET',
      timestamp: new Date(),
      duration,
      status: response.status
    });
    
    return response.json();
  } catch (error) {
    const duration = Date.now() - startTime;
    
    requestLogger.log({
      endpoint,
      method: 'GET',
      timestamp: new Date(),
      duration,
      status: 0,
      error: (error as Error).message
    });
    
    throw error;
  }
}
```

#### 2. Performance Monitor Component

```typescript
// src/components/PerformanceMonitor.tsx
import { useEffect, useState } from 'react';
import { requestLogger } from '../utils/request-logger';

export function PerformanceMonitor() {
  const [stats, setStats] = useState({ total: 0, errors: 0, avgDuration: 0 });
  const [isOpen, setIsOpen] = useState(false);
  
  useEffect(() => {
    const interval = setInterval(() => {
      setStats(requestLogger.getStats());
    }, 1000);
    
    return () => clearInterval(interval);
  }, []);
  
  if (!import.meta.env.DEV) return null;
  
  return (
    <div className="fixed bottom-4 right-4 z-50">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="px-4 py-2 bg-gray-800 text-white rounded-lg shadow-lg"
      >
        📊 API Stats
      </button>
      
      {isOpen && (
        <div className="mt-2 p-4 bg-white border rounded-lg shadow-xl">
          <h3 className="font-bold mb-2">Performance Monitor</h3>
          <div className="space-y-1 text-sm">
            <div>Total Requests: {stats.total}</div>
            <div>Errors: {stats.errors}</div>
            <div>Avg Duration: {stats.avgDuration}ms</div>
            <div className="pt-2 border-t">
              <button
                onClick={() => {
                  console.table(requestLogger.getLogs());
                }}
                className="text-blue-600 underline text-xs"
              >
                View detailed logs in console
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

---

## 🎯 Sonraki Adımlar - Size Özel Yol Haritası

### 1️⃣ Envanterinizi Paylaşın

Bana şunları gösterin:

```bash
cd ~/figma_ui

# Mock data dosyalarını listeleyin
find src -name "*mock*" -o -name "*data*" | grep -v node_modules

# Bir örnek mock data dosyasının içeriğini gösterin
cat src/data/mockData.ts  # veya hangi dosya varsa

# Bir örnek component'in kodunu gösterin
cat src/pages/Dashboard.tsx  # veya hangi sayfa varsa

# API yapınız varsa, endpoint listesini gösterin
cat src/services/api.service.ts  # veya benzeri dosya
```

### 2️⃣ Size Hazırlayabileceğim Çıktılar

Bu bilgileri paylaştığınızda, sizin için:

✅ **Custom Adapter'lar** - Tam çalışan, projenize özel adapter dosyaları  
✅ **Migration Roadmap** - Hangi component'i nasıl migrate edeceğiniz, adım adım  
✅ **Öncelik Matrisi** - Hangi component'ten başlanmalı (risk vs fayda)  
✅ **Test Scenarios** - Her feature için test senaryoları  
✅ **Code Examples** - Kopyala-yapıştır yapabileceğiniz kod örnekleri  

### 3️⃣ Önerilen Başlangıç

**Düşük Risk, Hızlı Sonuç:**
1. 🟢 **CPU/Memory Cards** - En basit, 30 dakika
2. 🟢 **Device List** - Basit liste, 1 saat
3. 🟡 **Dashboard Charts** - Orta seviye, 2 saat
4. 🟡 **Service Manager** - Actions var, 3 saat
5. 🔴 **Log Viewer** - WebSocket gerekli, 4 saat

---

## 🔧 Eksik Implementasyonlar

### API Service - Tam Implementasyon

```typescript
// src/services/api.service.ts
import { API_CONFIG } from '../config/api.config';
import type {
  TelemetryResponse,
  DevicesResponse,
  ServicesResponse,
  LogsResponse,
  ApiResponse,
  ApiError
} from '../types/api.types';

class ApiService {
  private baseUrl: string;
  private timeout: number;
  private pendingRequests: Map<string, Promise<any>> = new Map();

  constructor() {
    this.baseUrl = API_CONFIG.BASE_URL;
    this.timeout = API_CONFIG.TIMEOUT;
  }

  // ==================== PRIVATE METHODS ====================

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    // Request deduplication
    const cacheKey = `${options.method || 'GET'}-${url}`;
    if (this.pendingRequests.has(cacheKey)) {
      return this.pendingRequests.get(cacheKey)!;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    const requestPromise = (async () => {
      try {
        const response = await fetch(url, {
          ...options,
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            ...options.headers,
          },
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new ApiServiceError(
            errorData.message || `HTTP ${response.status}`,
            response.status,
            errorData
          );
        }

        return await response.json();
      } catch (error) {
        clearTimeout(timeoutId);
        
        if (error instanceof ApiServiceError) {
          throw error;
        }
        
        if (error instanceof Error) {
          if (error.name === 'AbortError') {
            throw new ApiServiceError('Request timeout', 408);
          }
          throw new ApiServiceError(error.message, 0);
        }
        
        throw new ApiServiceError('Unknown error', 0);
      } finally {
        this.pendingRequests.delete(cacheKey);
      }
    })();

    this.pendingRequests.set(cacheKey, requestPromise);
    return requestPromise;
  }

  private get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  private post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  private put<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  private delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  // ==================== TELEMETRY ====================

  telemetry = {
    getCurrent: (): Promise<TelemetryResponse> => {
      return this.get<TelemetryResponse>('/api/telemetry/current');
    },

    getHistory: (params: { duration: '1h' | '6h' | '24h' | '7d' }): Promise<any> => {
      return this.get(`/api/telemetry/history?duration=${params.duration}`);
    },
  };

  // ==================== DEVICES ====================

  devices = {
    list: (): Promise<DevicesResponse> => {
      return this.get<DevicesResponse>('/api/devices/list');
    },

    getById: (id: string): Promise<any> => {
      return this.get(`/api/devices/${id}`);
    },

    eject: (id: string): Promise<void> => {
      return this.post(`/api/devices/${id}/eject`);
    },

    mount: (id: string, mountPoint?: string): Promise<void> => {
      return this.post(`/api/devices/${id}/mount`, { mountPoint });
    },
  };

  // ==================== SERVICES ====================

  services = {
    list: (): Promise<ServicesResponse> => {
      return this.get<ServicesResponse>('/api/services/list');
    },

    getById: (id: string): Promise<any> => {
      return this.get(`/api/services/${id}`);
    },

    start: (id: string): Promise<void> => {
      return this.post(`/api/services/${id}/start`);
    },

    stop: (id: string): Promise<void> => {
      return this.post(`/api/services/${id}/stop`);
    },

    restart: (id: string): Promise<void> => {
      return this.post(`/api/services/${id}/restart`);
    },

    enable: (id: string): Promise<void> => {
      return this.post(`/api/services/${id}/enable`);
    },

    disable: (id: string): Promise<void> => {
      return this.post(`/api/services/${id}/disable`);
    },
  };

  // ==================== RESOURCES (Generic) ====================

  resources = {
    list: (params?: { type?: string }): Promise<any> => {
      const query = params?.type ? `?type=${params.type}` : '';
      return this.get(`/api/resources/list${query}`);
    },

    control: (id: string, action: 'start' | 'stop' | 'restart'): Promise<void> => {
      return this.post(`/api/resources/${id}/${action}`);
    },
  };

  // ==================== LOGS ====================

  logs = {
    getRecent: (limit: number = 50): Promise<LogsResponse> => {
      return this.get<LogsResponse>(`/api/logs/recent?limit=${limit}`);
    },

    getByLevel: (level: string, limit: number = 50): Promise<LogsResponse> => {
      return this.get<LogsResponse>(`/api/logs?level=${level}&limit=${limit}`);
    },

    search: (query: string, limit: number = 50): Promise<LogsResponse> => {
      return this.get<LogsResponse>(`/api/logs/search?q=${encodeURIComponent(query)}&limit=${limit}`);
    },
  };

  // ==================== SYSTEM ====================

  system = {
    getInfo: (): Promise<any> => {
      return this.get('/api/system/info');
    },

    getHealth: (): Promise<any> => {
      return this.get('/api/system/health');
    },

    reboot: (): Promise<void> => {
      return this.post('/api/system/reboot');
    },

    shutdown: (): Promise<void> => {
      return this.post('/api/system/shutdown');
    },
  };

  // ==================== NETWORK ====================

  network = {
    getStatus: (): Promise<any> => {
      return this.get('/api/network/status');
    },

    getInterfaces: (): Promise<any> => {
      return this.get('/api/network/interfaces');
    },

    getConnections: (): Promise<any> => {
      return this.get('/api/network/connections');
    },
  };
}

// Custom Error Class
export class ApiServiceError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public details?: any
  ) {
    super(message);
    this.name = 'ApiServiceError';
  }
}

// Singleton instance
export const apiService = new ApiService();
```

---

### Services Adapter

```typescript
// src/adapters/services.adapter.ts
import type { ServicesResponse, SystemService } from '../types/api.types';

export interface MockService {
  id: string;
  name: string;
  displayName: string;
  status: 'running' | 'stopped' | 'failed';
  enabled: boolean;
  description: string;
  icon: string;
  canStart: boolean;
  canStop: boolean;
  canRestart: boolean;
}

export function apiServicesToMock(apiResponse: ServicesResponse): MockService[] {
  if (!apiResponse?.services) return [];

  return apiResponse.services.map((service: SystemService) => ({
    id: service.id,
    name: service.name,
    displayName: formatServiceName(service.name),
    status: service.status,
    enabled: service.enabled,
    description: service.description || 'No description available',
    icon: getServiceIcon(service.name),
    canStart: service.status !== 'running',
    canStop: service.status === 'running',
    canRestart: service.status === 'running',
  }));
}

function formatServiceName(name: string): string {
  // nginx → Nginx, ssh-server → SSH Server
  return name
    .split(/[-_]/)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function getServiceIcon(name: string): string {
  const iconMap: Record<string, string> = {
    nginx: '🌐',
    apache: '🌐',
    docker: '🐳',
    ssh: '🔐',
    sshd: '🔐',
    mysql: '🗄️',
    postgres: '🐘',
    redis: '📦',
    mongodb: '🍃',
    cron: '⏰',
    systemd: '⚙️',
  };

  const lowerName = name.toLowerCase();
  for (const [key, icon] of Object.entries(iconMap)) {
    if (lowerName.includes(key)) return icon;
  }
  return '⚙️';
}

export function mockToApiServices(mockServices: MockService[]): ServicesResponse {
  return {
    services: mockServices.map(service => ({
      id: service.id,
      name: service.name,
      status: service.status,
      enabled: service.enabled,
      description: service.description,
    })),
    count: mockServices.length,
  };
}
```

---

### Logs Adapter

```typescript
// src/adapters/logs.adapter.ts
import type { LogsResponse, LogEntry } from '../types/api.types';

export interface MockLog {
  id: number;
  timestamp: string;
  timeAgo: string;
  level: 'info' | 'warning' | 'error' | 'debug';
  levelColor: string;
  message: string;
  source: string;
  icon: string;
}

export function apiLogsToMock(apiResponse: LogsResponse): MockLog[] {
  if (!apiResponse?.logs) return [];

  return apiResponse.logs.map((log: LogEntry, index: number) => ({
    id: index + 1,
    timestamp: formatTimestamp(log.timestamp),
    timeAgo: formatTimeAgo(log.timestamp),
    level: log.level,
    levelColor: getLevelColor(log.level),
    message: log.message,
    source: log.source || 'system',
    icon: getLevelIcon(log.level),
  }));
}

function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString('tr-TR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatTimeAgo(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function getLevelColor(level: string): string {
  const colors: Record<string, string> = {
    error: 'text-red-600 bg-red-50',
    warning: 'text-yellow-600 bg-yellow-50',
    info: 'text-blue-600 bg-blue-50',
    debug: 'text-gray-600 bg-gray-50',
  };
  return colors[level] || colors.info;
}

function getLevelIcon(level: string): string {
  const icons: Record<string, string> = {
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️',
    debug: '🔍',
  };
  return icons[level] || icons.info;
}

export function mockToApiLogs(mockLogs: MockLog[]): LogsResponse {
  return {
    logs: mockLogs.map(log => ({
      id: String(log.id),
      timestamp: log.timestamp,
      level: log.level,
      message: log.message,
      source: log.source,
    })),
    total: mockLogs.length,
  };
}
```

---

### Charts Adapter

```typescript
// src/adapters/charts.adapter.ts

export interface MockChartDataPoint {
  time: string;
  timestamp: Date;
  cpu: number;
  memory: number;
  disk: number;
  temperature?: number;
  networkRx?: number;
  networkTx?: number;
}

export interface ChartHistoryResponse {
  telemetry: Array<{
    timestamp: string;
    cpu: { usage: number; temp?: number };
    memory: { percent: number };
    disk: { percent: number };
    network?: { rx_bytes: number; tx_bytes: number };
  }>;
  duration: string;
  interval: string;
}

export function apiChartToMock(apiResponse: ChartHistoryResponse): MockChartDataPoint[] {
  if (!apiResponse?.telemetry) return [];

  return apiResponse.telemetry.map((point) => ({
    time: formatTimeForChart(point.timestamp),
    timestamp: new Date(point.timestamp),
    cpu: Math.round(point.cpu?.usage ?? 0),
    memory: Math.round(point.memory?.percent ?? 0),
    disk: Math.round(point.disk?.percent ?? 0),
    temperature: point.cpu?.temp ? Math.round(point.cpu.temp) : undefined,
    networkRx: point.network?.rx_bytes,
    networkTx: point.network?.tx_bytes,
  }));
}

function formatTimeForChart(isoString: string): string {
  const date = new Date(isoString);
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
}

export function formatTimeLong(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// Chart data aggregation utilities
export function aggregateChartData(
  data: MockChartDataPoint[],
  interval: number = 5
): MockChartDataPoint[] {
  if (data.length <= interval) return data;

  const aggregated: MockChartDataPoint[] = [];
  for (let i = 0; i < data.length; i += interval) {
    const slice = data.slice(i, i + interval);
    aggregated.push({
      time: slice[0].time,
      timestamp: slice[0].timestamp,
      cpu: Math.round(slice.reduce((sum, p) => sum + p.cpu, 0) / slice.length),
      memory: Math.round(slice.reduce((sum, p) => sum + p.memory, 0) / slice.length),
      disk: Math.round(slice.reduce((sum, p) => sum + p.disk, 0) / slice.length),
      temperature: slice[0].temperature
        ? Math.round(slice.reduce((sum, p) => sum + (p.temperature || 0), 0) / slice.length)
        : undefined,
    });
  }
  return aggregated;
}
```

---

### Network Adapter

```typescript
// src/adapters/network.adapter.ts

export interface MockNetworkStats {
  rxBytes: number;
  txBytes: number;
  rxFormatted: string;
  txFormatted: string;
  rxSpeed: string;
  txSpeed: string;
  totalFormatted: string;
}

export interface NetworkStatusResponse {
  network: {
    rx_bytes: number;
    tx_bytes: number;
    rx_speed?: number;
    tx_speed?: number;
  };
  interfaces?: Array<{
    name: string;
    ip: string;
    mac: string;
    status: 'up' | 'down';
  }>;
}

export function apiNetworkToMock(apiResponse: NetworkStatusResponse): MockNetworkStats {
  const { rx_bytes, tx_bytes, rx_speed, tx_speed } = apiResponse.network;

  return {
    rxBytes: rx_bytes,
    txBytes: tx_bytes,
    rxFormatted: formatBytes(rx_bytes),
    txFormatted: formatBytes(tx_bytes),
    rxSpeed: rx_speed ? `${formatBytes(rx_speed)}/s` : 'N/A',
    txSpeed: tx_speed ? `${formatBytes(tx_speed)}/s` : 'N/A',
    totalFormatted: formatBytes(rx_bytes + tx_bytes),
  };
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

export interface MockNetworkInterface {
  name: string;
  displayName: string;
  ip: string;
  mac: string;
  status: 'up' | 'down';
  statusColor: string;
  icon: string;
}

export function apiInterfacesToMock(
  interfaces: NetworkStatusResponse['interfaces']
): MockNetworkInterface[] {
  if (!interfaces) return [];

  return interfaces.map((iface) => ({
    name: iface.name,
    displayName: formatInterfaceName(iface.name),
    ip: iface.ip || 'No IP',
    mac: iface.mac || 'N/A',
    status: iface.status,
    statusColor: iface.status === 'up' ? 'text-green-600' : 'text-red-600',
    icon: getInterfaceIcon(iface.name),
  }));
}

function formatInterfaceName(name: string): string {
  if (name.startsWith('eth')) return `Ethernet ${name.slice(3)}`;
  if (name.startsWith('wlan')) return `WiFi ${name.slice(4)}`;
  if (name === 'lo') return 'Loopback';
  return name;
}

function getInterfaceIcon(name: string): string {
  if (name.startsWith('eth')) return '🔌';
  if (name.startsWith('wlan')) return '📶';
  if (name === 'lo') return '🔄';
  return '🌐';
}
```

---

### Adapter Index (Barrel Export)

```typescript
// src/adapters/index.ts
export * from './telemetry.adapter';
export * from './devices.adapter';
export * from './services.adapter';
export * from './logs.adapter';
export * from './charts.adapter';
export * from './network.adapter';
```

---

### UI Components

#### LoadingSpinner

```typescript
// src/components/LoadingSpinner.tsx
import React from 'react';

interface LoadingSpinnerProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function LoadingSpinner({ 
  message = 'Loading...', 
  size = 'md',
  className = '' 
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'h-6 w-6',
    md: 'h-10 w-10',
    lg: 'h-16 w-16',
  };

  return (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      <div
        className={`animate-spin rounded-full border-b-2 border-blue-500 ${sizeClasses[size]}`}
      />
      {message && (
        <p className="mt-3 text-gray-600 text-sm">{message}</p>
      )}
    </div>
  );
}

export default LoadingSpinner;
```

#### ErrorMessage

```typescript
// src/components/ErrorMessage.tsx
import React from 'react';

interface ErrorMessageProps {
  message: string;
  title?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorMessage({ 
  message, 
  title = 'Error',
  onRetry,
  className = '' 
}: ErrorMessageProps) {
  return (
    <div className={`bg-red-50 border border-red-200 rounded-lg p-4 ${className}`}>
      <div className="flex items-start">
        <span className="text-red-500 text-xl mr-3">❌</span>
        <div className="flex-1">
          <h3 className="text-red-800 font-semibold">{title}</h3>
          <p className="text-red-700 text-sm mt-1">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 px-4 py-2 bg-red-600 text-white text-sm rounded hover:bg-red-700 transition-colors"
            >
              🔄 Retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ErrorMessage;
```

#### StatusBadge

```typescript
// src/components/StatusBadge.tsx
import React from 'react';

type Status = 'running' | 'stopped' | 'failed' | 'connected' | 'disconnected' | 'pending' | 'unknown';

interface StatusBadgeProps {
  status: Status;
  showIcon?: boolean;
  className?: string;
}

const statusConfig: Record<Status, { color: string; icon: string; label: string }> = {
  running: { color: 'bg-green-100 text-green-800', icon: '✅', label: 'Running' },
  stopped: { color: 'bg-gray-100 text-gray-800', icon: '⏹️', label: 'Stopped' },
  failed: { color: 'bg-red-100 text-red-800', icon: '❌', label: 'Failed' },
  connected: { color: 'bg-green-100 text-green-800', icon: '🔗', label: 'Connected' },
  disconnected: { color: 'bg-red-100 text-red-800', icon: '🔌', label: 'Disconnected' },
  pending: { color: 'bg-yellow-100 text-yellow-800', icon: '⏳', label: 'Pending' },
  unknown: { color: 'bg-gray-100 text-gray-600', icon: '❓', label: 'Unknown' },
};

export function StatusBadge({ status, showIcon = true, className = '' }: StatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.unknown;

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color} ${className}`}
    >
      {showIcon && <span className="mr-1">{config.icon}</span>}
      {config.label}
    </span>
  );
}

export default StatusBadge;
```

#### TableSkeleton

```typescript
// src/components/TableSkeleton.tsx
import React from 'react';

interface TableSkeletonProps {
  rows?: number;
  columns?: number;
  className?: string;
}

export function TableSkeleton({ rows = 5, columns = 4, className = '' }: TableSkeletonProps) {
  return (
    <div className={`animate-pulse ${className}`}>
      {/* Header */}
      <div className="flex gap-4 mb-4 pb-2 border-b">
        {Array.from({ length: columns }).map((_, i) => (
          <div key={`header-${i}`} className="h-4 bg-gray-300 rounded flex-1" />
        ))}
      </div>

      {/* Rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={`row-${rowIndex}`} className="flex gap-4 mb-3">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <div
              key={`cell-${rowIndex}-${colIndex}`}
              className="h-4 bg-gray-200 rounded flex-1"
              style={{ width: `${Math.random() * 40 + 60}%` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export default TableSkeleton;
```

#### ChartSkeleton

```typescript
// src/components/ChartSkeleton.tsx
import React from 'react';

interface ChartSkeletonProps {
  height?: number;
  className?: string;
}

export function ChartSkeleton({ height = 300, className = '' }: ChartSkeletonProps) {
  return (
    <div className={`animate-pulse ${className}`}>
      {/* Chart title */}
      <div className="h-6 bg-gray-300 rounded w-1/3 mb-4" />
      
      {/* Chart area */}
      <div 
        className="bg-gray-100 rounded-lg flex items-end justify-around p-4"
        style={{ height }}
      >
        {/* Fake bars */}
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            className="bg-gray-300 rounded-t w-6"
            style={{ height: `${Math.random() * 60 + 20}%` }}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="flex gap-6 mt-4 justify-center">
        {['CPU', 'Memory', 'Disk'].map((label) => (
          <div key={label} className="flex items-center gap-2">
            <div className="w-3 h-3 bg-gray-300 rounded" />
            <div className="h-3 bg-gray-200 rounded w-12" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default ChartSkeleton;
```

#### ErrorBoundary

```typescript
// src/components/ErrorBoundary.tsx
import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="bg-white p-8 rounded-lg shadow-lg max-w-md text-center">
            <div className="text-6xl mb-4">💥</div>
            <h2 className="text-2xl font-bold text-gray-800 mb-2">
              Something went wrong
            </h2>
            <p className="text-gray-600 mb-4">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            <button
              onClick={this.handleRetry}
              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
```

---

### Utility Functions

#### formatters.ts

```typescript
// src/utils/formatters.ts

/**
 * Format bytes to human readable string
 */
export function formatBytes(bytes: number, decimals: number = 2): string {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`;
}

/**
 * Format seconds to human readable uptime
 */
export function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  if (secs > 0 && parts.length === 0) parts.push(`${secs}s`);

  return parts.join(' ') || '0s';
}

/**
 * Format date to relative time (e.g., "5 minutes ago")
 */
export function formatTimeAgo(date: Date | string): string {
  const now = new Date();
  const past = typeof date === 'string' ? new Date(date) : date;
  const seconds = Math.floor((now.getTime() - past.getTime()) / 1000);

  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;

  return past.toLocaleDateString();
}

/**
 * Format percentage with optional decimals
 */
export function formatPercent(value: number, decimals: number = 0): string {
  return `${value.toFixed(decimals)}%`;
}

/**
 * Format temperature with unit
 */
export function formatTemperature(celsius: number, unit: 'C' | 'F' = 'C'): string {
  if (unit === 'F') {
    return `${((celsius * 9) / 5 + 32).toFixed(1)}°F`;
  }
  return `${celsius.toFixed(1)}°C`;
}

/**
 * Format number with thousand separators
 */
export function formatNumber(num: number): string {
  return num.toLocaleString();
}

/**
 * Truncate string with ellipsis
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return `${str.slice(0, maxLength - 3)}...`;
}
```

#### validators.ts

```typescript
// src/utils/validators.ts

/**
 * Check if value is a valid IP address
 */
export function isValidIP(ip: string): boolean {
  const ipv4Regex = /^(\d{1,3}\.){3}\d{1,3}$/;
  const ipv6Regex = /^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$/;

  if (ipv4Regex.test(ip)) {
    const parts = ip.split('.').map(Number);
    return parts.every((part) => part >= 0 && part <= 255);
  }

  return ipv6Regex.test(ip);
}

/**
 * Check if value is a valid MAC address
 */
export function isValidMAC(mac: string): boolean {
  const macRegex = /^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$/;
  return macRegex.test(mac);
}

/**
 * Check if value is a valid URL
 */
export function isValidURL(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

/**
 * Check if value is a valid port number
 */
export function isValidPort(port: number): boolean {
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}

/**
 * Check if value is within range
 */
export function isInRange(value: number, min: number, max: number): boolean {
  return value >= min && value <= max;
}

/**
 * Validate API response structure
 */
export function isValidApiResponse<T>(
  response: any,
  requiredFields: (keyof T)[]
): response is T {
  if (!response || typeof response !== 'object') return false;

  return requiredFields.every((field) => field in response);
}

/**
 * Sanitize user input
 */
export function sanitizeInput(input: string): string {
  return input
    .replace(/[<>]/g, '') // Remove < and >
    .replace(/javascript:/gi, '') // Remove javascript: protocol
    .trim();
}

/**
 * Validate telemetry data
 */
export function isValidTelemetry(data: any): boolean {
  return (
    data &&
    typeof data.cpu?.usage === 'number' &&
    typeof data.memory?.percent === 'number' &&
    typeof data.disk?.percent === 'number'
  );
}
```

---

### Unit Test Örnekleri

```typescript
// src/adapters/__tests__/telemetry.adapter.test.ts
import { describe, it, expect } from 'vitest';
import { apiToMockFormat, mockToApiFormat } from '../telemetry.adapter';

describe('Telemetry Adapter', () => {
  const mockApiResponse = {
    cpu: { usage: 45.5, temp: 65, cores: [{ id: 0, usage: 42 }], load: [1.2, 1.5, 1.8] },
    memory: { used: 3072, total: 4096, percent: 75, swap: { used: 512, total: 2048 } },
    disk: { used: 50000, total: 100000, percent: 50 },
    network: { rx_bytes: 1000000, tx_bytes: 500000 },
    uptime: 86400,
    timestamp: '2024-12-16T10:00:00Z',
  };

  describe('apiToMockFormat', () => {
    it('should convert API response to mock format', () => {
      const result = apiToMockFormat(mockApiResponse);

      expect(result.cpuUsage).toBe(46); // Rounded
      expect(result.memoryUsage).toBe(75);
      expect(result.diskUsage).toBe(50);
      expect(result.temperature).toBe(65);
    });

    it('should format uptime correctly', () => {
      const result = apiToMockFormat(mockApiResponse);
      expect(result.uptime).toBe('1d 0h 0m');
    });

    it('should handle missing cores gracefully', () => {
      const apiWithoutCores = { ...mockApiResponse, cpu: { usage: 45, temp: 65 } };
      const result = apiToMockFormat(apiWithoutCores as any);
      expect(result.cpuCores).toEqual([]);
    });
  });

  describe('mockToApiFormat', () => {
    it('should convert mock format back to API format', () => {
      const mockData = apiToMockFormat(mockApiResponse);
      const result = mockToApiFormat(mockData);

      expect(result.cpu.usage).toBe(mockData.cpuUsage);
      expect(result.memory.percent).toBe(mockData.memoryUsage);
    });
  });
});

// src/adapters/__tests__/devices.adapter.test.ts
import { describe, it, expect } from 'vitest';
import { apiDevicesToMock } from '../devices.adapter';

describe('Devices Adapter', () => {
  it('should convert USB devices', () => {
    const apiResponse = {
      devices: {
        usb: [
          { id: 'usb-001', name: 'USB Drive', vendor: 'Kingston', status: 'connected', path: '/dev/sda1' },
        ],
      },
      count: 1,
    };

    const result = apiDevicesToMock(apiResponse);

    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('USB Drive');
    expect(result[0].type).toBe('USB');
    expect(result[0].status).toBe('connected');
  });

  it('should handle empty devices', () => {
    const result = apiDevicesToMock({ devices: { usb: [] }, count: 0 });
    expect(result).toEqual([]);
  });

  it('should handle undefined response', () => {
    const result = apiDevicesToMock(undefined as any);
    expect(result).toEqual([]);
  });
});
```

---

## 🚀 Hızlı Başlangıç Kılavuzu

### 1. Dosyaları Oluştur

```bash
# Proje dizininde çalıştır
mkdir -p src/{adapters,hooks,services,config,types,utils,components}

# Dosyaları oluştur
touch src/adapters/{index,telemetry.adapter,devices.adapter,services.adapter,logs.adapter,charts.adapter,network.adapter}.ts
touch src/hooks/{useRealtimeApi,useWebSocket}.ts
touch src/services/api.service.ts
touch src/config/{api.config,features.config}.ts
touch src/types/{api.types,mock.types}.ts
touch src/utils/{formatters,validators}.ts
touch src/components/{LoadingSpinner,ErrorMessage,StatusBadge,TableSkeleton,ChartSkeleton,ErrorBoundary}.tsx
```

### 2. Environment Dosyasını Ayarla

```bash
# .env.local dosyası oluştur
cat > .env.local << EOF
VITE_API_BASE_URL=http://YOUR_RASPBERRY_PI_IP:8000
VITE_WS_URL=ws://YOUR_RASPBERRY_PI_IP:8000/ws
VITE_USE_REAL_API=false
VITE_WEBSOCKET_ENABLED=false
EOF
```

### 3. İlk Migration'ı Yap

```typescript
// Herhangi bir component'te
import { useRealtimeApi } from '../hooks/useRealtimeApi';
import { apiService } from '../services/api.service';
import { apiToMockFormat } from '../adapters/telemetry.adapter';

function MyComponent() {
  const { data, loading, error } = useRealtimeApi(
    () => apiService.telemetry.getCurrent(),
    { refreshInterval: 5000 }
  );

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message={error} />;

  const mockData = apiToMockFormat(data);
  // Mevcut component'ler aynı props'ları kullanmaya devam eder
}


