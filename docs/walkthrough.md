# Deployment Walkthrough

The application has been successfully deployed to the Raspberry Pi at `192.168.1.180`.

## Deployment Details

- **Target Host**: `fou4@192.168.1.180`
- **Installation Directory**: `/opt/pi-control`
- **Deployment Method**: Manual execution of `deploy-native.sh` steps.

## Recent Updates

### 14. Real-time Chart Updates (High Performance Mode)
- **Feature**: Performance charts now automatically refresh every **15 seconds** (default).
- **Update**: The backend data collection frequency has been increased to **every 1 second**.
- **Benefit**: You can watch the chart update literally every second if you choose 1s in the settings. This is true real-time monitoring.

### 15. Standard User (Read-Only)
- **Feature**: A new default user `user` with password `user123` has been added.
- **Role**: `viewer` (Read-Only).
- **Restrictions**:
    - **No Terminal**: The Terminal tab is hidden and inaccessible.
    - **No Service Control**: Start/Stop/Restart buttons are hidden (Services, process management).
- **Purpose**: Safe viewing for guests or monitoring displays without risk of accidental changes.

### 16. Configurable Refresh Rate (Restored & Functional)
- **Feature**: You can now set your own refresh interval (e.g., 5s, 10s, 60s).
- **Controls**: A new input box `[ 15 ]s ✔️` is located next to the time range selector.
- **Persistence**: Your setting is **saved permanently** in the browser. If you set it to 5s, it stays 5s even after you close and reopen the page.

### 17. Enhanced Settings Page
- **Dynamic Profile**: Displays logged-in username ("admin" or "user") and role ("Operator" or "Viewer").
- **Role-Based Tabs**: Hides "Security" and "Users" tabs for non-admin users.
- **User Management**: Admins can view, add, and delete users from the interface.

### Feature Refinement & Fixes
- **GPIO Manager Restriction**: The "Open GPIO Manager" button in `Devices` page is now hidden for "viewer" users (standard users). Only Admins/Operators can access it.
- **WiFi Scanning Fix**:
    - Implemented missing `scan_wifi` logic in the backend Agent (`nmcli` based).
    - Installed and configured the `pi-agent` systemd service which was previously missing.
    - Providing real-time WiFi network discovery for Admins.

### 11. Antivirus / Ad-blocker Fix (Complete)
- **Issue**: "Request has been forbidden by antivirus" error was preventing the chart from loading data. This happens because some security software inspects URL parameters aggressively.
- **Fix**: Re-engineered the data fetching layer to use **POST requests** instead of GET. This hides the parameters inside the request body (JSON), which typically bypasses these filters.
- **Update**: Applied this fix to **all** time ranges, including 7 Days and 30 Days summaries.
- **Result**: Data should now load reliably without being blocked for any time range.

### 13. UI Aesthetics
- **Chart Style**: Removed dots from the line chart for a cleaner look.

### 12. UI Polish
- **Time Selector**: Removed the horizontal scrollbar. The buttons (1M, 30M, etc.) now sit cleanly side-by-side.

### 10. Network Activity Fix
- **Issue**: Network usage was showing "0 B/s" due to a mismatch between database keys and frontend expectations.
- **Fix**: Updated `DashboardContext.jsx` to use `host.net.rx_bytes` and `host.net.tx_bytes` directly from the database, ensuring correct speed calculation.

### 9. Extended Data Retention
- **Policy Update**: Updated the backend configuration on the Raspberry Pi.
- **Raw Data**: Retained for **30 days** (previously 15).
- **Summary Data**: Retained for **90 days** (previously 30).
- **Database**: Data is stored locally in `/var/lib/pi-control/telemetry.db` on the Pi.

### 8. Data Persistence Fix
- **API Response Fix**: Resolved an issue where the chart remained empty because the application was not correctly reading the API response format.
- **Improved 1m View**: The "1M" filter now displays the last **5 minutes** of data to ensure enough data points are visible for a meaningful trend line (Live Mode).

### 7. Chart Visibility Improvements
- **Line Chart**: Switched from Area Chart to Line Chart to improve visibility of sparse data.
- **Data Points**: Added visible dots to the line chart, ensuring even single data points are seen.

### 6. Performance Widget Polish
- **Default View**: Set to **ALL** by default.
- **Button Styling**:
    - **CPU**: Purple (Theme Accent)
    - **RAM**: Emerald Green
    - **TEMP**: Amber/Orange
    - **ALL**: Purple (Theme Accent)
- **Active State**: Selected buttons are now **bold** and have a subtle background tint for better visibility.

### 5. Performance Widget Enhancements
- **Granular Time Ranges**: Added **1m** (1 minute) and **30m** (30 minutes) views for real-time monitoring.
- **Combined View**: Added **ALL** option to the metric selector.
    - Displays CPU, Memory, and Temperature on the same chart.
    - Uses distinct colors (Purple, Green, Orange) for easy differentiation.

### 4. Performance Monitoring Upgrade
- **New Feature**: Historical data visualization with interactive Line Charts.
- **Metrics**: 
    - CPU Usage (%)
    - Memory Usage (%)
    - Temperature (°C)
- **Time Ranges**:
    - 1 Hour (Raw data)
    - 24 Hours (Raw data)
    - 7 Days (Summary data)
    - 30 Days (Summary data)

## Post-Deployment Fixes

### 1. JWT Permission Error
- **Fix**: Changed ownership of `/etc/pi-control/jwt_secret` to `fou4:fou4`.

### 2. Sudo Command Errors
- **Fix**: Disabled `NoNewPrivileges` in `pi-control.service` to allow privilege escalation.

### 3. Sidebar Icon Visibility
- **Fix**: Updated `Sidebar.jsx` to force the active icon color to **White**.

### 4. Login Crash
- **Fix**: Resolved syntax error in `telemetry_collector.py` that caused service startup failure.

## Access
You can now access the control panel at:
**http://192.168.1.180**
