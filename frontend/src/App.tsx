import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import { LoadingPage } from './components/common/LoadingPage'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { ApiHealthCheck } from './components/common/ApiHealthCheck'

// Lazy load all page components for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })))
const Login = lazy(() => import('./pages/Login').then(m => ({ default: m.Login })))
const AWSAccountsPage = lazy(() => import('./pages/AWSAccountsPage').then(m => ({ default: m.AWSAccountsPage })))
const BudgetManagement = lazy(() => import('./pages/BudgetManagement').then(m => ({ default: m.BudgetManagement })))
const FinOpsAudit = lazy(() => import('./pages/FinOpsAudit').then(m => ({ default: m.FinOpsAudit })))
const Automation = lazy(() => import('./pages/Automation').then(m => ({ default: m.Automation })))
const Analytics = lazy(() => import('./pages/Analytics').then(m => ({ default: m.Analytics })))
const KPIDashboard = lazy(() => import('./pages/KPIDashboard').then(m => ({ default: m.KPIDashboard })))
const UnitCosts = lazy(() => import('./pages/UnitCosts').then(m => ({ default: m.UnitCosts })))
const RightSizing = lazy(() => import('./pages/RightSizing').then(m => ({ default: m.RightSizing })))
const Settings = lazy(() => import('./pages/Settings'))

function App() {
  return (
    <ErrorBoundary>
      <ApiHealthCheck>
        <Suspense fallback={<LoadingPage message="Loading..." />}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/*"
              element={
                <Layout>
                  <Suspense fallback={<LoadingPage message="Loading page..." />}>
                    <Routes>
                      <Route path="/dashboard" element={<Dashboard />} />
                      <Route path="/aws-accounts" element={<AWSAccountsPage />} />
                      <Route path="/budgets" element={<BudgetManagement />} />
                      <Route path="/finops-audit" element={<FinOpsAudit />} />
                      <Route path="/automation" element={<Automation />} />
                      <Route path="/analytics" element={<Analytics />} />
                      <Route path="/kpi" element={<KPIDashboard />} />
                      <Route path="/unit-costs" element={<UnitCosts />} />
                      <Route path="/rightsizing" element={<RightSizing />} />
                      <Route path="/settings" element={<Settings />} />
                      <Route path="/" element={<Navigate to="/dashboard" replace />} />
                      <Route path="*" element={<Navigate to="/dashboard" replace />} />
                    </Routes>
                  </Suspense>
                </Layout>
              }
            />
          </Routes>
        </Suspense>
      </ApiHealthCheck>
    </ErrorBoundary>
  )
}

export default App
