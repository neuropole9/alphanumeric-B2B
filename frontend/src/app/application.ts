import type {Product,Workspace} from '../types'

export const applicationPath=(workspace:Workspace,isInternal:boolean)=>`/app/${workspace.toLowerCase()}/${isInternal?'dashboard':'projects'}`
export const productsForApplication=(products:Product[],workspace:Workspace)=>products.filter(product=>product.workspace===workspace)
export const reportUrl=(path:string,workspace:Workspace,download=false)=>`${path}${path.includes('?')?'&':'?'}workspace=${workspace}${download?'&download=true':''}`
export const shouldDiscardApplicationState=(current:Workspace,next:Workspace)=>current!==next
