import React, { useState } from 'react';
import {
    View,
    Text,
    TextInput,
    TouchableOpacity,
    StyleSheet,
    ActivityIndicator,
    KeyboardAvoidingView,
    Platform,
    Alert,
} from 'react-native';
import { colors, spacing, borderRadius, fontSize, fontWeight } from '../../theme';
import { useAuthStore } from '../../store/authStore';

export default function LoginScreen() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const login = useAuthStore((state) => state.login);

    const handleLogin = async () => {
        if (!username.trim() || !password.trim()) {
            Alert.alert('Error', 'Please enter username and password');
            return;
        }

        setLoading(true);
        const success = await login(username, password);
        setLoading(false);

        if (!success) {
            Alert.alert('Login Failed', 'Invalid username or password');
        }
    };

    return (
        <KeyboardAvoidingView
            style={styles.container}
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
            <View style={styles.content}>
                {/* Logo */}
                <View style={styles.logoContainer}>
                    <Text style={styles.logoEmoji}>🥧</Text>
                    <Text style={styles.title}>Pi Control</Text>
                    <Text style={styles.subtitle}>Universal Control Panel</Text>
                </View>

                {/* Form */}
                <View style={styles.form}>
                    <View style={styles.inputContainer}>
                        <Text style={styles.label}>Username</Text>
                        <TextInput
                            style={styles.input}
                            value={username}
                            onChangeText={setUsername}
                            placeholder="Enter username"
                            placeholderTextColor={colors.gray[500]}
                            autoCapitalize="none"
                            autoCorrect={false}
                        />
                    </View>

                    <View style={styles.inputContainer}>
                        <Text style={styles.label}>Password</Text>
                        <TextInput
                            style={styles.input}
                            value={password}
                            onChangeText={setPassword}
                            placeholder="Enter password"
                            placeholderTextColor={colors.gray[500]}
                            secureTextEntry
                        />
                    </View>

                    <TouchableOpacity
                        style={[styles.button, loading && styles.buttonDisabled]}
                        onPress={handleLogin}
                        disabled={loading}
                    >
                        {loading ? (
                            <ActivityIndicator color={colors.white} />
                        ) : (
                            <Text style={styles.buttonText}>Login</Text>
                        )}
                    </TouchableOpacity>
                </View>
            </View>
        </KeyboardAvoidingView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.gray[950],
    },
    content: {
        flex: 1,
        justifyContent: 'center',
        paddingHorizontal: spacing.lg,
    },
    logoContainer: {
        alignItems: 'center',
        marginBottom: spacing.xxl,
    },
    logoEmoji: {
        fontSize: 64,
        marginBottom: spacing.md,
    },
    title: {
        fontSize: fontSize['3xl'],
        fontWeight: fontWeight.bold,
        color: colors.white,
        marginBottom: spacing.xs,
    },
    subtitle: {
        fontSize: fontSize.base,
        color: colors.gray[400],
    },
    form: {
        backgroundColor: colors.gray[900],
        borderRadius: borderRadius.xl,
        padding: spacing.lg,
        borderWidth: 1,
        borderColor: colors.gray[800],
    },
    inputContainer: {
        marginBottom: spacing.md,
    },
    label: {
        fontSize: fontSize.sm,
        fontWeight: fontWeight.medium,
        color: colors.gray[400],
        marginBottom: spacing.xs,
    },
    input: {
        backgroundColor: colors.gray[800],
        borderRadius: borderRadius.md,
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm + 4,
        fontSize: fontSize.base,
        color: colors.white,
        borderWidth: 1,
        borderColor: colors.gray[700],
    },
    button: {
        backgroundColor: colors.primary[600],
        borderRadius: borderRadius.md,
        paddingVertical: spacing.md,
        alignItems: 'center',
        marginTop: spacing.md,
    },
    buttonDisabled: {
        opacity: 0.7,
    },
    buttonText: {
        fontSize: fontSize.base,
        fontWeight: fontWeight.semibold,
        color: colors.white,
    },
});
