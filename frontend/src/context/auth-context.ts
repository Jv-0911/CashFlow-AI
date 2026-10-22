import { createContext } from 'react';

export interface User {
  id: string;
  name: string;
  email: string;
  businessName: string;
}

export interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, name?: string) => void;
  logout: () => void;
  demoLogin: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const DEMO_USER: User = {
  id: 'usr_demo_001',
  name: 'Alex Morgan',
  email: 'alex@novacraft.io',
  businessName: 'NovaCraft Studio',
};

export const AUTH_STORAGE_KEY = 'cashflow_ai_user';
