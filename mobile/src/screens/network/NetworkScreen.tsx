import React, { useEffect, useState } from 'react';
import {
    View,
    Text,
    FlatList,
    StyleSheet,
    RefreshControl,
    ActivityIndicator,
} from 'react-native';
import { colors, spacing, borderRadius, fontSize, fontWeight } from '../../theme';
import { api } from '../../services/api';

interface NetworkInterface {
    name: string;
    type: string;
    state: string;
    mac?: string;
    ipv4?: string;
    ipv6?: string;
}

function InterfaceCard({ iface }: { iface: NetworkInterface }) {
    const getIcon = (type: string) => {
        switch (type) {
            case 'ethernet': return '🔌';
            case 'wifi': return '📶';
            case 'loopback': return '🔄';
            default: return '🌐';
        }
    };

    const isUp = iface.state === 'up';

    return (
        <View style={styles.card}>
            <View style={styles.cardHeader}>
                <Text style={styles.icon}>{getIcon(iface.type)}</Text>
                <View style={styles.cardInfo}>
                    <Text style={styles.ifaceName}>{iface.name}</Text>
                    <Text style={styles.ifaceType}>{iface.type}</Text>
                </View>
                <View style={[styles.stateBadge, isUp ? styles.stateUp : styles.stateDown]}>
                    <Text style={styles.stateText}>{iface.state}</Text>
                </View>
            </View>

            {iface.ipv4 && (
                <View style={styles.addressRow}>
                    <Text style={styles.addressLabel}>IPv4:</Text>
                    <Text style={styles.addressValue}>{iface.ipv4}</Text>
                </View>
            )}

            {iface.mac && (
                <View style={styles.addressRow}>
                    <Text style={styles.addressLabel}>MAC:</Text>
                    <Text style={styles.addressValue}>{iface.mac}</Text>
                </View>
            )}
        </View>
    );
}

export default function NetworkScreen() {
    const [interfaces, setInterfaces] = useState<NetworkInterface[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const fetchInterfaces = async () => {
        try {
            const { data } = await api.get<NetworkInterface[]>('/network/interfaces');
            setInterfaces(data);
        } catch (error) {
            console.error('Failed to fetch interfaces:', error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchInterfaces();
    }, []);

    const onRefresh = () => {
        setRefreshing(true);
        fetchInterfaces();
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
            data={interfaces}
            keyExtractor={(item) => item.name}
            refreshControl={
                <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary[500]} />
            }
            renderItem={({ item }) => <InterfaceCard iface={item} />}
            ListEmptyComponent={
                <View style={styles.emptyContainer}>
                    <Text style={styles.emptyText}>No interfaces found</Text>
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
        marginBottom: spacing.sm,
    },
    icon: {
        fontSize: 24,
        marginRight: spacing.md,
    },
    cardInfo: {
        flex: 1,
    },
    ifaceName: {
        fontSize: fontSize.base,
        fontWeight: fontWeight.semibold,
        color: colors.white,
    },
    ifaceType: {
        fontSize: fontSize.xs,
        color: colors.gray[500],
        textTransform: 'capitalize',
    },
    stateBadge: {
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.xs,
        borderRadius: borderRadius.full,
    },
    stateUp: {
        backgroundColor: colors.success,
    },
    stateDown: {
        backgroundColor: colors.gray[600],
    },
    stateText: {
        fontSize: fontSize.xs,
        fontWeight: fontWeight.medium,
        color: colors.white,
        textTransform: 'uppercase',
    },
    addressRow: {
        flexDirection: 'row',
        marginTop: spacing.xs,
    },
    addressLabel: {
        fontSize: fontSize.sm,
        color: colors.gray[500],
        width: 50,
    },
    addressValue: {
        fontSize: fontSize.sm,
        color: colors.gray[300],
        fontFamily: 'monospace',
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
