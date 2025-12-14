import React, { useEffect, useState } from 'react';
import {
    View,
    Text,
    FlatList,
    StyleSheet,
    RefreshControl,
    TouchableOpacity,
    Alert,
    ActivityIndicator,
} from 'react-native';
import { colors, spacing, borderRadius, fontSize, fontWeight } from '../../theme';
import { api } from '../../services/api';

interface AlertItem {
    id: string;
    rule_id: string;
    rule_name: string;
    state: string;
    severity: string;
    message: string;
    value: number;
    fired_at: string;
}

function AlertCard({ alert, onAcknowledge }: { alert: AlertItem; onAcknowledge: () => void }) {
    const getSeverityColor = (severity: string) => {
        switch (severity) {
            case 'critical': return colors.error;
            case 'warning': return colors.warning;
            default: return colors.info;
        }
    };

    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case 'critical': return '🔴';
            case 'warning': return '🟡';
            default: return '🔵';
        }
    };

    return (
        <View style={[styles.card, { borderLeftColor: getSeverityColor(alert.severity) }]}>
            <View style={styles.cardHeader}>
                <Text style={styles.severityIcon}>{getSeverityIcon(alert.severity)}</Text>
                <View style={styles.cardInfo}>
                    <Text style={styles.alertName}>{alert.rule_name}</Text>
                    <Text style={styles.alertTime}>
                        {new Date(alert.fired_at).toLocaleString()}
                    </Text>
                </View>
                <View style={[styles.stateBadge, alert.state === 'firing' && styles.firingBadge]}>
                    <Text style={styles.stateText}>{alert.state}</Text>
                </View>
            </View>
            <Text style={styles.message}>{alert.message}</Text>
            {alert.state === 'firing' && (
                <TouchableOpacity style={styles.ackButton} onPress={onAcknowledge}>
                    <Text style={styles.ackButtonText}>✓ Acknowledge</Text>
                </TouchableOpacity>
            )}
        </View>
    );
}

export default function AlertsScreen() {
    const [alerts, setAlerts] = useState<AlertItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const fetchAlerts = async () => {
        try {
            const { data } = await api.get<AlertItem[]>('/alerts');
            setAlerts(data);
        } catch (error) {
            console.error('Failed to fetch alerts:', error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchAlerts();
        const interval = setInterval(fetchAlerts, 10000);
        return () => clearInterval(interval);
    }, []);

    const onRefresh = () => {
        setRefreshing(true);
        fetchAlerts();
    };

    const handleAcknowledge = async (alertId: string) => {
        try {
            await api.post(`/alerts/${alertId}/acknowledge`);
            fetchAlerts();
        } catch (error) {
            Alert.alert('Error', 'Failed to acknowledge alert');
        }
    };

    if (loading) {
        return (
            <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color={colors.primary[500]} />
            </View>
        );
    }

    return (
        <FlatList
            style={styles.container}
            contentContainerStyle={styles.content}
            data={alerts}
            keyExtractor={(item) => item.id}
            refreshControl={
                <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary[500]} />
            }
            renderItem={({ item }) => (
                <AlertCard alert={item} onAcknowledge={() => handleAcknowledge(item.id)} />
            )}
            ListEmptyComponent={
                <View style={styles.emptyContainer}>
                    <Text style={styles.emptyIcon}>✅</Text>
                    <Text style={styles.emptyTitle}>All Clear</Text>
                    <Text style={styles.emptyText}>No active alerts</Text>
                </View>
            }
        />
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
    card: {
        backgroundColor: colors.gray[900],
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        marginBottom: spacing.md,
        borderLeftWidth: 4,
        borderWidth: 1,
        borderColor: colors.gray[800],
    },
    cardHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: spacing.sm,
    },
    severityIcon: {
        fontSize: 20,
        marginRight: spacing.sm,
    },
    cardInfo: {
        flex: 1,
    },
    alertName: {
        fontSize: fontSize.base,
        fontWeight: fontWeight.semibold,
        color: colors.white,
    },
    alertTime: {
        fontSize: fontSize.xs,
        color: colors.gray[500],
    },
    stateBadge: {
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.xs,
        borderRadius: borderRadius.full,
        backgroundColor: colors.gray[700],
    },
    firingBadge: {
        backgroundColor: colors.error,
    },
    stateText: {
        fontSize: fontSize.xs,
        fontWeight: fontWeight.medium,
        color: colors.white,
        textTransform: 'capitalize',
    },
    message: {
        fontSize: fontSize.sm,
        color: colors.gray[300],
        marginBottom: spacing.md,
    },
    ackButton: {
        backgroundColor: colors.primary[600],
        paddingVertical: spacing.sm,
        borderRadius: borderRadius.md,
        alignItems: 'center',
    },
    ackButtonText: {
        fontSize: fontSize.sm,
        fontWeight: fontWeight.medium,
        color: colors.white,
    },
    emptyContainer: {
        alignItems: 'center',
        paddingVertical: spacing.xxl,
    },
    emptyIcon: {
        fontSize: 48,
        marginBottom: spacing.md,
    },
    emptyTitle: {
        fontSize: fontSize.xl,
        fontWeight: fontWeight.semibold,
        color: colors.white,
        marginBottom: spacing.xs,
    },
    emptyText: {
        fontSize: fontSize.base,
        color: colors.gray[400],
    },
});
