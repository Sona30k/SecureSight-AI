import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { services, tokenStore, User } from './lib/api'

type AuthState={user:User|null;loading:boolean;login:(email:string,password:string)=>Promise<User>;logout:()=>Promise<void>}
const AuthContext=createContext<AuthState|null>(null)

export function AuthProvider({children}:{children:React.ReactNode}){
  const [user,setUser]=useState<User|null>(null)
  const [loading,setLoading]=useState(Boolean(tokenStore.get()))
  useEffect(()=>{
    const restore=async()=>{if(!tokenStore.get()){setLoading(false);return}try{setUser(await services.auth.me())}catch{tokenStore.clear()}finally{setLoading(false)}}
    void restore()
    const clear=()=>setUser(null)
    window.addEventListener('shieldiq:logout',clear)
    return()=>window.removeEventListener('shieldiq:logout',clear)
  },[])
  const login=async(email:string,password:string)=>{await services.auth.login(email,password);const current=await services.auth.me();setUser(current);return current}
  const logout=async()=>{await services.auth.logout();setUser(null)}
  return <AuthContext.Provider value={{user,loading,login,logout}}>{children}</AuthContext.Provider>
}

export const useAuth=()=>{const value=useContext(AuthContext);if(!value)throw new Error('AuthProvider missing');return value}

export function Protected({children,roles}:{children:React.ReactNode;roles?:User['role'][]}){
  const {user,loading}=useAuth();const location=useLocation()
  if(loading)return <div className="app-loader"><span/><p>Establishing secure session…</p></div>
  if(!user)return <Navigate to="/login" replace state={{from:location.pathname}}/>
  if(roles&&!roles.includes(user.role))return <Navigate to="/dashboard" replace/>
  return <>{children}</>
}
