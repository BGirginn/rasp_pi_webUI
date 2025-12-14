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

interface Service {
    id: string;
    name: string;
    type: string;
    state: string;
    description?: string;
}

function ServiceCard({ service, onAction }: { service: Service; onAction: (action: string) => void }) {
    const isRunning = service.state === 'running';

    return (
        <View style={styles.card}>
            <View style={styles.cardHeader}>
                <View style={[styles.statusDot, isRunning ? styles.statusRunning : styles.statusStopped]} />
                <Text style={styles.serviceName}>{service.name}</Text>
            </View>
            <Text style={styles.serviceDescription} numberOfLines={1}>
                {service.description || 'No description'}
            </Text>
            <View style={styles.cardActions}>
                {isRunning ? (
                    <>
                        <TouchableOpacity
                            style={[styles.actionBtn, styles.restartBtn]}
                            onPress={() => onAction('restart')}
                        >
                            <Text style={styles.actionBtnText}>🔄 Restart</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                            style={[styles.actionBtn, styles.stopBtn]}
                            onPress={() => onAction('stop')}
                        >
                            <Text style={styles.actionBtnText}>⏹ Stop</Text>
                        </TouchableOpacity>
                    </>
                ) : (
                    <TouchableOpacity
                        style={[styles.actionBtn, styles.startBtn]}
                        onPress={() => onAction('start')}
                    >
                        <Text style={styles.actionBtnText}>▶️ Start</Text>
                    </TouchableOpacity>
                )}
            </View>
        </View>
    );
}

export default function ServicesScreen() {
    const [services, setServices] = useState<Service[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [actionLoading, setActionLoading] = useState<string | null>(null);

    const fetchServices = async () => {
        try {
            const { data } = await api.get<Service[]>('/resources?type=systemd');
            setServices(data);
        } catch (error) {
            console.error('Failed to fetch services:', error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchServices();
    }, []);

    const onRefresh = () => {
        setRefreshing(true);
        fetchServices();
    };

    const handleAction = async (serviceId: string, action: string) => {
        setActionLoading(serviceId);
        try {
            await api.post(`/resources/${serviceId}/action`, { action });
            Alert.alert('Success', `Service ${action} successful`);
            fetchServices();
        } catch (error) {
            Alert.alert('Error', `Failed to ${action} service`);
        } finally {
            setActionLoading(null);
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
            data={services}
            keyExtractor={(item) => item.id}
            refreshControl={
                <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary[500]} />
            }
            renderItem={({ item }) => (
                <ServiceCard
                    service={item}
                    onAction={(action) => handleAction(item.id, action)}
                />
            )}
            ListEmptyComponent={
                <View style={styles.emptyContainer}>
                    <Text style={styles.emptyText}>No services found</Text>
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
        borderWidth: 1,
        borderColor: colors.gray[800],
    },
    cardHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: spacing.xs,
    },
    statusDot: {
        width: 10,
        height: 10,
        borderRadius: 5,
        marginRight: spacing.sm,
    },
    statusRunning: {
        backgroundColor: colors.success,
    },
    statusStopped: {
        backgroundColor: colors.gray[500],
    },
    serviceName: {
        fontSize: fontSize.base,
        fontWeight: fontWeight.semibold,
        color: colors.white,
        flex: 1,
    },
    serviceDescription: {
        fontSize: fontSize.sm,
        color: colors.gray[400],
        marginBottom: spacing.md,
    },
    cardActions: {
        flexDirection: 'row',
        justifyContent: 'flex-end',
        gap: spacing.sm,
    },
    actionBtn: {
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        borderRadius: borderRadius.md,
    },
    startBtn: {
        backgroundColor: colors.success,
    },
    stopBtn: {
        backgroundColor: colors.error,
    },
    restartBtn: {
        backgroundColor: colors.primary[600],
    },
    actionBtnText: {
        fontSize: fontSize.sm,
        fontWeight: fontWeight.medium,
        color: colors.white,
    },
    emptyContainer: {
        alignItems: 'center',
        paddingVertical: spacing.xxl,
    },
    emptyText: {
        fontSize: fontSize.base,
        color: colors.gray[400],
    },
});
