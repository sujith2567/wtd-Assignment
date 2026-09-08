import { useState } from 'react'
import { Link, Navigate, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { AuthProvider, apiRequest, useAuth } from './api.jsx'
import './assets/design-tokens.css';
import './assets/fonts.css';
import {
  AdminOverviewPage,
  AdminStudentsPage,
  AdminStudentDetailPage,
  AdminJobsPage,
  AdminInterviewsPage,
  AdminSectionsPage,
  AdminSectionDetailPage,
  AdminFairnessPage,
} from './admin.jsx'

import {
  RecruiterJobsPage,
  PostJobPage,
  CandidateShortlistPage,
  RecruiterSectionsPage,
  RecruiterSectionDetailPage,
} from './recruiter.jsx'

import {
  StudentProfilePage,
  StudentRecommendationsPage,
  StudentInterviewsPage,
  StudentAlumniPage,
  StudentReadinessPage,
  StudentApplicationsPage,
} from './student.jsx'

// ----- route guards --------------------------------------------------------

function ProtectedRoute({ allowedRole, children }) {
  const { auth } = useAuth()
  const location = useLocation()
  if (!auth?.token || !auth?.user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (auth.user.role !== allowedRole) return <Navigate to={`/${auth.user.role}`} replace />
  return children
}

function DashboardLayout() {
  const { auth, logout } = useAuth()
  const navigate = useNavigate()
  function handleLogout() { logout(); navigate('/login', { replace: true }) }
  return (
    <div className="app-shell">
      <header className="top-nav">
        <span className="shell-brand">PlaceMatch AI</span>
        <div className="user-controls">
          <span>Signed in as <strong>{auth.user.fullName}</strong> ({auth.user.role})</span>
          <button className="logout-button" onClick={handleLogout}>Log out</button>
        </div>
      </header>
      <main className="dashboard-main">
        <Outlet />
      </main>
    </div>
  )
}

// ----- auth pages ----------------------------------------------------------

function AuthPage({ children }) {
  return <div className="auth-page"><section className="auth-card">{children}</section></div>
}

function LoginPage() {
  const { auth, saveAuth } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [selectedRole, setSelectedRole] = useState('student')
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  if (auth?.user) return <Navigate to={`/${auth.user.role}`} replace />

  async function handleSubmit(event) {
    event.preventDefault(); setError(''); setIsSubmitting(true)
    try {
      const data = await apiRequest('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ ...form, role: selectedRole }) })
      saveAuth(data)
      navigate(location.state?.from || `/${data.role}`, { replace: true })
    } catch (requestError) { setError(requestError.message) } finally { setIsSubmitting(false) }
  }

  const roleConfigs = {
    student: { title: 'Student Portal', label: 'Roll No / Email address', placeholder: 'student@placematch.edu' },
    recruiter: { title: 'Recruiter Portal', label: 'Work Email address', placeholder: 'recruiter@google.com' },
    admin: { title: 'College Admin Portal', label: 'Institutional Email address', placeholder: 'admin@placematch.edu' }
  }

  const currentConfig = roleConfigs[selectedRole]

  return (
    <AuthPage>
      <p className="brand">PlaceMatch AI</p>
      <h1>Welcome back</h1>
      <p className="muted">Select your portal role to sign in:</p>

      <div className="role-selector">
        <button
          type="button"
          className={`role-tile ${selectedRole === 'student' ? 'is-selected' : ''}`}
          onClick={() => setSelectedRole('student')}
        >
          <span className="role-icon">🎓</span> Student
        </button>
        <button
          type="button"
          className={`role-tile ${selectedRole === 'recruiter' ? 'is-selected' : ''}`}
          onClick={() => setSelectedRole('recruiter')}
        >
          <span className="role-icon">🏢</span> Recruiter
        </button>
        <button
          type="button"
          className={`role-tile ${selectedRole === 'admin' ? 'is-selected' : ''}`}
          onClick={() => setSelectedRole('admin')}
        >
          <span className="role-icon">🏛️</span> Admin
        </button>
      </div>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label className="field">
          {currentConfig.label}
          <input
            type="email"
            required
            placeholder={currentConfig.placeholder}
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </label>
        <label className="field">
          Password
          <input
            type="password"
            required
            placeholder="••••••••"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </label>
        {error && <p className="error-message" role="alert">{error}</p>}
        <button className="primary-button" disabled={isSubmitting}>
          {isSubmitting ? 'Signing in...' : `Sign in as ${selectedRole === 'student' ? 'Student' : selectedRole === 'recruiter' ? 'Recruiter' : 'Admin'}`}
        </button>
      </form>
      <p className="auth-switch">New here? <Link to="/register">Create an account</Link></p>
    </AuthPage>
  )
}

function RegisterPage() {
  const navigate = useNavigate()
  const [selectedRole, setSelectedRole] = useState('student')
  const [form, setForm] = useState({ full_name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault(); setError(''); setIsSubmitting(true)
    try {
      await apiRequest('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify({ ...form, role: selectedRole })
      })
      navigate('/login', { replace: true })
    } catch (requestError) { setError(requestError.message) } finally { setIsSubmitting(false) }
  }

  const roleConfigs = {
    student: { emailLabel: 'Student Email / Roll No', emailPlaceholder: 'student@placematch.edu', nameLabel: 'Full Student Name' },
    recruiter: { emailLabel: 'Work Email address', emailPlaceholder: 'recruiter@company.com', nameLabel: 'Full Name (Recruiter)' },
    admin: { emailLabel: 'Institutional Email address', emailPlaceholder: 'admin@placematch.edu', nameLabel: 'Administrator Name' }
  }

  const currentConfig = roleConfigs[selectedRole]

  return (
    <AuthPage>
      <p className="brand">PlaceMatch AI</p>
      <h1>Create an account</h1>
      <p className="muted">First, select your account category:</p>

      <div className="role-selector">
        <button
          type="button"
          className={`role-tile ${selectedRole === 'student' ? 'is-selected' : ''}`}
          onClick={() => setSelectedRole('student')}
        >
          <span className="role-icon">🎓</span> Student
        </button>
        <button
          type="button"
          className={`role-tile ${selectedRole === 'recruiter' ? 'is-selected' : ''}`}
          onClick={() => setSelectedRole('recruiter')}
        >
          <span className="role-icon">🏢</span> Recruiter
        </button>
        <button
          type="button"
          className={`role-tile ${selectedRole === 'admin' ? 'is-selected' : ''}`}
          onClick={() => setSelectedRole('admin')}
        >
          <span className="role-icon">🏛️</span> Admin
        </button>
      </div>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label className="field">
          {currentConfig.nameLabel}
          <input
            required
            placeholder="e.g. Alex Sharma"
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
        </label>
        <label className="field">
          {currentConfig.emailLabel}
          <input
            type="email"
            required
            placeholder={currentConfig.emailPlaceholder}
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </label>
        <label className="field">
          Password
          <input
            type="password"
            minLength="6"
            required
            placeholder="At least 6 characters"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </label>
        {error && <p className="error-message" role="alert">{error}</p>}
        <button className="primary-button" disabled={isSubmitting}>
          {isSubmitting ? 'Creating account...' : `Register as ${selectedRole === 'student' ? 'Student' : selectedRole === 'recruiter' ? 'Recruiter' : 'Admin'}`}
        </button>
      </form>
      <p className="auth-switch">Already registered? <Link to="/login">Sign in</Link></p>
    </AuthPage>
  )
}

// ----- redirects and placeholders ------------------------------------------

function AdminHomeRedirect() {
  return <Navigate to="/admin/overview" replace />
}

function RecruiterHomeRedirect() {
  return <Navigate to="/recruiter/jobs" replace />
}

function StudentHomeRedirect() {
  return <Navigate to="/student/profile" replace />
}



// ----- root component ------------------------------------------------------

export default function App() {
  return <AuthProvider><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />

    <Route element={<ProtectedRoute allowedRole="admin"><DashboardLayout /></ProtectedRoute>}>
      <Route path="/admin" element={<AdminHomeRedirect />} />
      <Route path="/admin/overview" element={<AdminOverviewPage />} />
      <Route path="/admin/students" element={<AdminStudentsPage />} />
      <Route path="/admin/students/:studentId" element={<AdminStudentDetailPage />} />
      <Route path="/admin/sections" element={<AdminSectionsPage />} />
      <Route path="/admin/sections/:sectionId" element={<AdminSectionDetailPage />} />
      <Route path="/admin/jobs" element={<AdminJobsPage />} />
      <Route path="/admin/interviews" element={<AdminInterviewsPage />} />
      <Route path="/admin/fairness" element={<AdminFairnessPage />} />
    </Route>

    <Route element={<ProtectedRoute allowedRole="recruiter"><DashboardLayout /></ProtectedRoute>}>
      <Route path="/recruiter" element={<RecruiterHomeRedirect />} />
      <Route path="/recruiter/jobs" element={<RecruiterJobsPage />} />
      <Route path="/recruiter/sections" element={<RecruiterSectionsPage />} />
      <Route path="/recruiter/sections/:sectionId" element={<RecruiterSectionDetailPage />} />
      <Route path="/recruiter/post-job" element={<PostJobPage />} />
      <Route path="/recruiter/jobs/:jobId/shortlist" element={<CandidateShortlistPage />} />
    </Route>


    <Route element={<ProtectedRoute allowedRole="student"><DashboardLayout /></ProtectedRoute>}>
      <Route path="/student" element={<StudentHomeRedirect />} />
      <Route path="/student/profile" element={<StudentProfilePage />} />
      <Route path="/student/recommendations" element={<StudentRecommendationsPage />} />
      <Route path="/student/interviews" element={<StudentInterviewsPage />} />
      <Route path="/student/alumni" element={<StudentAlumniPage />} />
      <Route path="/student/readiness" element={<StudentReadinessPage />} />
      <Route path="/student/applications" element={<StudentApplicationsPage />} />
    </Route>

    <Route path="/" element={<Navigate to="/login" replace />} />
    <Route path="*" element={<Navigate to="/login" replace />} />
  </Routes></AuthProvider>
}
