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
  login: (email: string, password: string) => Promise<void>;
  serverAuthenticated: boolean;
  loading: boolean;
  logout: () => Promise<void>;
  demoLogin: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const DEMO_USER: User = {
  id: 'usr_demo_001',
  name: 'Business Owner',
  email: 'owner@example.test',
  businessName: 'Juniper Studio',
};

export const AUTH_STORAGE_KEY = 'cashflow_ai_user';
