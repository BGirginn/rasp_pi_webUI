import React, { useState } from 'react';
import {
    View,
    Text,
    ScrollView,
    StyleSheet,
    TouchableOpacity,
    TextInput,
    Alert,
    Switch,
} from 'react-native';
import { colors, spacing, borderRadius, fontSize, fontWeight } from '../../theme';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../services/api';

function SettingSection({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <View style={styles.section}>
            <Text style={styles.sectionTitle}>{title}</Text>
            <View style={styles.sectionContent}>{children}</View>
        </View>
    );
}

function SettingRow({
    icon,
    label,
    value,
    onPress
}: {
    icon: string;
    label: string;
    value?: string;
    onPress?: () => void;
}) {
    return (
        <TouchableOpacity style={styles.settingRow} onPress={onPress} disabled={!onPress}>
            <Text style={styles.settingIcon}>{icon}</Text>
            <Text style={styles.settingLabel}>{label}</Text>
            {value && <Text style={styles.settingValue}>{value}</Text>}
            {onPress && <Text style={styles.chevron}>›</Text>}
        </TouchableOpacity>
    );
}

export default function SettingsScreen() {
    const { user, logout } = useAuthStore();
    const [showPasswordModal, setShowPasswordModal] = useState(false);
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [notifications, setNotifications] = useState(true);

    const handleChangePassword = async () => {
        if (!currentPassword || !newPassword) {
            Alert.alert('Error', 'Please fill in all fields');
            return;
        }

        try {
            await api.post('/auth/password/change', {
                current_password: currentPassword,
                new_password: newPassword,
            });
            Alert.alert('Success', 'Password changed successfully');
            setShowPasswordModal(false);
            setCurrentPassword('');
            setNewPassword('');
        } catch (error) {
            Alert.alert('Error', 'Failed to change password');
        }
    };

    const handleLogout = () => {
        Alert.alert('Logout', 'Are you sure you want to logout?', [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Logout', style: 'destructive', onPress: logout },
        ]);
    };

    return (
        <ScrollView style={styles.container} contentContainerStyle={styles.content}>
            {/* Profile Section */}
            <SettingSection title="Profile">
                <View style={styles.profileCard}>
                    <View style={styles.avatar}>
                        <Text style={styles.avatarText}>{user?.username?.[0]?.toUpperCase() || '?'}</Text>
                    </View>
                    <View style={styles.profileInfo}>
                        <Text style={styles.username}>{user?.username}</Text>
                        <Text style={styles.role}>{user?.role}</Text>
                    </View>
                </View>
            </SettingSection>

            {/* Security Section */}
            <SettingSection title="Security">
                <SettingRow
                    icon="🔑"
                    label="Change Password"
                    onPress={() => setShowPasswordModal(true)}
                />
                <SettingRow icon="🔐" label="Two-Factor Auth" value="Not enabled" />
            </SettingSection>

            {/* Notifications Section */}
            <SettingSection title="Notifications">
                <View style={styles.switchRow}>
                    <Text style={styles.settingIcon}>🔔</Text>
                    <Text style={styles.settingLabel}>Push Notifications</Text>
                    <Switch
                        value={notifications}
                        onValueChange={setNotifications}
                        trackColor={{ false: colors.gray[700], true: colors.primary[600] }}
                        thumbColor={colors.white}
                    />
                </View>
            </SettingSection>

            {/* About Section */}
            <SettingSection title="About">
                <SettingRow icon="📱" label="App Version" value="1.0.0" />
                <SettingRow icon="🥧" label="Pi Control Panel" value="v2.0" />
            </SettingSection>

            {/* Logout Button */}
            <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
                <Text style={styles.logoutText}>🚪 Logout</Text>
            </TouchableOpacity>

            {/* Password Modal */}
            {showPasswordModal && (
                <View style={styles.modalOverlay}>
                    <View style={styles.modal}>
                        <Text style={styles.modalTitle}>Change Password</Text>
                        <TextInput
                            style={styles.input}
                            placeholder="Current Password"
                            placeholderTextColor={colors.gray[500]}
                            secureTextEntry
                            value={currentPassword}
                            onChangeText={setCurrentPassword}
                        />
                        <TextInput
                            style={styles.input}
                            placeholder="New Password"
                            placeholderTextColor={colors.gray[500]}
                            secureTextEntry
                            value={newPassword}
                            onChangeText={setNewPassword}
                        />
                        <View style={styles.modalButtons}>
                            <TouchableOpacity
                                style={[styles.modalButton, styles.cancelButton]}
                                onPress={() => setShowPasswordModal(false)}
                            >
                                <Text style={styles.cancelButtonText}>Cancel</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={[styles.modalButton, styles.confirmButton]}
                                onPress={handleChangePassword}
                            >
                                <Text style={styles.confirmButtonText}>Change</Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            )}
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
        fontSize: fontSize.sm,
        fontWeight: fontWeight.medium,
        color: colors.gray[400],
        marginBottom: spacing.sm,
        marginLeft: spacing.sm,
        textTransform: 'uppercase',
        letterSpacing: 1,
    },
    sectionContent: {
        backgroundColor: colors.gray[900],
        borderRadius: borderRadius.lg,
        borderWidth: 1,
        borderColor: colors.gray[800],
        overflow: 'hidden',
    },
    profileCard: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: spacing.md,
    },
    avatar: {
        width: 60,
        height: 60,
        borderRadius: 30,
        backgroundColor: colors.primary[600],
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: spacing.md,
    },
    avatarText: {
        fontSize: fontSize['2xl'],
        fontWeight: fontWeight.bold,
        color: colors.white,
    },
    profileInfo: {
        flex: 1,
    },
    username: {
        fontSize: fontSize.lg,
        fontWeight: fontWeight.semibold,
        color: colors.white,
    },
    role: {
        fontSize: fontSize.sm,
        color: colors.gray[400],
        textTransform: 'capitalize',
    },
    settingRow: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: spacing.md,
        borderBottomWidth: 1,
        borderBottomColor: colors.gray[800],
    },
    switchRow: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: spacing.md,
    },
    settingIcon: {
        fontSize: 20,
        marginRight: spacing.md,
    },
    settingLabel: {
        flex: 1,
        fontSize: fontSize.base,
        color: colors.white,
    },
    settingValue: {
        fontSize: fontSize.sm,
        color: colors.gray[400],
    },
    chevron: {
        fontSize: fontSize.xl,
        color: colors.gray[500],
        marginLeft: spacing.sm,
    },
    logoutButton: {
        backgroundColor: colors.error,
        borderRadius: borderRadius.lg,
        padding: spacing.md,
        alignItems: 'center',
        marginTop: spacing.md,
    },
    logoutText: {
        fontSize: fontSize.base,
        fontWeight: fontWeight.semibold,
        color: colors.white,
    },
    modalOverlay: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.8)',
        justifyContent: 'center',
        padding: spacing.lg,
    },
    modal: {
        backgroundColor: colors.gray[900],
        borderRadius: borderRadius.xl,
        padding: spacing.lg,
    },
    modalTitle: {
        fontSize: fontSize.xl,
        fontWeight: fontWeight.semibold,
        color: colors.white,
        marginBottom: spacing.lg,
        textAlign: 'center',
    },
    input: {
        backgroundColor: colors.gray[800],
        borderRadius: borderRadius.md,
        padding: spacing.md,
        fontSize: fontSize.base,
        color: colors.white,
        marginBottom: spacing.md,
        borderWidth: 1,
        borderColor: colors.gray[700],
    },
    modalButtons: {
        flexDirection: 'row',
        gap: spacing.md,
        marginTop: spacing.md,
    },
    modalButton: {
        flex: 1,
        padding: spacing.md,
        borderRadius: borderRadius.md,
        alignItems: 'center',
    },
    cancelButton: {
        backgroundColor: colors.gray[700],
    },
    confirmButton: {
        backgroundColor: colors.primary[600],
    },
    cancelButtonText: {
        color: colors.white,
        fontWeight: fontWeight.medium,
    },
    confirmButtonText: {
        color: colors.white,
        fontWeight: fontWeight.semibold,
    },
});
