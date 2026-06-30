import { DependencyList, useCallback, useEffect, useState } from 'react'
import { errorMessage } from '../lib/api'

export function useApi<T>(loader:()=>Promise<T>, deps:DependencyList=[]){
  const [data,setData]=useState<T|null>(null)
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const load=useCallback(async()=>{
    setLoading(true);setError('')
    try{setData(await loader())}catch(err){setError(errorMessage(err))}
    finally{setLoading(false)}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },deps)
  useEffect(()=>{void load()},[load])
  return {data,loading,error,retry:load,setData}
}
