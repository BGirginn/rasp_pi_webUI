import React, { useEffect, useState } from 'react';
import {
    View,
    Text,
    ScrollView,
    StyleSheet,
    RefreshControl,
    TouchableOpacity,
    Alert,
} from 'react-native';
import { colors, spacing, borderRadius, fontSize, fontWeight } from '../../theme';
import { api } from '../../services/api';

interface DashboardData {
    hostname: string;
    uptime: string;
    cpu: { pct_total: number };
    memory: { pct: number; used_gb: number; total_gb: number };
    disk: { pct: number; used_gb: number; total_gb: number };
    temperature?: { cpu_c: number };
}

function MetricCard({
    title,
    value,
    unit,
    icon,
    color
}: {
    title: string;
    value: string | number;
    unit?: string;
    icon: string;
    color: string;
}) {
    return (
        <View style={[styles.metricCard, { borderLeftColor: color }]}>
            <Text style={styles.metricIcon}>{icon}</Text>
            <View style={styles.metricContent}>
                <Text style={styles.metricTitle}>{title}</Text>
                <Text style={styles.metricValue}>
                    {value}{unit && <Text style={styles.metricUnit}>{unit}</Text>}
                </Text>
            </View>
        </View>
    );
}

export default function DashboardScreen() {
    const [data, setData] = useState<DashboardData | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const fetchData = async () => {
        try {
            const { data: dashboard } = await api.get<DashboardData>('/telemetry/dashboard');
            setData(dashboard);
        } catch (error) {
            console.error('Failed to fetch dashboard:', error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, []);

    const onRefresh = () => {
        setRefreshing(true);
        fetchData();
    };

    const handleQuickAction = async (action: string) => {
        Alert.alert(
            `Confirm ${action}`,
            `Are you sure you want to ${action.toLowerCase()} the system?`,
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: action,
                    style: action === 'Shutdown' ? 'destructive' : 'default',
                    onPress: async () => {
                        try {
                            await api.post(`/admin/${action.toLowerCase()}`);
                            Alert.alert('Success', `${action} initiated`);
                        } catch (error) {
                            Alert.alert('Error', `Failed to ${action.toLowerCase()}`);
                        }
                    },
                },
            ]
        );
    };

    if (loading) {
        return (
            <View style={styles.loadingContainer}>
                <Text style={styles.loadingText}>Loading...</Text>
            </View>
        );
    }

    return (
        <ScrollView
            style={styles.container}
            contentContainerStyle={styles.content}
            refreshControl={
                <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary[500]} />
            }
        >
            {/* Header */}
            <View style={styles.header}>
                <Text style={styles.hostname}>{data?.hostname || 'Raspberry Pi'}</Text>
                <Text style={styles.uptime}>Uptime: {data?.uptime || 'N/A'}</Text>
            </View>

            {/* Metrics Grid */}
            <View style={styles.metricsGrid}>
                <MetricCard
                    title="CPU Usage"
                    value={data?.cpu?.pct_total?.toFixed(1) || '0'}
                    unit="%"
                    icon="⚡"
                    color={colors.primary[500]}
                />
                <MetricCard
                    title="Memory"
                    value={data?.memory?.pct?.toFixed(1) || '0'}
                    unit="%"
                    icon="💾"
                    color={colors.success}
                />
                <MetricCard
                    title="Disk"
                    value={data?.disk?.pct?.toFixed(1) || '0'}
                    unit="%"
                    icon="💿"
                    color={colors.warning}
                />
                <MetricCard
                    title="Temperature"
                    value={data?.temperature?.cpu_c?.toFixed(1) || 'N/A'}
                    unit="°C"
                    icon="🌡️"
                    color={colors.error}
                />
            </View>

            {/* Quick Actions */}
            <Text style={styles.sectionTitle}>Quick Actions</Text>
            <View style={styles.actionsRow}>
                <TouchableOpacity
                    style={[styles.actionButton, styles.rebootButton]}
                    onPress={() => handleQuickAction('Reboot')}
                >
                    <Text style={styles.actionIcon}>🔄</Text>
                    <Text style={styles.actionText}>Reboot</Text>
                </TouchableOpacity>
                <TouchableOpacity
                    style={[styles.actionButton, styles.shutdownButton]}
                    onPress={() => handleQuickAction('Shutdown')}
                >
                    <Text style={styles.actionIcon}>⏻</Text>
                    <Text style={styles.actionText}>Shutdown</Text>
                </TouchableOpacity>
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
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: colors.gray[950],
    },
    loadingText: {
        color: colors.gray[400],
        fontSize: fontSize.lg,
    },
    header: {
        marginBottom: spacing.lg,
    },
    hostname: {
        fontSize: fontSize['2xl'],
        fontWeight: fontWeight.bold,
        color: colors.white,
    },
    uptime: {
        fontSize: fontSize.sm,
        color: colors.gray[400],
        marginTop: spacing.xs,
    },
    metricsGrid: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        marginHorizontal: -spacing.xs,
    },
    metricCard: {
        width: '50%',
        paddingHorizontal: spacing.xs,
        marginBottom: spacing.md,
    },
    metricCard: {
        backgroundColor: colors.gray[900],
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        marginHorizontal: spacing.xs,
        marginBottom: spacing.md,
        width: '47%',
        borderLeftWidth: 4,
        flexDirection: 'row',
        alignItems: 'center',
    },
    metricIcon: {
        fontSize: 28,
        marginRight: spacing.sm,
    },
    metricContent: {
        flex: 1,
    },
    metricTitle: {
        fontSize: fontSize.xs,
        color: colors.gray[400],
        marginBottom: spacing.xs,
    },
    metricValue: {
        fontSize: fontSize.xl,
        fontWeight: fontWeight.bold,
        color: colors.white,
    },
    metricUnit: {
        fontSize: fontSize.sm,
        color: colors.gray[400],
    },
    sectionTitle: {
        fontSize: fontSize.lg,
        fontWeight: fontWeight.semibold,
        color: colors.white,
        marginTop: spacing.md,
        marginBottom: spacing.md,
    },
    actionsRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
    },
    actionButton: {
        flex: 1,
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        alignItems: 'center',
        marginHorizontal: spacing.xs,
    },
    rebootButton: {
        backgroundColor: colors.primary[600],
    },
    shutdownButton: {
        backgroundColor: colors.error,
    },
    actionIcon: {
        fontSize: 24,
        marginBottom: spacing.xs,
    },
    actionText: {
        fontSize: fontSize.sm,
        fontWeight: fontWeight.medium,
        color: colors.white,
    },
});
