import { useState, useEffect, type ReactNode } from 'react';
import { AuthContext, AUTH_STORAGE_KEY, DEMO_USER, type User } from './auth-context';
import { apiClient, getSession } from '../api/client';
export function AuthProvider({children}:{children:ReactNode}) {
  const [user,setUser]=useState<User|null>(null);
  const [loading,setLoading]=useState(true);
  const [serverAuthenticated,setServerAuthenticated]=useState(false);
  useEffect(()=>{let active=true; try {localStorage.removeItem(AUTH_STORAGE_KEY);} catch {/* Browser storage is not required for authorization. */}
    getSession().then(s=>{if(active){setServerAuthenticated(s.authenticated);setUser(s.authenticated||s.read_only_demo?DEMO_USER:null);}}).catch(()=>{if(active)setUser(null);}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[]);
  const login=async(_email:string,password:string)=>{
    await apiClient('/api/v1/session',{method:'POST',body:JSON.stringify({password})});
    const s=await getSession();
    if(!s.authenticated)throw new Error('Sign-in was not confirmed by the server.');
    setUser(DEMO_USER);setServerAuthenticated(true);
  };
  const demoLogin=async()=>{const s=await getSession();if(!s.read_only_demo&&!s.authenticated)throw new Error('This workspace requires administrator sign-in.');setUser(DEMO_USER);setServerAuthenticated(s.authenticated);};
  const logout=async()=>{if(serverAuthenticated)await apiClient('/api/v1/session',{method:'DELETE'});setUser(null);setServerAuthenticated(false);};
  return <AuthContext.Provider value={{user,isAuthenticated:!!user,serverAuthenticated,loading,login,logout,demoLogin}}>{children}</AuthContext.Provider>;
}
