import {lazy,Suspense} from 'react'
import type {ReactNode} from 'react'
import {Navigate,Route,Routes,useLocation,useParams} from 'react-router-dom'
import {useAuth} from './AuthContext'
import Layout from './Layout'
import LoginPage from '../pages/LoginPage'

const DashboardPage=lazy(()=>import('../pages/DashboardPage'))
const ProductsPage=lazy(()=>import('../pages/ProductsPage'))
const ProductDetailPage=lazy(()=>import('../pages/ProductDetailPage'))
const InquiriesPage=lazy(()=>import('../pages/InquiriesPage'))
const CreateInquiryPage=lazy(()=>import('../pages/CreateInquiryPage'))
const InquiryDetailPage=lazy(()=>import('../pages/InquiryDetailPage'))
const QuotationsPage=lazy(()=>import('../pages/QuotationsPage'))
const QuotationDetailPage=lazy(()=>import('../pages/QuotationDetailPage'))
const OrdersPage=lazy(()=>import('../pages/OrdersPage'))
const InvoicesPage=lazy(()=>import('../pages/InvoicesPage'))
const InvoiceDetailPage=lazy(()=>import('../pages/InvoiceDetailPage'))
const CustomersPage=lazy(()=>import('../pages/CustomersPage'))
const CustomerDetailPage=lazy(()=>import('../pages/CustomerDetailPage'))
const ProjectsPage=lazy(()=>import('../pages/ProjectsPage'))
const ProjectDetailPage=lazy(()=>import('../pages/ProjectDetailPage'))
const RoomDetailPage=lazy(()=>import('../pages/RoomDetailPage'))
const BuildingDetailPage=lazy(()=>import('../pages/BuildingDetailPage'))
const SettingsPage=lazy(()=>import('../pages/SettingsPage'))
const AuditPage=lazy(()=>import('../pages/AuditPage'))
const RequestProductsPage=lazy(()=>import('../pages/RequestProductsPage'))
const ApprovalsPage=lazy(()=>import('../pages/ApprovalsPage'))
const FloorDetailPage=lazy(()=>import('../pages/FloorDetailPage'))
const OrderDetailPage=lazy(()=>import('../pages/OrderDetailPage'))
const ProjectDocumentsPage=lazy(()=>import('../pages/ProjectDocumentsPage'))
const ChangePasswordPage=lazy(()=>import('../pages/ChangePasswordPage'))
const OperationsPage=lazy(()=>import('../pages/OperationsPage'))
const CommercialOperationsPage=lazy(()=>import('../pages/CommercialOperationsPage'))
const CataloguePage=lazy(()=>import('../pages/CataloguePage'))

function Protected(){const {user,loading}=useAuth();const location=useLocation();const {workspace='lighting'}=useParams();if(loading)return <div className="splash">AlphaNumeric</div>;if(!user)return <Navigate to="/login" replace/>;if(user.must_change_password&&!location.pathname.endsWith('/change-password'))return <Navigate to={`/app/${workspace}/change-password`} replace/>;return <Layout/>}
function AdminOnly({children}:{children:ReactNode}){const {user}=useAuth();const {workspace='lighting'}=useParams();return (user?.role==='ADMIN'||user?.role==='SUPER_ADMIN')?children:<Navigate to={`/app/${workspace}/projects`} replace/>}
const loading=<div className="loading">Loading workspace…</div>

