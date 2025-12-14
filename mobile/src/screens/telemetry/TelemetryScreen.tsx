import React, { useEffect, useState } from 'react';
import {
    View,
    Text,
    ScrollView,
    StyleSheet,
    RefreshControl,
    Dimensions,
} from 'react-native';
import { colors, spacing, borderRadius, fontSize, fontWeight } from '../../theme';
import { api } from '../../services/api';

interface TelemetryData {
    cpu: { pct_total: number; cores: number[] };
    memory: { pct: number; used_gb: number; total_gb: number };
    disk: { pct: number; used_gb: number; total_gb: number };
    network: { rx_mbps: number; tx_mbps: number };
    temperature?: { cpu_c: number };
}

function ProgressBar({ value, color, label }: { value: number; color: string; label: string }) {
    return (
        <View style={styles.progressContainer}>
            <View style={styles.progressHeader}>
                <Text style={styles.progressLabel}>{label}</Text>
                <Text style={styles.progressValue}>{value.toFixed(1)}%</Text>
            </View>
            <View style={styles.progressTrack}>
                <View style={[styles.progressFill, { width: `${Math.min(value, 100)}%`, backgroundColor: color }]} />
            </View>
        </View>
    );
}

function MetricRow({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
    return (
        <View style={styles.metricRow}>
            <Text style={styles.metricLabel}>{label}</Text>
            <Text style={styles.metricValue}>
                {value}{unit && <Text style={styles.metricUnit}> {unit}</Text>}
            </Text>
        </View>
    );
}

export default function TelemetryScreen() {
    const [data, setData] = useState<TelemetryData | null>(null);
    const [refreshing, setRefreshing] = useState(false);

    const fetchData = async () => {
        try {
            const { data: telemetry } = await api.get<TelemetryData>('/telemetry/dashboard');
            setData(telemetry);
        } catch (error) {
            console.error('Failed to fetch telemetry:', error);
        } finally {
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 3000);
        return () => clearInterval(interval);
    }, []);

    const onRefresh = () => {
        setRefreshing(true);
        fetchData();
    };

    const getUsageColor = (pct: number) => {
        if (pct >= 90) return colors.error;
        if (pct >= 70) return colors.warning;
        return colors.success;
    };

    return (
        <ScrollView
            style={styles.container}
            contentContainerStyle={styles.content}
            refreshControl={
                <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary[500]} />
            }
        >
            {/* CPU Section */}
            <View style={styles.section}>
                <Text style={styles.sectionTitle}>⚡ CPU</Text>
                <View style={styles.card}>
                    <ProgressBar
                        value={data?.cpu?.pct_total || 0}
                        color={getUsageColor(data?.cpu?.pct_total || 0)}
                        label="Total Usage"
                    />
                    {data?.temperature?.cpu_c && (
                        <MetricRow label="Temperature" value={data.temperature.cpu_c.toFixed(1)} unit="°C" />
                    )}
                </View>
            </View>

            {/* Memory Section */}
            <View style={styles.section}>
                <Text style={styles.sectionTitle}>💾 Memory</Text>
                <View style={styles.card}>
                    <ProgressBar
                        value={data?.memory?.pct || 0}
                        color={getUsageColor(data?.memory?.pct || 0)}
                        label="Usage"
                    />
                    <MetricRow
                        label="Used / Total"
                        value={`${data?.memory?.used_gb?.toFixed(1) || 0} / ${data?.memory?.total_gb?.toFixed(1) || 0}`}
                        unit="GB"
                    />
                </View>
            </View>

            {/* Disk Section */}
            <View style={styles.section}>
                <Text style={styles.sectionTitle}>💿 Disk</Text>
                <View style={styles.card}>
                    <ProgressBar
                        value={data?.disk?.pct || 0}
                        color={getUsageColor(data?.disk?.pct || 0)}
                        label="Usage"
                    />
                    <MetricRow
                        label="Used / Total"
                        value={`${data?.disk?.used_gb?.toFixed(1) || 0} / ${data?.disk?.total_gb?.toFixed(1) || 0}`}
                        unit="GB"
                    />
                </View>
            </View>

            {/* Network Section */}
            <View style={styles.section}>
                <Text style={styles.sectionTitle}>🌐 Network</Text>
                <View style={styles.card}>
                    <MetricRow label="Download" value={data?.network?.rx_mbps?.toFixed(2) || 0} unit="Mbps" />
                    <MetricRow label="Upload" value={data?.network?.tx_mbps?.toFixed(2) || 0} unit="Mbps" />
                </View>
            </View>
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.gray[950],
    },
    content: {
        padding: spacing.md,
    },
    section: {
        marginBottom: spacing.lg,
    },
    sectionTitle: {
        fontSize: fontSize.lg,
        fontWeight: fontWeight.semibold,
        color: colors.white,
        marginBottom: spacing.sm,
    },
    card: {
        backgroundColor: colors.gray[900],
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        borderWidth: 1,
        borderColor: colors.gray[800],
    },
    progressContainer: {
        marginBottom: spacing.md,
    },
    progressHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        marginBottom: spacing.xs,
    },
    progressLabel: {
        fontSize: fontSize.sm,
        color: colors.gray[400],
    },
    progressValue: {
        fontSize: fontSize.sm,
        fontWeight: fontWeight.semibold,
        color: colors.white,
    },
    progressTrack: {
        height: 8,
        backgroundColor: colors.gray[800],
        borderRadius: borderRadius.full,
        overflow: 'hidden',
    },
    progressFill: {
        height: '100%',
        borderRadius: borderRadius.full,
    },
    metricRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        paddingVertical: spacing.xs,
    },
    metricLabel: {
        fontSize: fontSize.sm,
        color: colors.gray[400],
    },
    metricValue: {
        fontSize: fontSize.sm,
        fontWeight: fontWeight.medium,
        color: colors.white,
    },
    metricUnit: {
        color: colors.gray[500],
    },
});
