import React from 'react';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Text } from 'react-native';

import { useAuthStore } from '../store/authStore';
import { colors } from '../theme';

// Screens
import LoginScreen from '../screens/auth/LoginScreen';
import DashboardScreen from '../screens/home/DashboardScreen';
import ServicesScreen from '../screens/services/ServicesScreen';
import DevicesScreen from '../screens/devices/DevicesScreen';
import AlertsScreen from '../screens/alerts/AlertsScreen';

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
    };
    return (
        <Text style={{ fontSize: focused ? 24 : 20, opacity: focused ? 1 : 0.6 }}>
            {icons[name]}
        </Text>
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
        </Tab.Navigator>
    );
}

export default function AppNavigator() {
    const { isAuthenticated, isLoading } = useAuthStore();

    if (isLoading) {
        return null; // Or a splash screen
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