export default function App(){
  const {user,loading:authLoading}=useAuth()
  return <Suspense fallback={loading}><Routes>
    <Route path="/login" element={<LoginPage/>}/>
    <Route path="/app/:workspace" element={<Protected/>}>
      <Route index element={<Navigate to="dashboard" replace/>}/>
      <Route path="dashboard" element={<DashboardPage/>}/>
      <Route path="products" element={<ProductsPage/>}/>
      <Route path="products/:id" element={<ProductDetailPage/>}/>
      <Route path="catalogue" element={<AdminOnly><CataloguePage/></AdminOnly>}/>
      <Route path="catalogue/categories" element={<AdminOnly><CataloguePage/></AdminOnly>}/>
      <Route path="catalogue/products" element={<AdminOnly><CataloguePage/></AdminOnly>}/>
      <Route path="catalogue/imports" element={<AdminOnly><CataloguePage/></AdminOnly>}/>
      <Route path="catalogue/builder" element={<AdminOnly><CataloguePage/></AdminOnly>}/>
      <Route path="catalogue/versions" element={<AdminOnly><CataloguePage/></AdminOnly>}/>
      <Route path="inquiries" element={<InquiriesPage/>}/>
      <Route path="inquiries/new" element={<AdminOnly><CreateInquiryPage/></AdminOnly>}/>
      <Route path="inquiries/:id/edit" element={<AdminOnly><CreateInquiryPage/></AdminOnly>}/>
      <Route path="inquiries/:id" element={<InquiryDetailPage/>}/>
      <Route path="quotations" element={<AdminOnly><QuotationsPage/></AdminOnly>}/>
      <Route path="quotations/:id" element={<QuotationDetailPage/>}/>
      <Route path="orders" element={<OrdersPage/>}/>
      <Route path="orders/:id" element={<OrderDetailPage/>}/>
      <Route path="invoices" element={<AdminOnly><InvoicesPage/></AdminOnly>}/>
      <Route path="invoices/:id" element={<InvoiceDetailPage/>}/>
      <Route path="customers" element={<AdminOnly><CustomersPage/></AdminOnly>}/>
      <Route path="customers/:id" element={<AdminOnly><CustomerDetailPage/></AdminOnly>}/>
      <Route path="customers/:customerId/projects/:id" element={<ProjectDetailPage/>}/>
      <Route path="customers/:customerId/projects/:id/buildings/:buildingId" element={<BuildingDetailPage/>}/>
      <Route path="customers/:customerId/projects/:id/buildings/:buildingId/documents" element={<ProjectDocumentsPage/>}/>
      <Route path="customers/:customerId/projects/:id/buildings/:buildingId/floors/:floorId" element={<FloorDetailPage/>}/>
      <Route path="customers/:customerId/projects/:id/buildings/:buildingId/floors/:floorId/rooms/:roomId" element={<RoomDetailPage/>}/>
      <Route path="projects" element={<ProjectsPage/>}/>
      <Route path="projects/:id" element={<ProjectDetailPage/>}/>
      <Route path="projects/:id/buildings/:buildingId" element={<BuildingDetailPage/>}/>
      <Route path="projects/:id/buildings/:buildingId/documents" element={<ProjectDocumentsPage/>}/>
      <Route path="projects/:id/documents" element={<ProjectDocumentsPage/>}/>
      <Route path="projects/:id/buildings/:buildingId/floors/:floorId" element={<FloorDetailPage/>}/>
      <Route path="projects/:id/rooms/:roomId" element={<RoomDetailPage/>}/>
      <Route path="change-password" element={<ChangePasswordPage/>}/>
      <Route path="settings" element={<AdminOnly><SettingsPage/></AdminOnly>}/>
      <Route path="audit" element={<AdminOnly><AuditPage/></AdminOnly>}/>
      <Route path="requests/new" element={<RequestProductsPage/>}/>
      <Route path="approvals" element={<ApprovalsPage/>}/>
      <Route path="operations" element={<OperationsPage/>}/>
      <Route path="commercial-control" element={<AdminOnly><CommercialOperationsPage/></AdminOnly>}/>
    </Route>
    <Route path="*" element={authLoading?<div/>:<Navigate to={user?`/app/${(user.workspaces[0]||'LIGHTING').toLowerCase()}/${(user.role==='ADMIN'||user.role==='SUPER_ADMIN')?'dashboard':'projects'}`:'/login'} replace/>}/>
  </Routes></Suspense>
}
