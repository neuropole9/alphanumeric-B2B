import {createContext,useContext,useEffect,useMemo,useState,type ReactNode} from 'react'
import {api,post} from '../api/client'
import type {User} from '../types'

type AuthCtx={user:User|null;loading:boolean;login:(email:string,password:string)=>Promise<void>;logout:()=>Promise<void>;refresh:()=>Promise<void>}
const Ctx=createContext<AuthCtx|null>(null)
export function AuthProvider({children}:{children:ReactNode}){
  const [user,setUser]=useState<User|null>(null); const [loading,setLoading]=useState(true)
  const refresh=async()=>{try{const x=await api<{user:User}>('/api/v1/auth/me');setUser(x.user)}catch{setUser(null)}}
  useEffect(()=>{refresh().finally(()=>setLoading(false))},[])
  const login=async(email:string,password:string)=>{const x=await post<{user:User}>('/api/v1/auth/login',{email,password});setUser(x.user)}
  const logout=async()=>{try{await post('/api/v1/auth/logout')}finally{setUser(null)}}
  return <Ctx.Provider value={useMemo(()=>({user,loading,login,logout,refresh}),[user,loading])}>{children}</Ctx.Provider>
}
export function useAuth(){const c=useContext(Ctx);if(!c)throw new Error('AuthProvider missing');return c}
