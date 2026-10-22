import { useState, type ReactNode } from 'react';
import { AuthContext, AUTH_STORAGE_KEY, DEMO_USER, type User } from './auth-context';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(AUTH_STORAGE_KEY);
      if (stored) {
        try {
          return JSON.parse(stored) as User;
        } catch {
          // ignore corrupted data
        }
      }
    }
    return null;
  });

  const login = (email: string, name = 'Demo User', businessName?: string) => {
    const newUser: User = {
      id: `usr_${Date.now()}`,
      name,
      email,
      businessName: businessName || `${name.split(' ')[0]}'s Venture`,
    };
    setUser(newUser);
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(newUser));
  };

  const demoLogin = () => {
    setUser(DEMO_USER);
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(DEMO_USER));
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(AUTH_STORAGE_KEY);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        login,
        logout,
        demoLogin,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
