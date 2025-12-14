import React from 'react';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Text, View } from 'react-native';

import { useAuthStore } from '../store/authStore';
import { colors } from '../theme';

// Screens
import LoginScreen from '../screens/auth/LoginScreen';
import DashboardScreen from '../screens/home/DashboardScreen';
import ServicesScreen from '../screens/services/ServicesScreen';
import DevicesScreen from '../screens/devices/DevicesScreen';
import AlertsScreen from '../screens/alerts/AlertsScreen';
import NetworkScreen from '../screens/network/NetworkScreen';
import TelemetryScreen from '../screens/telemetry/TelemetryScreen';
import SettingsScreen from '../screens/settings/SettingsScreen';
import CommandScreen from '../screens/commands/CommandScreen';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

const darkTheme = {
    ...DefaultTheme,
    colors: {
        ...DefaultTheme.colors,
        primary: colors.primary[500],
        background: colors.gray[950],
        card: colors.gray[900],
        text: colors.white,
        border: colors.gray[800],
    },
};

function TabIcon({ name, focused }: { name: string; focused: boolean }) {
    const icons: Record<string, string> = {
        Home: '🏠',
        Services: '⚙️',
        Devices: '🔌',
        Alerts: '🔔',
        More: '☰',
    };
    return (
        <Text style={{ fontSize: focused ? 24 : 20, opacity: focused ? 1 : 0.6 }}>
            {icons[name]}
        </Text>
    );
}

function MoreStack() {
    return (
        <Stack.Navigator
            screenOptions={{
                headerStyle: { backgroundColor: colors.gray[900] },
                headerTintColor: colors.white,
            }}
        >
            <Stack.Screen name="MoreMenu" component={MoreMenuScreen} options={{ title: 'More' }} />
            <Stack.Screen name="Network" component={NetworkScreen} />
            <Stack.Screen name="Telemetry" component={TelemetryScreen} />
            <Stack.Screen name="Commands" component={CommandScreen} options={{ title: 'Command Runner' }} />
            <Stack.Screen name="Settings" component={SettingsScreen} />
        </Stack.Navigator>
    );
}

function MoreMenuScreen({ navigation }: any) {
    const menuItems = [
        { name: 'Network', icon: '🌐', screen: 'Network' },
        { name: 'Telemetry', icon: '📊', screen: 'Telemetry' },
        { name: 'Commands', icon: '💻', screen: 'Commands' },
        { name: 'Settings', icon: '🔧', screen: 'Settings' },
    ];

    return (
        <View style={{ flex: 1, backgroundColor: colors.gray[950], padding: 16 }}>
            {menuItems.map((item) => (
                <View
                    key={item.name}
                    style={{
                        backgroundColor: colors.gray[900],
                        borderRadius: 12,
                        marginBottom: 12,
                        borderWidth: 1,
                        borderColor: colors.gray[800],
                    }}
                >
                    <Text
                        style={{
                            fontSize: 16,
                            color: colors.white,
                            padding: 16,
                        }}
                        onPress={() => navigation.navigate(item.screen)}
                    >
                        {item.icon}  {item.name}
                    </Text>
                </View>
            ))}
        </View>
    );
}

function MainTabs() {
    return (
        <Tab.Navigator
            screenOptions={({ route }) => ({
                tabBarIcon: ({ focused }) => <TabIcon name={route.name} focused={focused} />,
                tabBarActiveTintColor: colors.primary[500],
                tabBarInactiveTintColor: colors.gray[500],
                tabBarStyle: {
                    backgroundColor: colors.gray[900],
                    borderTopColor: colors.gray[800],
                    height: 60,
                    paddingBottom: 8,
                },
                headerStyle: {
                    backgroundColor: colors.gray[900],
                },
                headerTintColor: colors.white,
            })}
        >
            <Tab.Screen name="Home" component={DashboardScreen} options={{ title: 'Dashboard' }} />
            <Tab.Screen name="Services" component={ServicesScreen} />
            <Tab.Screen name="Devices" component={DevicesScreen} />
            <Tab.Screen name="Alerts" component={AlertsScreen} />
            <Tab.Screen name="More" component={MoreStack} options={{ headerShown: false }} />
        </Tab.Navigator>
    );
}

export default function AppNavigator() {
    const { isAuthenticated, isLoading } = useAuthStore();

    if (isLoading) {
        return (
            <View style={{ flex: 1, backgroundColor: colors.gray[950], justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 48 }}>🥧</Text>
            </View>
        );
    }

    return (
        <NavigationContainer theme={darkTheme}>
            <Stack.Navigator screenOptions={{ headerShown: false }}>
                {isAuthenticated ? (
                    <Stack.Screen name="Main" component={MainTabs} />
                ) : (
                    <Stack.Screen name="Login" component={LoginScreen} />
                )}
            </Stack.Navigator>
        </NavigationContainer>
    );
}
