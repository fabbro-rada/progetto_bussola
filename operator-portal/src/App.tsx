import { Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { AppShell } from './shell/AppShell'
import { Login } from './screens/Login'
import { ChangePassword } from './screens/ChangePassword'
import { Home } from './screens/Home'
import { Unauthorized } from './screens/Unauthorized'
import { JobRequestList } from './screens/jobRequests/JobRequestList'
import { JobRequestCreate } from './screens/jobRequests/JobRequestCreate'
import { JobRequestDetail } from './screens/jobRequests/JobRequestDetail'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/change-password"
        element={
          <ProtectedRoute allowMustChange>
            <ChangePassword />
          </ProtectedRoute>
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Home />} />
        <Route path="unauthorized" element={<Unauthorized />} />
        <Route path="job-requests" element={<JobRequestList />} />
        <Route path="job-requests/new" element={<JobRequestCreate />} />
        <Route path="job-requests/:id" element={<JobRequestDetail />} />
        {/* later sub-projects add nested section routes here */}
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
