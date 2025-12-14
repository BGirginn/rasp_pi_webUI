import React, { useState, useRef } from 'react';
import {
    View,
    Text,
    TextInput,
    ScrollView,
    StyleSheet,
    TouchableOpacity,
    KeyboardAvoidingView,
    Platform,
    Alert,
} from 'react-native';
import { colors, spacing, borderRadius, fontSize, fontWeight } from '../../theme';
import { api } from '../../services/api';

interface CommandOutput {
    command: string;
    output: string;
    success: boolean;
    timestamp: Date;
}

export default function CommandScreen() {
    const [command, setCommand] = useState('');
    const [history, setHistory] = useState<CommandOutput[]>([]);
    const [loading, setLoading] = useState(false);
    const scrollRef = useRef<ScrollView>(null);

    const runCommand = async () => {
        if (!command.trim()) return;

        const cmd = command.trim();
        setCommand('');
        setLoading(true);

        try {
            const { data } = await api.post<{ output: string; exit_code: number }>('/terminal/exec', {
                command: cmd,
            });

            setHistory((prev) => [
                ...prev,
                {
                    command: cmd,
                    output: data.output || '(no output)',
                    success: data.exit_code === 0,
                    timestamp: new Date(),
                },
            ]);
        } catch (error: any) {
            setHistory((prev) => [
                ...prev,
                {
                    command: cmd,
                    output: error.message || 'Command failed',
                    success: false,
                    timestamp: new Date(),
                },
            ]);
        } finally {
            setLoading(false);
            setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
        }
    };

    const clearHistory = () => {
        Alert.alert('Clear History', 'Are you sure?', [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Clear', style: 'destructive', onPress: () => setHistory([]) },
        ]);
    };

    const quickCommands = [
        { label: 'uptime', cmd: 'uptime' },
        { label: 'df -h', cmd: 'df -h' },
        { label: 'free -m', cmd: 'free -m' },
        { label: 'top -bn1', cmd: 'top -bn1 | head -20' },
    ];

    return (
        <KeyboardAvoidingView
            style={styles.container}
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            keyboardVerticalOffset={90}
        >
            {/* Quick Commands */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.quickBar}>
                {quickCommands.map((qc) => (
                    <TouchableOpacity
                        key={qc.label}
                        style={styles.quickButton}
                        onPress={() => setCommand(qc.cmd)}
                    >
                        <Text style={styles.quickButtonText}>{qc.label}</Text>
                    </TouchableOpacity>
                ))}
                <TouchableOpacity style={styles.clearButton} onPress={clearHistory}>
                    <Text style={styles.clearButtonText}>🗑️</Text>
                </TouchableOpacity>
            </ScrollView>

            {/* Output History */}
            <ScrollView ref={scrollRef} style={styles.output} contentContainerStyle={styles.outputContent}>
                {history.length === 0 ? (
                    <View style={styles.emptyContainer}>
                        <Text style={styles.emptyIcon}>💻</Text>
                        <Text style={styles.emptyText}>Run a command to see output</Text>
                    </View>
                ) : (
                    history.map((item, index) => (
                        <View key={index} style={styles.outputBlock}>
                            <View style={styles.commandRow}>
                                <Text style={styles.prompt}>$</Text>
                                <Text style={styles.commandText}>{item.command}</Text>
                            </View>
                            <Text style={[styles.outputText, !item.success && styles.errorText]}>
                                {item.output}
                            </Text>
                        </View>
                    ))
                )}
            </ScrollView>

            {/* Input */}
            <View style={styles.inputContainer}>
                <Text style={styles.inputPrompt}>$</Text>
                <TextInput
                    style={styles.input}
                    value={command}
                    onChangeText={setCommand}
                    placeholder="Enter command..."
                    placeholderTextColor={colors.gray[500]}
                    autoCapitalize="none"
                    autoCorrect={false}
                    returnKeyType="send"
                    onSubmitEditing={runCommand}
                    editable={!loading}
                />
                <TouchableOpacity
                    style={[styles.runButton, loading && styles.runButtonDisabled]}
                    onPress={runCommand}
                    disabled={loading}
                >
                    <Text style={styles.runButtonText}>{loading ? '...' : '▶'}</Text>
                </TouchableOpacity>
            </View>
        </KeyboardAvoidingView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: colors.gray[950],
    },
    quickBar: {
        flexGrow: 0,
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: colors.gray[800],
    },
    quickButton: {
        backgroundColor: colors.gray[800],
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        borderRadius: borderRadius.md,
        marginRight: spacing.sm,
    },
    quickButtonText: {
        fontSize: fontSize.sm,
        color: colors.gray[300],
        fontFamily: 'monospace',
    },
    clearButton: {
        backgroundColor: colors.gray[800],
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        borderRadius: borderRadius.md,
    },
    clearButtonText: {
        fontSize: fontSize.base,
    },
    output: {
        flex: 1,
    },
    outputContent: {
        padding: spacing.md,
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
    outputBlock: {
        marginBottom: spacing.md,
    },
    commandRow: {
        flexDirection: 'row',
        marginBottom: spacing.xs,
    },
    prompt: {
        fontSize: fontSize.sm,
        fontFamily: 'monospace',
        color: colors.success,
        marginRight: spacing.xs,
    },
    commandText: {
        fontSize: fontSize.sm,
        fontFamily: 'monospace',
        color: colors.white,
        flex: 1,
    },
    outputText: {
        fontSize: fontSize.sm,
        fontFamily: 'monospace',
        color: colors.gray[300],
        backgroundColor: colors.gray[900],
        padding: spacing.sm,
        borderRadius: borderRadius.md,
    },
    errorText: {
        color: colors.error,
    },
    inputContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: spacing.md,
        backgroundColor: colors.gray[900],
        borderTopWidth: 1,
        borderTopColor: colors.gray[800],
    },
    inputPrompt: {
        fontSize: fontSize.lg,
        fontFamily: 'monospace',
        color: colors.success,
        marginRight: spacing.sm,
    },
    input: {
        flex: 1,
        fontSize: fontSize.base,
        fontFamily: 'monospace',
        color: colors.white,
        paddingVertical: spacing.sm,
    },
    runButton: {
        backgroundColor: colors.primary[600],
        width: 44,
        height: 44,
        borderRadius: 22,
        justifyContent: 'center',
        alignItems: 'center',
        marginLeft: spacing.sm,
    },
    runButtonDisabled: {
        opacity: 0.5,
    },
    runButtonText: {
        fontSize: fontSize.lg,
        color: colors.white,
    },
});
