import { createContext, useContext, useState } from 'react';
const NavigationContext = createContext(undefined);
export function NavigationProvider({ children }) {
    const [currentPage, setCurrentPage] = useState('dashboard');
    return (<NavigationContext.Provider value={{ currentPage, setCurrentPage }}>
      {children}
    </NavigationContext.Provider>);
}
export function useNavigation() {
    const context = useContext(NavigationContext);
    if (context === undefined) {
        throw new Error('useNavigation must be used within a NavigationProvider');
    }
    return context;
}
