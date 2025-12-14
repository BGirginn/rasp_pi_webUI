import React, { useEffect, useState } from 'react';
import {
    View,
    Text,
    FlatList,
    StyleSheet,
    RefreshControl,
    TouchableOpacity,
    ActivityIndicator,
} from 'react-native';
import { colors, spacing, borderRadius, fontSize, fontWeight } from '../../theme';
import { api } from '../../services/api';

interface Device {
    id: string;
    name: string;
    type: string;
    state: string;
    product?: string;
    manufacturer?: string;
    path?: string;
}

function DeviceCard({ device }: { device: Device }) {
    const getIcon = (type: string) => {
        switch (type) {
            case 'usb': return '🔌';
            case 'serial': return '📡';
            case 'esp': return '📶';
            default: return '💻';
        }
    };

    const getStateColor = (state: string) => {
        switch (state) {
            case 'connected': return colors.success;
            case 'disconnected': return colors.gray[500];
            default: return colors.warning;
        }
    };

    return (
        <View style={styles.card}>
            <View style={styles.cardHeader}>
                <Text style={styles.icon}>{getIcon(device.type)}</Text>
                <View style={styles.cardInfo}>
                    <Text style={styles.deviceName}>{device.product || device.name}</Text>
                    <Text style={styles.devicePath}>{device.path || device.id}</Text>
                </View>
                <View style={[styles.stateBadge, { backgroundColor: getStateColor(device.state) }]}>
                    <Text style={styles.stateText}>{device.state}</Text>
                </View>
            </View>
            {device.manufacturer && (
                <Text style={styles.manufacturer}>{device.manufacturer}</Text>
            )}
        </View>
    );
}

export default function DevicesScreen() {
    const [devices, setDevices] = useState<Device[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const fetchDevices = async () => {
        try {
            const { data } = await api.get<Device[]>('/devices');
            setDevices(data);
        } catch (error) {
            console.error('Failed to fetch devices:', error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchDevices();
    }, []);

    const onRefresh = () => {
        setRefreshing(true);
        fetchDevices();
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
            data={devices}
            keyExtractor={(item) => item.id}
            refreshControl={
                <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary[500]} />
            }
            renderItem={({ item }) => <DeviceCard device={item} />}
            ListEmptyComponent={
                <View style={styles.emptyContainer}>
                    <Text style={styles.emptyIcon}>🔌</Text>
                    <Text style={styles.emptyText}>No devices connected</Text>
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
    },
    icon: {
        fontSize: 28,
        marginRight: spacing.md,
    },
    cardInfo: {
        flex: 1,
    },
    deviceName: {
        fontSize: fontSize.base,
        fontWeight: fontWeight.semibold,
        color: colors.white,
    },
    devicePath: {
        fontSize: fontSize.xs,
        color: colors.gray[500],
        fontFamily: 'monospace',
    },
    stateBadge: {
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.xs,
        borderRadius: borderRadius.full,
    },
    stateText: {
        fontSize: fontSize.xs,
        fontWeight: fontWeight.medium,
        color: colors.white,
        textTransform: 'capitalize',
    },
    manufacturer: {
        fontSize: fontSize.sm,
        color: colors.gray[400],
        marginTop: spacing.sm,
    },
    emptyContainer: {
        alignItems: 'center',
        paddingVertical: spacing.xxl,
    },
    emptyIcon: {
        fontSize: 48,
        marginBottom: spacing.md,
    },
    emptyText: {
        fontSize: fontSize.base,
        color: colors.gray[400],
    },
});
