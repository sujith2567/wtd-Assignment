import { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, useParams } from 'react-router-dom'
import { apiRequest, useAuth } from './api.jsx'

// ----- helpers --------------------------------------------------------------

import { StatCard, LoadingBlock, ErrorBlock, EmptyState, formatPercent, formatCgpa } from './components.jsx';

// ----- admin shell with sub-tabs -------------------------------------------

export function AdminDashboard() {
  return (
    <div className="admin-shell">
      <AdminSubNav />
      <div className="admin-subpage">
        {/* Nested route renders here via <Outlet /> in App.jsx */}
      </div>
    </div>
  )
}

function AdminSubNav() {
  const tabs = [
    { to: '/admin/overview', label: 'Overview' },
    { to: '/admin/students', label: 'Students' },
    { to: '/admin/sections', label: '📂 Sections' },
    { to: '/admin/jobs', label: 'Jobs' },
    { to: '/admin/interviews', label: 'Interview Outcomes' },
    { to: '/admin/fairness', label: '⚖️ Fairness Audit' },
  ]
  return (
    <nav className="admin-tabs" aria-label="Admin sections">
      {tabs.map((tab) => (
        <NavLink key={tab.to} to={tab.to} className={({ isActive }) => `admin-tab${isActive ? ' is-active' : ''}`}>
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}

// ----- overview page -------------------------------------------------------

export function AdminOverviewPage() {
  const { auth } = useAuth()
  const [students, setStudents] = useState(null)
  const [jobs, setJobs] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setError('')
      try {
        const [studentList, jobList] = await Promise.all([
          apiRequest('/api/v1/students/?limit=200', { headers: { Authorization: `Bearer ${auth.token}` } }),
          apiRequest('/api/v1/jobs/?limit=100', { headers: { Authorization: `Bearer ${auth.token}` } }),
        ])
        if (cancelled) return
        setStudents(studentList)
        setJobs(jobList)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load overview data.')
      }
    }
    load()
    return () => { cancelled = true }
  }, [auth.token])

  const stats = useMemo(() => {
    const totalStudents = Array.isArray(students) ? students.length : null
    const totalJobs = Array.isArray(jobs) ? jobs.length : null
    const domains = new Set()
    const studentsWithPrediction = []
    if (Array.isArray(students)) {
      for (const s of students) {
        if (s.predicted_domain) {
          domains.add(s.predicted_domain)
          studentsWithPrediction.push(s)
        }
      }
    }
    return {
      totalStudents,
      totalJobs,
      uniqueDomains: domains.size,
      studentsWithPrediction: studentsWithPrediction.length,
    }
  }, [students, jobs])

  return (
    <>
      <AdminSubNav />
      <header className="dashboard-header">
        <p className="eyebrow">Admin overview</p>
        <h1>Pipeline at a glance</h1>
        <p className="muted">Live numbers pulled from the FastAPI backend.</p>
      </header>

      {error && <ErrorBlock message={error} />}

      <section className="stat-grid">
        <StatCard
          label="Total students"
          value={stats.totalStudents == null ? '…' : stats.totalStudents}
          hint="Across all departments"
        />
        <StatCard
          label="Total job postings"
          value={stats.totalJobs == null ? '…' : stats.totalJobs}
          hint="Active listings"
        />
        <StatCard
          label="Students with AI domain prediction"
          value={stats.studentsWithPrediction == null ? '…' : stats.studentsWithPrediction}
          hint="Model has classified"
        />
        <StatCard
          label="Unique predicted domains"
          value={stats.uniqueDomains == null ? '…' : stats.uniqueDomains}
          hint="Distinct AI labels"
        />
      </section>

      <p className="muted footnote">
        Total matches made is not exposed by a dedicated endpoint yet — counted
        on each candidate evaluation, so it's intentionally omitted here.
      </p>
    </>
  )
}

// ----- students list -------------------------------------------------------

// ----- Modals for Phase 2 ---------------------------------------------------

function UploadResumeModal({ onClose, onSuccess }) {
  const { auth } = useAuth()
  const [form, setForm] = useState({
    email: '',
    full_name: '',
    roll_number: '',
    department: 'Computer Science',
    cgpa: '7.5',
    active_backlogs: '0',
    skills_csv: '',
    raw_text: ''
  })
  const [file, setFile] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')

    try {
      const formData = new FormData()
      if (file) formData.append('file', file)
      
      const params = new URLSearchParams({
        email: form.email,
        full_name: form.full_name,
        roll_number: form.roll_number,
        department: form.department,
        cgpa: form.cgpa,
        active_backlogs: form.active_backlogs,
        skills_csv: form.skills_csv,
        raw_text: form.raw_text
      })

      const baseUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
      const res = await fetch(`${baseUrl}/api/v1/students/upload-resume?${params.toString()}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${auth.token}` },
        body: formData
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to upload resume')
      onSuccess()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <div className="modal-header">
          <h2>📂 Upload New Student Resume</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="edit-form-grid">
            <label className="field">
              Full Name *
              <input required value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} placeholder="e.g. Rahul Verma" />
            </label>
            <label className="field">
              Email *
              <input type="email" required value={form.email} onChange={e => setForm({...form, email: e.target.value})} placeholder="rahul@placematch.edu" />
            </label>
            <label className="field">
              Roll Number *
              <input required value={form.roll_number} onChange={e => setForm({...form, roll_number: e.target.value})} placeholder="21CSE088" />
            </label>
            <label className="field">
              Department
              <input value={form.department} onChange={e => setForm({...form, department: e.target.value})} />
            </label>
            <label className="field">
              CGPA
              <input type="number" step="0.01" min="0" max="10" value={form.cgpa} onChange={e => setForm({...form, cgpa: e.target.value})} />
            </label>
            <label className="field">
              Active Backlogs
              <input type="number" min="0" value={form.active_backlogs} onChange={e => setForm({...form, active_backlogs: e.target.value})} />
            </label>
            <label className="field full-width">
              Skills (comma separated)
              <input value={form.skills_csv} onChange={e => setForm({...form, skills_csv: e.target.value})} placeholder="Python, React, Machine Learning, SQL" />
            </label>
            <label className="field full-width">
              Upload Resume File (.txt, .pdf, etc.)
              <input type="file" onChange={e => setFile(e.target.files[0])} />
            </label>
            <label className="field full-width">
              Or Paste Raw Resume Text
              <textarea rows="4" style={{width:'100%', padding:'10px', borderRadius:'8px', border:'1px solid #cbd6e6'}} value={form.raw_text} onChange={e => setForm({...form, raw_text: e.target.value})} placeholder="Paste extracted resume text here..." />
            </label>
          </div>
          {error && <p className="error-message">{error}</p>}
          <div style={{display:'flex', gap:'12px', marginTop:'16px', justifyContent:'flex-end'}}>
            <button type="button" className="logout-button" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary-button" disabled={submitting}>{submitting ? 'Uploading...' : 'Save & Classify'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

function EditStudentModal({ student, onClose, onSuccess }) {
  const { auth } = useAuth()
  const [form, setForm] = useState({
    full_name: student.full_name || '',
    roll_number: student.roll_number || '',
    department: student.department || '',
    batch_year: student.batch_year || 2025,
    cgpa: student.cgpa || '',
    active_backlogs: student.active_backlogs ?? 0,
    skills: Array.isArray(student.skills) ? student.skills.join(', ') : '',
    raw_resume_text: student.raw_resume_text || '',
    predicted_domain: student.predicted_domain || ''
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')

    const payload = {
      full_name: form.full_name,
      roll_number: form.roll_number,
      department: form.department,
      batch_year: Number(form.batch_year),
      cgpa: Number(form.cgpa),
      active_backlogs: Number(form.active_backlogs),
      skills: form.skills.split(',').map(s => s.trim()).filter(Boolean),
      raw_resume_text: form.raw_resume_text,
      predicted_domain: form.predicted_domain
    }

    try {
      await apiRequest(`/api/v1/students/${student.id}`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${auth.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      })
      onSuccess()
    } catch (err) {
      setError(err.message || 'Failed to update student')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <div className="modal-header">
          <h2>✏️ Edit Student Record #{student.id}</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="edit-form-grid">
            <label className="field">
              Full Name
              <input required value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} />
            </label>
            <label className="field">
              Roll Number
              <input required value={form.roll_number} onChange={e => setForm({...form, roll_number: e.target.value})} />
            </label>
            <label className="field">
              Department
              <input required value={form.department} onChange={e => setForm({...form, department: e.target.value})} />
            </label>
            <label className="field">
              Batch Year
              <input type="number" required value={form.batch_year} onChange={e => setForm({...form, batch_year: e.target.value})} />
            </label>
            <label className="field">
              CGPA
              <input type="number" step="0.01" min="0" max="10" required value={form.cgpa} onChange={e => setForm({...form, cgpa: e.target.value})} />
            </label>
            <label className="field">
              Active Backlogs
              <input type="number" min="0" required value={form.active_backlogs} onChange={e => setForm({...form, active_backlogs: e.target.value})} />
            </label>
            <label className="field full-width">
              Predicted Domain Tag
              <input value={form.predicted_domain} onChange={e => setForm({...form, predicted_domain: e.target.value})} />
            </label>
            <label className="field full-width">
              Skills (comma separated)
              <input value={form.skills} onChange={e => setForm({...form, skills: e.target.value})} />
            </label>
            <label className="field full-width">
              Raw Resume Text
              <textarea rows="4" style={{width:'100%', padding:'10px', borderRadius:'8px', border:'1px solid #cbd6e6'}} value={form.raw_resume_text} onChange={e => setForm({...form, raw_resume_text: e.target.value})} />
            </label>
          </div>
          {error && <p className="error-message">{error}</p>}
          <div style={{display:'flex', gap:'12px', marginTop:'16px', justifyContent:'flex-end'}}>
            <button type="button" className="logout-button" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary-button" disabled={submitting}>{submitting ? 'Saving...' : 'Save Changes'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ----- students list -------------------------------------------------------

export function AdminStudentsPage() {
  const { auth } = useAuth()
  const [students, setStudents] = useState(null)
  const [search, setSearch] = useState('')
  const [domain, setDomain] = useState('')
  const [error, setError] = useState('')
  
  // Modals state
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [editingStudent, setEditingStudent] = useState(null)

  // Sorting state
  const [sortField, setSortField] = useState('full_name')
  const [sortAsc, setSortAsc] = useState(true)

  async function load(querySearch = search, queryDomain = domain) {
    setError('')
    try {
      const params = new URLSearchParams()
      params.set('limit', '200')
      if (querySearch.trim()) params.set('search', querySearch.trim())
      if (queryDomain.trim()) params.set('domain', queryDomain.trim())
      const data = await apiRequest(`/api/v1/students/?${params.toString()}`, {
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      setStudents(data)
    } catch (err) {
      setError(err.message || 'Failed to load students.')
    }
  }

  useEffect(() => { load('', '') }, [auth.token]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit(event) {
    event.preventDefault()
    load(search, domain)
  }

  function handleReset() {
    setSearch(''); setDomain(''); load('', '')
  }

  function toggleSort(field) {
    if (sortField === field) {
      setSortAsc(!sortAsc)
    } else {
      setSortField(field)
      setSortAsc(true)
    }
  }

  const sortedStudents = useMemo(() => {
    if (!students) return []
    return [...students].sort((a, b) => {
      let valA = a[sortField] ?? ''
      let valB = b[sortField] ?? ''
      if (sortField === 'full_name') {
        valA = a.full_name || ''
        valB = b.full_name || ''
      }
      if (typeof valA === 'number') {
        return sortAsc ? valA - valB : valB - valA
      }
      return sortAsc
        ? String(valA).localeCompare(String(valB))
        : String(valB).localeCompare(String(valA))
    })
  }, [students, sortField, sortAsc])

  return (
    <>
      <AdminSubNav />
      <header className="dashboard-header" style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start'}}>
        <div>
          <p className="eyebrow">Students</p>
          <h1>All registered students</h1>
          <p className="muted">Search by name or roll number, filter by predicted domain, and manage records.</p>
        </div>
        <button className="primary-button" style={{padding:'10px 18px'}} onClick={() => setShowUploadModal(true)}>
          📄 Upload Resume
        </button>
      </header>

      <form className="filter-row" onSubmit={handleSubmit}>
        <label className="field filter-field">
          <span>Search (name / roll / email)</span>
          <input
            type="search"
            value={search}
            placeholder="e.g. Aisha or 21CSE045"
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="field filter-field">
          <span>Predicted domain</span>
          <input
            type="search"
            value={domain}
            placeholder="e.g. Machine Learning"
            onChange={(e) => setDomain(e.target.value)}
          />
        </label>
        <div className="filter-actions">
          <button className="primary-button" type="submit">Apply</button>
          <button className="logout-button" type="button" onClick={handleReset}>Reset</button>
        </div>
      </form>

      {error && <ErrorBlock message={error} onRetry={() => load()} />}

      {students == null ? (
        <LoadingBlock />
      ) : students.length === 0 ? (
        <EmptyState message="No students match your filters." />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th className="sortable-th" onClick={() => toggleSort('roll_number')}>
                  Roll # {sortField === 'roll_number' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th className="sortable-th" onClick={() => toggleSort('full_name')}>
                  Name {sortField === 'full_name' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th className="sortable-th" onClick={() => toggleSort('department')}>
                  Department {sortField === 'department' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th className="sortable-th" onClick={() => toggleSort('cgpa')}>
                  CGPA {sortField === 'cgpa' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th>Ground truth</th>
                <th className="sortable-th" onClick={() => toggleSort('predicted_domain')}>
                  Predicted domain {sortField === 'predicted_domain' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th className="sortable-th" onClick={() => toggleSort('domain_confidence')}>
                  Confidence {sortField === 'domain_confidence' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th aria-label="actions">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sortedStudents.map((s) => (
                <tr key={s.id}>
                  <td><span className="mono">{s.roll_number}</span></td>
                  <td><strong>{s.full_name || '—'}</strong></td>
                  <td>{s.department}</td>
                  <td>{formatCgpa(s.cgpa)}</td>
                  <td>{s.domain_label || <span className="muted">—</span>}</td>
                  <td>{s.predicted_domain || <span className="muted">Not yet predicted</span>}</td>
                  <td>{formatPercent(s.domain_confidence)}</td>
                  <td style={{display:'flex', gap:'6px'}}>
                    <Link className="link-button" to={`/admin/students/${s.id}`}>View</Link>
                    <button className="link-button" style={{border:'none', cursor:'pointer'}} onClick={() => setEditingStudent(s)}>Edit</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted footnote">Showing {students.length} student{students.length === 1 ? '' : 's'} (click column headers to sort).</p>
        </div>
      )}

      {showUploadModal && (
        <UploadResumeModal
          onClose={() => setShowUploadModal(false)}
          onSuccess={() => { setShowUploadModal(false); load() }}
        />
      )}

      {editingStudent && (
        <EditStudentModal
          student={editingStudent}
          onClose={() => setEditingStudent(null)}
          onSuccess={() => { setEditingStudent(null); load() }}
        />
      )}
    </>
  )
}

// ----- student detail + explainability -------------------------------------

export function AdminStudentDetailPage() {
  const { auth } = useAuth()
  const { studentId } = useParams()
  const id = Number(studentId)

  const [student, setStudent] = useState(null)
  const [explanation, setExplanation] = useState(null)
  const [shapData, setShapData] = useState(null)
  const [anomalyData, setAnomalyData] = useState(null)

  const [loadingStudent, setLoadingStudent] = useState(true)
  const [loadingExplanation, setLoadingExplanation] = useState(true)
  const [studentError, setStudentError] = useState('')
  const [explanationError, setExplanationError] = useState('')
  const [editingStudent, setEditingStudent] = useState(null)

  async function refreshData() {
    setLoadingStudent(true)
    try {
      const data = await apiRequest(`/api/v1/students/${id}`, {
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      setStudent(data)
    } catch (err) {
      setStudentError(err.message || 'Failed to refresh student.')
    } finally {
      setLoadingStudent(false)
    }
  }

  useEffect(() => {
    if (!Number.isFinite(id)) return
    let cancelled = false
    async function loadStudent() {
      setLoadingStudent(true); setStudentError('')
      try {
        const data = await apiRequest(`/api/v1/students/${id}`, {
          headers: { Authorization: `Bearer ${auth.token}` },
        })
        if (!cancelled) setStudent(data)
      } catch (err) {
        if (!cancelled) setStudentError(err.message || 'Failed to load student.')
      } finally {
        if (!cancelled) setLoadingStudent(false)
      }
    }
    async function loadExplanation() {
      setLoadingExplanation(true); setExplanationError('')
      try {
        const [explRes, shapRes, anomalyRes] = await Promise.allSettled([
          apiRequest(`/api/v1/matching/student/${id}/explanation`, { headers: { Authorization: `Bearer ${auth.token}` } }),
          apiRequest(`/api/v1/explain/shap-compare/${id}`, { headers: { Authorization: `Bearer ${auth.token}` } }),
          apiRequest(`/api/v1/audit/anomaly-score/${id}`, { headers: { Authorization: `Bearer ${auth.token}` } })
        ])

        if (!cancelled) {
          if (explRes.status === 'fulfilled') setExplanation(explRes.value)
          if (shapRes.status === 'fulfilled') setShapData(shapRes.value.shap_analysis)
          if (anomalyRes.status === 'fulfilled') setAnomalyData(anomalyRes.value.anomaly_audit)
        }
      } catch (err) {
        if (!cancelled) setExplanationError(err.message || 'Failed to load explanation.')
      } finally {
        if (!cancelled) setLoadingExplanation(false)
      }
    }
    loadStudent(); loadExplanation()
    return () => { cancelled = true }
  }, [auth.token, id])

  if (!Number.isFinite(id)) {
    return <ErrorBlock message="Invalid student id." />
  }

  return (
    <>
      <AdminSubNav />
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
        <Link to="/admin/students" className="back-link">← Back to all students</Link>
        {student && (
          <button className="primary-button" style={{padding:'8px 16px', fontSize:'.85rem'}} onClick={() => setEditingStudent(student)}>
            ✏️ Edit Student Record
          </button>
        )}
      </div>
      <header className="dashboard-header">
        <p className="eyebrow">Student detail</p>
        <h1>{student?.full_name ? `${student.full_name} (${student.roll_number})` : `Student #${id}`}</h1>
      </header>

      {studentError && <ErrorBlock message={studentError} />}
      {loadingStudent ? (
        <LoadingBlock label="Loading... student profile…" />
      ) : student ? (
        <section className="detail-grid">
          <article className="detail-card">
            <p className="stat-label">Roll number</p>
            <p className="stat-value mono">{student.roll_number}</p>
          </article>
          <article className="detail-card">
            <p className="stat-label">Department</p>
            <p className="stat-value">{student.department}</p>
          </article>
          <article className="detail-card">
            <p className="stat-label">CGPA</p>
            <p className="stat-value">{formatCgpa(student.cgpa)}</p>
          </article>
          <article className="detail-card">
            <p className="stat-label">Batch</p>
            <p className="stat-value">{student.batch_year}</p>
          </article>
          <article className="detail-card">
            <p className="stat-label">Active backlogs</p>
            <p className="stat-value">{student.active_backlogs}</p>
          </article>
          <article className="detail-card">
            <p className="stat-label">Ground-truth domain</p>
            <p className="stat-value">{student.domain_label || '—'}</p>
          </article>
        </section>
      ) : null}

      <section className="explainability-card">
        <h2>AI explainability</h2>
        <p className="muted">
          Why the classifier predicted this student's domain — the project's
          key novelty feature.
        </p>

        {explanationError && <ErrorBlock message={explanationError} />}

        {loadingExplanation ? (
          <LoadingBlock label="Running explainability…" />
        ) : explanation ? (
          <>
            <div className="explanation-headline">
              <div>
                <p className="stat-label">Predicted domain</p>
                <p className="stat-value">{explanation.predicted_domain}</p>
              </div>
              <div>
                <p className="stat-label">Confidence</p>
                <p className="stat-value">{formatPercent(explanation.confidence_score)}</p>
              </div>
              <div>
                <p className="stat-label">Ground truth</p>
                <p className="stat-value">
                  {explanation.ground_truth_domain || '—'}
                  {explanation.is_correct === true && <span className="badge badge-good"> match</span>}
                  {explanation.is_correct === false && <span className="badge badge-bad"> mismatch</span>}
                </p>
              </div>
              <div>
                <p className="stat-label">Model version</p>
                <p className="stat-value mono">{explanation.model_version}</p>
              </div>
            </div>

            <p className="summary-text">{explanation.human_readable_summary}</p>

            <h3>Class probabilities</h3>
            <ul className="prob-list">
              {explanation.class_probabilities.map((c) => (
                <li key={c.domain}>
                  <span>{c.domain}</span>
                  <span className="prob-bar-wrap">
                    <span
                      className="prob-bar"
                      style={{ width: `${Math.max(0, Math.min(1, c.probability)) * 100}%` }}
                    />
                  </span>
                  <span className="prob-value">{formatPercent(c.probability)}</span>
                </li>
              ))}
            </ul>

            <h3>Top contributing factors</h3>
            <ul className="factor-list">
              {explanation.top_contributing_factors.map((f, idx) => (
                <li key={`${f.keyword}-${idx}`} className={`factor factor-${f.direction}`}>
                  <div className="factor-head">
                    <span className="factor-keyword">{f.keyword}</span>
                    <span className="factor-weight">weight {f.weight}</span>
                  </div>
                  <p className="factor-desc">{f.description}</p>
                  <p className="factor-direction">{f.direction.replace('_', ' ')}</p>
                </li>
              ))}
            </ul>

            {/* Novelty 1: Isolation Forest Anomaly Audit */}
            {anomalyData && (
              <div style={{ marginTop: '28px', paddingTop: '20px', borderTop: '1px solid #dfe6f2' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 style={{ margin: 0, color: '#172033' }}>🌲 Isolation Forest Anomaly Audit</h3>
                  <span className={`badge ${anomalyData.is_anomalous ? 'badge-bad' : 'badge-good'}`} style={{ fontSize: '.85rem', padding: '6px 12px' }}>
                    {anomalyData.audit_status}
                  </span>
                </div>
                <div className="explanation-headline" style={{ margin: '14px 0 10px', padding: '12px' }}>
                  <div>
                    <p className="stat-label">Anomaly Score</p>
                    <p className="stat-value" style={{ color: anomalyData.is_anomalous ? '#ae2431' : '#1d6b3d' }}>
                      {anomalyData.anomaly_score} / 1.0
                    </p>
                  </div>
                  <div>
                    <p className="stat-label">Pipeline Audit Action</p>
                    <p className="stat-value" style={{ fontSize: '1rem' }}>{anomalyData.recommendation}</p>
                  </div>
                </div>
                <ul style={{ margin: '6px 0 0', paddingLeft: '20px', fontSize: '.9rem', color: '#44536b' }}>
                  {anomalyData.anomaly_reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Novelty 2: SHAP Resume-vs-Database Distribution Comparison */}
            {shapData && (
              <div style={{ marginTop: '24px', paddingTop: '20px', borderTop: '1px solid #dfe6f2' }}>
                <h3 style={{ margin: '0 0 10px', color: '#172033' }}>📄 SHAP Resume-vs-Database Feature Comparison</h3>
                <div className="explanation-headline" style={{ margin: '0 0 14px', padding: '12px' }}>
                  <div>
                    <p className="stat-label">Database Coverage Score</p>
                    <p className="stat-value" style={{ color: '#1959b8' }}>
                      {(shapData.database_coverage_score * 100).toFixed(0)}%
                    </p>
                  </div>
                  <div>
                    <p className="stat-label">Well-Supported Skills</p>
                    <p className="stat-value" style={{ fontSize: '1.1rem', color: '#1d6b3d' }}>
                      {shapData.well_supported_skills.length} skills verified
                    </p>
                  </div>
                  <div>
                    <p className="stat-label">Attribution Method</p>
                    <p className="stat-value mono" style={{ fontSize: '.85rem' }}>{shapData.shap_method_used}</p>
                  </div>
                </div>

                {shapData.outlier_or_exaggerated_skills?.length > 0 && (
                  <div style={{ background: '#fcefef', borderLeft: '4px solid #8a1d29', padding: '10px 14px', borderRadius: '8px', marginBottom: '14px' }}>
                    <strong style={{ color: '#8a1d29' }}>⚠️ Outlier / Potential Exaggerated Skills Detected: </strong>
                    <span>{shapData.outlier_or_exaggerated_skills.join(', ')}</span>
                  </div>
                )}

                <div className="skill-chips" style={{ maxWidth: '100%' }}>
                  {shapData.well_supported_skills.map(s => (
                    <span key={s} className="chip" style={{ background: '#e6f0ff', color: '#1959b8' }}>✏️“ {s}</span>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : null}
      </section>

      {editingStudent && (
        <EditStudentModal
          student={editingStudent}
          onClose={() => setEditingStudent(null)}
          onSuccess={() => { setEditingStudent(null); refreshData(); }}
        />
      )}
    </>
  )
}

// ----- jobs table ----------------------------------------------------------

export function AdminJobsPage() {
  const { auth } = useAuth()
  const [jobs, setJobs] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setError('')
      try {
        const data = await apiRequest('/api/v1/jobs/?limit=100', {
          headers: { Authorization: `Bearer ${auth.token}` },
        })
        if (!cancelled) setJobs(data)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load jobs.')
      }
    }
    load()
    return () => { cancelled = true }
  }, [auth.token])

  return (
    <>
      <AdminSubNav />
      <header className="dashboard-header">
        <p className="eyebrow">Job postings</p>
        <h1>All active jobs</h1>
        <p className="muted">All job postings across companies.</p>
      </header>

      {error && <ErrorBlock message={error} />}

      {jobs == null ? (
        <LoadingBlock />
      ) : jobs.length === 0 ? (
        <EmptyState message="No active job postings yet." />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Target domain</th>
                <th>Min CGPA</th>
                <th>Max backlogs</th>
                <th>Required skills</th>
                <th>Company</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td><strong>{j.title}</strong></td>
                  <td>{j.target_domain}</td>
                  <td>{formatCgpa(j.min_cgpa)}</td>
                  <td>{j.max_backlogs_allowed}</td>
                  <td>
                    <div className="skill-chips">
                      {(j.required_skills || []).map((s) => (
                        <span key={s} className="chip">{s}</span>
                      ))}
                    </div>
                  </td>
                  <td>{j.company_name ? <strong>{j.company_name}</strong> : <span className="muted">#{j.company_id}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

// ----- interview outcomes table --------------------------------------------

export function AdminInterviewsPage() {
  const { auth } = useAuth()
  const [records, setRecords] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setError('')
      try {
        const data = await apiRequest('/api/v1/interviews/', {
          headers: { Authorization: `Bearer ${auth.token}` },
        })
        if (!cancelled) setRecords(data)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load interview records.')
      }
    }
    load()
    return () => { cancelled = true }
  }, [auth.token])

  return (
    <>
      <AdminSubNav />
      <header className="dashboard-header">
        <p className="eyebrow">Interview Records</p>
        <h1>Campus Placement Interview Outcomes</h1>
        <p className="muted">Recruiter evaluation ratings, decision outcomes, and feedback notes across all companies.</p>
      </header>

      {error && <ErrorBlock message={error} />}

      {records == null ? (
        <LoadingBlock label="Loading... interview outcome records…" />
      ) : records.length === 0 ? (
        <EmptyState message="No interview feedback records logged yet." />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Job &amp; Company</th>
                <th>Round</th>
                <th>Scores (Tech / Comm / PS)</th>
                <th>Outcome</th>
                <th>Recruiter Summary</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr key={r.id}>
                  <td>
                    <strong>{r.student_name || `Student #${r.student_id}`}</strong>
                    <br />
                    <span className="mono muted" style={{ fontSize: '0.8rem' }}>{r.student_roll}</span>
                  </td>
                  <td>
                    <strong>{r.job_title}</strong>
                    <br />
                    <span className="muted" style={{ fontSize: '0.85rem' }}>{r.company_name}</span>
                  </td>
                  <td>{r.round_name} (#{r.round_number})</td>
                  <td>
                    <div style={{ fontSize: '0.85rem', lineHeight: '1.4' }}>
                      Tech: <strong>{r.technical_score}</strong> | Comm: <strong>{r.communication_score}</strong> | PS: <strong>{r.problem_solving_score}</strong>
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${r.interview_outcome === 'passed' ? 'badge-good' : r.interview_outcome === 'on_hold' ? 'badge-buffer' : 'badge-bad'}`}>
                      {r.interview_outcome.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ maxWidth: '280px', fontSize: '0.85rem' }} className="muted">
                    {r.detailed_feedback}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
// ============================================================
// PHASE 7: SECTIONS MANAGEMENT
// ============================================================

// ----- Create Section Modal ----------------------------------------

function CreateSectionModal({ onClose, onCreated }) {
  const { auth } = useAuth()
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true); setError('')
    try {
      const data = await apiRequest('/api/v1/sections/', {
        method: 'POST',
        headers: { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() }),
      })
      onCreated(data)
    } catch (err) {
      setError(err.message || 'Failed to create section.')
    } finally { setSubmitting(false) }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal-card" style={{ maxWidth: '420px' }}>
        <div className="modal-header">
          <h2>📂 Create New Section</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          <label className="field">
            Section Name
            <input
              required autoFocus
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. IT-A, CSE-B, DS-2025"
              style={{ fontFamily: 'monospace', letterSpacing: '0.05em' }}
            />
          </label>
          {error && <p className="error-message">{error}</p>}
          <div style={{ display: 'flex', gap: '12px', marginTop: '16px', justifyContent: 'flex-end' }}>
            <button type="button" className="logout-button" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary-button" disabled={submitting || !name.trim()}>
              {submitting ? 'Creating…' : 'Create Section'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ----- Section CSV Upload Modal ------------------------------------

function SectionBulkUploadModal({ sectionId, sectionName, onClose, onSuccess }) {
  const { auth } = useAuth()
  const [file, setFile] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!file) { setError('Please select a file to upload.'); return }

    const confirmUpload = window.confirm(
      `Upload file to ${sectionName}? Any student in this file who is already assigned to another section will be moved to ${sectionName}.`
    )
    if (!confirmUpload) return

    setSubmitting(true); setError(''); setResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const baseUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
      const res = await fetch(`${baseUrl}/api/v1/sections/${sectionId}/bulk-upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${auth.token}` },
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || 'Upload failed.')
      setResult(data)
      onSuccess()
    } catch (err) {
      setError(err.message)
    } finally { setSubmitting(false) }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal-card" style={{ maxWidth: '520px' }}>
        <div className="modal-header">
          <h2>📄 Bulk Upload (CSV, Excel, Word) {sectionName}</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          <p className="muted" style={{ marginBottom: 8 }}>
            Upload a file (.csv, .xlsx, .docx) containing student data with columns: <code>email, full_name, roll_number, department, batch_year, cgpa, active_backlogs, skills, resume_text</code>.
          </p>
          <div style={{ padding: '10px 12px', background: '#fff3e0', border: '1px solid #ffe0b2', borderRadius: 8, fontSize: '0.82rem', color: '#e65100', marginBottom: 12 }}>
            ⚠️ <strong>Re-assignment Notice:</strong> Students already belonging to another section will be moved to <strong>{sectionName}</strong> upon bulk upload.
          </div>
          <label className="field">
            Data File (.csv, .xlsx, .docx)
            <input type="file" accept=".csv,.xlsx,.xls,.docx,.txt" onChange={e => setFile(e.target.files[0])} />
          </label>
          {result && (
            <div style={{ padding: '12px', background: '#e6f4ea', borderRadius: 8, fontSize: '0.875rem' }}>
              ✏️… Inserted/Updated <strong>{result.successful_inserts}</strong> of <strong>{result.total_parsed}</strong> rows.
              {result.failed_rows?.length > 0 && <span style={{ color: '#b71c1c' }}> {result.failed_rows.length} rows failed.</span>}
            </div>
          )}
          {error && <p className="error-message">{error}</p>}
          <div style={{ display: 'flex', gap: '12px', marginTop: '16px', justifyContent: 'flex-end' }}>
            <button type="button" className="logout-button" onClick={onClose}>Close</button>
            <button type="submit" className="primary-button" disabled={submitting}>
              {submitting ? 'Uploading…' : 'Upload File'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )

}

// ----- Add Existing Student to Section Modal -----------------------

function AddStudentToSectionModal({ sectionId, sectionName, onClose, onSuccess }) {
  const { auth } = useAuth()
  const [allStudents, setAllStudents] = useState([])
  const [sectionsMap, setSectionsMap] = useState({})
  const [selectedStudentId, setSelectedStudentId] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadData() {
      try {
        const [studRes, secRes] = await Promise.all([
          apiRequest('/api/v1/students/?limit=500', { headers: { Authorization: `Bearer ${auth.token}` } }),
          apiRequest('/api/v1/sections/', { headers: { Authorization: `Bearer ${auth.token}` } })
        ])
        setAllStudents(studRes || [])
        const map = {}
        ;(secRes || []).forEach(s => { map[s.id] = s.name })
        setSectionsMap(map)
      } catch (err) {
        setError(err.message || 'Failed to load students list.')
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [auth.token])

  const selectedStudent = allStudents.find(s => s.id === Number(selectedStudentId))
  const isAlreadyInAnotherSection = selectedStudent && selectedStudent.section_id && selectedStudent.section_id !== sectionId
  const currentSectionName = isAlreadyInAnotherSection ? (sectionsMap[selectedStudent.section_id] || `Section #${selectedStudent.section_id}`) : ''

  async function handleAdd(e) {
    e.preventDefault()
    if (!selectedStudentId) return

    if (isAlreadyInAnotherSection) {
      const confirmMove = window.confirm(
        `This student "${selectedStudent.full_name}" is currently in ${currentSectionName}. Move them to ${sectionName}?`
      )
      if (!confirmMove) return
    }

    setSubmitting(true); setError('')
    try {
      await apiRequest(`/api/v1/sections/${sectionId}/add-student/${selectedStudentId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${auth.token}` }
      })
      onSuccess()
    } catch (err) {
      setError(err.message || 'Failed to add student to section.')
    } finally {
      setSubmitting(false)
    }
  }

  const eligibleStudents = allStudents.filter(s => s.section_id !== sectionId)

  return (
    <div className="modal-backdrop">
      <div className="modal-card" style={{ maxWidth: '520px' }}>
        <div className="modal-header">
          <h2>➕ Add Student {sectionName}</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>
        {loading ? (
          <LoadingBlock label="Loading... students database..." />
        ) : (
          <form onSubmit={handleAdd} className="auth-form">
            <label className="field">
              Select Student
              <select
                required
                value={selectedStudentId}
                onChange={e => setSelectedStudentId(e.target.value)}
              >
                <option value="">-- Select a student --</option>
                {eligibleStudents.map(s => (
                  <option key={s.id} value={s.id}>
                    {s.full_name} ({s.roll_number}) {s.section_id ? `— Currently in ${sectionsMap[s.section_id] || 'another section'}` : '— Unassigned'}
                  </option>
                ))}
              </select>
            </label>

            {isAlreadyInAnotherSection && (
              <div style={{ padding: '12px', background: '#fff3e0', border: '1px solid #ffe0b2', borderRadius: 8, fontSize: '0.85rem', color: '#e65100' }}>
                ⚠️ <strong>Section Transfer Notice:</strong> {selectedStudent.full_name} is currently in section <strong>{currentSectionName}</strong>. Submitting will transfer them to <strong>{sectionName}</strong>.
              </div>
            )}

            {error && <p className="error-message">{error}</p>}

            <div style={{ display: 'flex', gap: '12px', marginTop: '16px', justifyContent: 'flex-end' }}>
              <button type="button" className="logout-button" onClick={onClose}>Cancel</button>
              <button type="submit" className="primary-button" disabled={submitting || !selectedStudentId}>
                {submitting ? 'Adding...' : isAlreadyInAnotherSection ? `Move to ${sectionName}` : 'Add Student'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

// ----- Scoped AI Comparison Panel ----------------------------------

function ScopedAIPanel({ sectionId, sectionName, students }) {
  const { auth } = useAuth()
  const [selectedStudentId, setSelectedStudentId] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function runComparison() {
    if (!selectedStudentId) return
    setLoading(true); setError(''); setResult(null)
    try {
      const data = await apiRequest(
        `/api/v1/audit/anomaly-score/${selectedStudentId}?section_id=${sectionId}`,
        { headers: { Authorization: `Bearer ${auth.token}` } }
      )
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally { setLoading(false) }
  }

  const delta = result ? result.score_delta : null
  const deltaColor = delta > 0.05 ? '#b71c1c' : delta < -0.05 ? '#1b5e20' : '#374151'
  const deltaLabel = result?.delta_direction?.replace(/_/g, ' ') || ''

  return (
    <div className="scope-compare">
      <div className="scope-compare-header">
        <span className="scope-badge">🔬 Scoped AI Analysis</span>
        <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
          Compare Isolation Forest anomaly scores: global baseline vs. section <strong>{sectionName}</strong> peer distribution
        </p>
      </div>

      <div className="scope-compare-controls">
        <select
          className="scope-select"
          value={selectedStudentId}
          onChange={e => setSelectedStudentId(e.target.value)}
        >
          <option value="">— Select a student —</option>
          {(students || []).map(s => (
            <option key={s.id} value={s.id}>{s.full_name} ({s.roll_number})</option>
          ))}
        </select>
        <button
          className="primary-button"
          style={{ padding: '8px 18px' }}
          disabled={!selectedStudentId || loading}
          onClick={runComparison}
        >
          {loading ? 'Running…' : 'Run Scoped Anomaly'}
        </button>
      </div>

      {error && <p className="error-message" style={{ marginTop: 8 }}>{error}</p>}

      {result && (
        <div className="scope-result-grid">
          <div className="scope-score-card scope-global">
            <p className="scope-score-label">Global Score</p>
            <p className="scope-score-value">{result.global_anomaly_score?.toFixed(3)}</p>
            <p className="scope-score-status">{result.global_audit?.audit_status}</p>
          </div>
          <div className="scope-delta-arrow">
            <span style={{ fontSize: '1.6rem', color: deltaColor }}>
              {delta > 0.05 ? '▲' : delta < -0.05 ? '▼' : '≈'}
            </span>
            <span className="scope-delta-value" style={{ color: deltaColor }}>
              {delta > 0 ? '+' : ''}{result.score_delta?.toFixed(3)}
            </span>
            <span className="muted" style={{ fontSize: '0.75rem', textAlign: 'center' }}>{deltaLabel}</span>
          </div>
          <div className="scope-score-card scope-section">
            <p className="scope-score-label">Section Score</p>
            <p className="scope-score-value">{result.scoped_anomaly_score?.toFixed(3)}</p>
            <p className="scope-score-status">{result.anomaly_audit?.audit_status}</p>
          </div>

          <div className="scope-reasons">
            <p className="scope-reasons-label">Section Audit Reasons:</p>
            <ul>
              {(result.anomaly_audit?.anomaly_reasons || []).map((r, i) => <li key={i}>{r}</li>)}
            </ul>
            {result.anomaly_audit?.scope_warning && (
              <p className="scope-warning">⚠️ {result.anomaly_audit.scope_warning}</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ----- Inline Editable Spreadsheet Table Row -----------------------

// ----- Section Single Resume / Record Upload Modal with Conflict Check ----

function SectionSingleUploadModal({ sectionId, sectionName, onClose, onSuccess }) {
  const { auth } = useAuth()
  const [form, setForm] = useState({
    email: '',
    full_name: '',
    roll_number: '',
    department: 'Computer Science',
    cgpa: '7.5',
    active_backlogs: '0',
    skills_csv: '',
    raw_text: ''
  })
  const [file, setFile] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [conflictData, setConflictData] = useState(null)

  async function submitUpload(paramsExtra = {}) {
    setSubmitting(true)
    setError('')
    try {
      const formData = new FormData()
      if (file) formData.append('file', file)

      const params = new URLSearchParams({
        email: form.email,
        full_name: form.full_name,
        roll_number: form.roll_number,
        department: form.department,
        cgpa: form.cgpa,
        active_backlogs: form.active_backlogs,
        skills_csv: form.skills_csv,
        raw_text: form.raw_text,
        ...paramsExtra
      })

      const baseUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
      const res = await fetch(`${baseUrl}/api/v1/sections/${sectionId}/upload-resume?${params.toString()}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${auth.token}` },
        body: formData
      })
      const data = await res.json()
      if (!res.ok) {
        if (res.status === 409 && data.detail && data.detail.status === 'conflict') {
          setConflictData(data.detail)
          return
        }
        throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || 'Failed to upload student')
      }
      onSuccess()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  function handleSubmit(e) {
    e.preventDefault()
    submitUpload()
  }

  if (conflictData) {
    return (
      <div className="modal-backdrop">
        <div className="modal-card" style={{ maxWidth: '650px' }}>
          <div className="modal-header">
            <h2 style={{ color: '#c2410c' }}>⚠️ Data Consistency Conflict Detected</h2>
            <button className="close-button" onClick={onClose}>×</button>
          </div>
          <p className="muted" style={{ fontSize: '0.88rem' }}>
            A student matching identity (Roll No: <strong>{conflictData.incoming_record?.roll_number}</strong> / Email: <strong>{conflictData.incoming_record?.email}</strong>) ALREADY exists in the database with differing values:
          </p>

          <div style={{ overflowX: 'auto', margin: '14px 0' }}>
            <table className="students-table" style={{ fontSize: '0.82rem' }}>
              <thead>
                <tr>
                  <th>Field</th>
                  <th style={{ color: '#b91c1c' }}>Existing Database Record</th>
                  <th style={{ color: '#15803d' }}>Incoming Upload Record</th>
                </tr>
              </thead>
              <tbody>
                {(conflictData.conflicting_fields || []).map((cf, idx) => (
                  <tr key={idx}>
                    <td><strong>{cf.field}</strong></td>
                    <td style={{ background: '#fef2f2', color: '#991b1b' }}>{JSON.stringify(cf.existing_value)}</td>
                    <td style={{ background: '#f0fdf4', color: '#166534' }}>{JSON.stringify(cf.incoming_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="muted" style={{ fontSize: '0.82rem' }}>
            Please select how to resolve this conflict:
          </p>

          {error && <p className="error-message">{error}</p>}

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'flex-end', marginTop: 16 }}>
            <button type="button" className="logout-button" onClick={onClose}>Cancel</button>
            <button
              type="button"
              className="primary-button"
              style={{ background: '#475569' }}
              disabled={submitting}
              onClick={() => submitUpload({ resolution: 'keep_existing' })}
            >
              Keep Existing & Assign to {sectionName}
            </button>
            <button
              type="button"
              className="primary-button"
              style={{ background: '#dc2626' }}
              disabled={submitting}
              onClick={() => submitUpload({ confirm_overwrite: 'true' })}
            >
              Overwrite with Incoming Data
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <div className="modal-header">
          <h2>📂 Add Student Record {sectionName}</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="edit-form-grid">
            <label className="field">
              Full Name *
              <input required value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} placeholder="e.g. Rahul Verma" />
            </label>
            <label className="field">
              Email *
              <input type="email" required value={form.email} onChange={e => setForm({...form, email: e.target.value})} placeholder="rahul@placematch.edu" />
            </label>
            <label className="field">
              Roll Number *
              <input required value={form.roll_number} onChange={e => setForm({...form, roll_number: e.target.value})} placeholder="21CSE088" />
            </label>
            <label className="field">
              Department
              <input value={form.department} onChange={e => setForm({...form, department: e.target.value})} />
            </label>
            <label className="field">
              CGPA
              <input type="number" step="0.01" min="0" max="10" value={form.cgpa} onChange={e => setForm({...form, cgpa: e.target.value})} />
            </label>
            <label className="field">
              Active Backlogs
              <input type="number" min="0" value={form.active_backlogs} onChange={e => setForm({...form, active_backlogs: e.target.value})} />
            </label>
            <label className="field" style={{ gridColumn: '1 / -1' }}>
              Skills (comma separated)
              <input value={form.skills_csv} onChange={e => setForm({...form, skills_csv: e.target.value})} placeholder="Python, PyTorch, React" />
            </label>
            <label className="field" style={{ gridColumn: '1 / -1' }}>
              Upload Resume File (.txt or raw text)
              <input type="file" accept=".txt,.pdf" onChange={e => setFile(e.target.files[0])} />
            </label>
          </div>
          {error && <p className="error-message">{error}</p>}
          <div style={{ display: 'flex', gap: '12px', marginTop: '16px', justifyContent: 'flex-end' }}>
            <button type="button" className="logout-button" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary-button" disabled={submitting}>
              {submitting ? 'Adding…' : 'Add Student'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function SectionStudentRow({ student, sectionId, onUpdated, onRemoved }) {
  const { auth } = useAuth()
  const isRecruiter = auth?.user?.role === 'recruiter'
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    full_name: student.full_name || '',
    cgpa: student.cgpa ? Number(student.cgpa).toFixed(2) : '',
    department: student.department || '',
    active_backlogs: student.active_backlogs ?? 0,
    skills: Array.isArray(student.skills) ? student.skills.join(', ') : '',
    predicted_domain: student.predicted_domain || '',
  })
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [rowError, setRowError] = useState('')

  async function saveRow() {
    if (isRecruiter) return
    setSaving(true); setRowError('')
    try {
      await apiRequest(`/api/v1/sections/${sectionId}/students/${student.id}`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: form.full_name,
          cgpa: Number(form.cgpa),
          department: form.department,
          active_backlogs: Number(form.active_backlogs),
          skills: form.skills.split(',').map(s => s.trim()).filter(Boolean),
          predicted_domain: form.predicted_domain,
        }),
      })
      setEditing(false)
      onUpdated()
    } catch (err) {
      setRowError(err.message)
    } finally { setSaving(false) }
  }

  async function removeRow() {
    if (isRecruiter) return
    if (!window.confirm(`Remove ${student.full_name} from this section? (student is NOT deleted)`)) return
    setRemoving(true)
    try {
      await apiRequest(`/api/v1/sections/${sectionId}/students/${student.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      onRemoved(student.id)
    } catch (err) {
      setRowError(err.message)
    } finally { setRemoving(false) }
  }

  function CellInput({ field, type = 'text', style }) {
    return (
      <input
        className="cell-input"
        type={type}
        value={form[field]}
        style={style}
        onChange={e => setForm({ ...form, [field]: e.target.value })}
      />
    )
  }

  if (!editing || isRecruiter) {
    return (
      <>
        <tr className="section-student-row" onClick={() => { if (!isRecruiter) setEditing(true) }} title={isRecruiter ? '' : 'Click to edit'}>
          <td className="editable-cell">{student.full_name}</td>
          <td className="editable-cell">{student.roll_number}</td>
          <td className="editable-cell">{student.department}</td>
          <td className="editable-cell" style={{ textAlign: 'center' }}>{Number(student.cgpa).toFixed(2)}</td>
          <td className="editable-cell" style={{ textAlign: 'center' }}>{student.active_backlogs}</td>
          <td className="editable-cell" style={{ fontSize: '0.78rem', maxWidth: 200 }}>
            {Array.isArray(student.skills) ? student.skills.slice(0, 4).join(', ') : '—'}
            {Array.isArray(student.skills) && student.skills.length > 4 ? ' …' : ''}
          </td>
          <td className="editable-cell">
            <span className="badge badge-buffer" style={{ fontSize: '0.72rem' }}>{student.predicted_domain || '—'}</span>
          </td>
          {!isRecruiter && (
            <td>
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="primary-button" style={{ padding: '4px 10px', fontSize: '0.78rem' }} onClick={e => { e.stopPropagation(); setEditing(true) }}>✏️</button>
                <button className="logout-button" style={{ padding: '4px 10px', fontSize: '0.78rem' }} onClick={e => { e.stopPropagation(); removeRow() }} disabled={removing}>{removing ? '…' : '✏️•'}</button>
              </div>
            </td>
          )}
        </tr>
        {rowError && (
          <tr><td colSpan={isRecruiter ? 7 : 8}><p className="error-message" style={{ margin: '4px 0' }}>{rowError}</p></td></tr>
        )}
      </>
    )
  }

  // Editing row (Admin only)
  return (
    <>
      <tr className="section-student-row is-editing">
        <td><CellInput field="full_name" /></td>
        <td><span className="muted" style={{ fontSize: '0.82rem', padding: '0 4px' }}>{student.roll_number}</span></td>
        <td><CellInput field="department" /></td>
        <td><CellInput field="cgpa" type="number" style={{ width: 64 }} /></td>
        <td><CellInput field="active_backlogs" type="number" style={{ width: 48 }} /></td>
        <td><CellInput field="skills" style={{ width: '100%', fontSize: '0.78rem' }} /></td>
        <td><CellInput field="predicted_domain" /></td>
        <td>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="primary-button" style={{ padding: '4px 10px', fontSize: '0.78rem' }} onClick={saveRow} disabled={saving}>{saving ? '…' : '✏️…'}</button>
            <button className="logout-button" style={{ padding: '4px 10px', fontSize: '0.78rem' }} onClick={() => { setEditing(false); setRowError('') }}>✏️•</button>
          </div>
        </td>
      </tr>
      {rowError && (
        <tr><td colSpan={8}><p className="error-message" style={{ margin: '4px 0' }}>{rowError}</p></td></tr>
      )}
    </>
  )
}

// ----- Admin Sections List Page ------------------------------------

export function AdminSectionsPage() {
  const { auth } = useAuth()
  const isRecruiter = auth?.user?.role === 'recruiter'
  const [sections, setSections] = useState(null)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)

  async function loadSections() {
    setError('')
    try {
      const data = await apiRequest('/api/v1/sections/', {
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      setSections(data)
    } catch (err) {
      setError(err.message || 'Failed to load sections.')
    }
  }

  useEffect(() => { loadSections() }, [auth.token]) // eslint-disable-line

  async function deleteSection(id, name) {
    if (isRecruiter) return
    if (!window.confirm(`Delete section "${name}"? Students will be unassigned (not deleted).`)) return
    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
      const res = await fetch(`${baseUrl}/api/v1/sections/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail) }
      loadSections()
    } catch (err) {
      alert(err.message)
    }
  }

  return (
    <>
      {!isRecruiter && <AdminSubNav />}
      <header className="dashboard-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <p className="eyebrow">{isRecruiter ? 'Recruiter Portal — Read Only' : 'Phase 7 — Sections'}</p>
          <h1>Student Sections</h1>
          <p className="muted">
            {isRecruiter
              ? 'View student sections and candidate lists.'
              : 'Create sub-databases of students by batch/department. Click a section to open the editable student table.'}
          </p>
        </div>
        {!isRecruiter && (
          <button className="primary-button" style={{ padding: '10px 18px' }} onClick={() => setShowCreate(true)}>
            + New Section
          </button>
        )}
      </header>

      {error && <ErrorBlock message={error} onRetry={loadSections} />}
      {sections == null && <LoadingBlock />}

      {Array.isArray(sections) && sections.length === 0 && (
        <EmptyState message="No sections yet." />
      )}

      {Array.isArray(sections) && sections.length > 0 && (
        <div className="section-list">
          {sections.map(sec => (
            <article key={sec.id} className="section-card">
              <div className="section-card-body">
                <p className="section-card-name">{sec.name}</p>
                <p className="section-card-meta">
                  <span className="section-badge-count">{sec.student_count} student{sec.student_count !== 1 ? 's' : ''}</span>
                  <span className="muted" style={{ fontSize: '0.78rem' }}>
                    Created {new Date(sec.created_at).toLocaleDateString()}
                  </span>
                </p>
              </div>
              <div className="section-card-actions">
                <Link
                  to={isRecruiter ? `/recruiter/sections/${sec.id}` : `/admin/sections/${sec.id}`}
                  className="primary-button"
                  style={{ padding: '8px 16px', textDecoration: 'none', fontSize: '0.875rem' }}
                >
                  Open ←’
                </Link>
                {!isRecruiter && (
                  <button className="logout-button" style={{ padding: '8px 12px', fontSize: '0.875rem' }} onClick={() => deleteSection(sec.id, sec.name)}>
                    📄
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {showCreate && !isRecruiter && (
        <CreateSectionModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); loadSections() }}
        />
      )}
    </>
  )
}

// ----- Admin Section Detail Page (editable spreadsheet) ------------

export function AdminSectionDetailPage() {
  const { auth } = useAuth()
  const isRecruiter = auth?.user?.role === 'recruiter'
  const { sectionId } = useParams()
  const [section, setSection] = useState(null)
  const [students, setStudents] = useState(null)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [showBulkUpload, setShowBulkUpload] = useState(false)
  const [showAddStudent, setShowAddStudent] = useState(false)
  const [showSingleUpload, setShowSingleUpload] = useState(false)
  const [showAIPanel, setShowAIPanel] = useState(false)

  async function loadSection() {
    try {
      const data = await apiRequest(`/api/v1/sections/${sectionId}`, {
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      setSection(data)
    } catch (err) {
      setError(err.message)
    }
  }

  async function loadStudents(q = '') {
    setError('')
    try {
      const params = new URLSearchParams({ limit: '500' })
      if (q) params.set('search', q)
      const data = await apiRequest(`/api/v1/sections/${sectionId}/students?${params}`, {
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      setStudents(data)
    } catch (err) {
      setError(err.message || 'Failed to load students.')
    }
  }

  useEffect(() => {
    loadSection()
    loadStudents()
  }, [sectionId, auth.token]) // eslint-disable-line

  function handleRemoved(studentId) {
    setStudents(prev => (prev || []).filter(s => s.id !== studentId))
  }

  const sectionsBackLink = isRecruiter ? '/recruiter/sections' : '/admin/sections'

  return (
    <>
      {!isRecruiter && <AdminSubNav />}
      <header className="dashboard-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <p className="eyebrow">
            <Link to={sectionsBackLink} style={{ color: 'var(--primary)', textDecoration: 'none' }}>← Sections</Link>
          </p>
          <h1 style={{ fontFamily: 'monospace', letterSpacing: '0.06em' }}>
            {section ? section.name : `Section #${sectionId}`}
          </h1>
          <p className="muted">
            {section
              ? `${section.student_count} student${section.student_count !== 1 ? 's' : ''} ${isRecruiter ? '(Read Only view)' : '— click any row to edit inline'}`
              : 'Loading...'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {!isRecruiter && (
            <>
              <button className="primary-button" style={{ padding: '8px 16px' }} onClick={() => setShowSingleUpload(true)}>
                📂 Add Student Record
              </button>
              <button className="primary-button" style={{ padding: '8px 16px' }} onClick={() => setShowAddStudent(true)}>
                ➕ Select Existing
              </button>
              <button className="primary-button" style={{ padding: '8px 16px' }} onClick={() => setShowBulkUpload(true)}>
                📄 Bulk Upload CSV
              </button>
            </>
          )}
          <button
            className={showAIPanel ? 'logout-button' : 'primary-button'}
            style={{ padding: '8px 16px', background: showAIPanel ? undefined : 'linear-gradient(135deg, #7c3aed, #4f46e5)' }}
            onClick={() => setShowAIPanel(!showAIPanel)}
          >
            🔬 {showAIPanel ? 'Hide' : 'Scoped AI'}
          </button>
        </div>
      </header>

      {error && <ErrorBlock message={error} onRetry={() => loadStudents(search)} />}

      {/* Scoped AI comparison panel */}
      {showAIPanel && section && (
        <ScopedAIPanel sectionId={parseInt(sectionId)} sectionName={section.name} students={students} />
      )}

      {/* Search bar */}
      <form
        className="filter-row"
        style={{ marginBottom: 16 }}
        onSubmit={e => { e.preventDefault(); loadStudents(search) }}
      >
        <label className="field filter-field">
          <span>Search students in this section</span>
          <input
            type="search"
            value={search}
            placeholder="Name, roll number, or email…"
            onChange={e => setSearch(e.target.value)}
          />
        </label>
        <div className="filter-actions">
          <button className="primary-button" type="submit">Search</button>
          <button className="logout-button" type="button" onClick={() => { setSearch(''); loadStudents('') }}>Reset</button>
        </div>
      </form>

      {students == null ? (
        <LoadingBlock />
      ) : students.length === 0 ? (
        <EmptyState message="No students in this section yet." />
      ) : (
        <div className="section-grid-wrapper">
          {!isRecruiter && (
            <p className="muted" style={{ fontSize: '0.82rem', marginBottom: 8 }}>
              💡 Click any row to edit inline. Changes are saved per-row.
            </p>
          )}
          <div className="table-scroll-wrapper">
            <table className="students-table section-spreadsheet">
              <thead>
                <tr>
                  <th>Full Name</th>
                  <th>Roll No</th>
                  <th>Department</th>
                  <th style={{ textAlign: 'center' }}>CGPA</th>
                  <th style={{ textAlign: 'center' }}>Backlogs</th>
                  <th>Skills</th>
                  <th>Predicted Domain</th>
                  {!isRecruiter && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {students.map(student => (
                  <SectionStudentRow
                    key={student.id}
                    student={student}
                    sectionId={parseInt(sectionId)}
                    onUpdated={() => loadStudents(search)}
                    onRemoved={handleRemoved}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showAddStudent && !isRecruiter && section && (
        <AddStudentToSectionModal
          sectionId={parseInt(sectionId)}
          sectionName={section.name}
          onClose={() => setShowAddStudent(false)}
          onSuccess={() => { setShowAddStudent(false); loadStudents(search); loadSection() }}
        />
      )}

      {showSingleUpload && !isRecruiter && section && (
        <SectionSingleUploadModal
          sectionId={parseInt(sectionId)}
          sectionName={section.name}
          onClose={() => setShowSingleUpload(false)}
          onSuccess={() => { setShowSingleUpload(false); loadStudents(search); loadSection() }}
        />
      )}

      {showBulkUpload && !isRecruiter && section && (
        <SectionBulkUploadModal
          sectionId={parseInt(sectionId)}
          sectionName={section.name}
          onClose={() => setShowBulkUpload(false)}
          onSuccess={() => { setShowBulkUpload(false); loadStudents(search); loadSection() }}
        />
      )}
    </>
  )
}


// ============================================================================
// AdminFairnessPage — Fairness Audit tab
// ============================================================================

function FourFifthsBadge({ passes }) {
  const style = {
    display: 'inline-block',
    padding: '2px 10px',
    borderRadius: '12px',
    fontSize: '0.78rem',
    fontWeight: 700,
    background: passes ? '#d1fae5' : '#fee2e2',
    color: passes ? '#065f46' : '#991b1b',
    border: `1px solid ${passes ? '#6ee7b7' : '#fca5a5'}`,
  }
  return <span style={style}>{passes ? '✏️“ Passes 4/5ths' : '✏️— Fails 4/5ths'}</span>
}

function FairnessMetricsPanel({ metrics, label }) {
  if (!metrics) return null
  return (
    <section style={{ marginBottom: '1.5rem' }}>
      <h3 style={{ marginBottom: '0.5rem', fontSize: '1rem' }}>{label}</h3>
      <table className="data-table" style={{ marginBottom: '0.75rem' }}>
        <thead>
          <tr>
            <th>Group</th>
            <th style={{ textAlign: 'center' }}>Total</th>
            <th style={{ textAlign: 'center' }}>Selected</th>
            <th style={{ textAlign: 'center' }}>Selection Rate</th>
          </tr>
        </thead>
        <tbody>
          {metrics.group_rates.map(g => (
            <tr key={g.group}>
              <td>
                {g.group}
                {g.group === metrics.privileged_group && (
                  <span style={{ marginLeft: 6, fontSize: '0.72rem', color: '#6b7280' }}>(privileged)</span>
                )}
              </td>
              <td style={{ textAlign: 'center' }}>{g.total}</td>
              <td style={{ textAlign: 'center' }}>{g.selected}</td>
              <td style={{ textAlign: 'center' }}>{(g.selection_rate * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: '0.9rem' }}>
          <strong>DPD:</strong>{' '}
          <code>{(metrics.demographic_parity_difference * 100).toFixed(2)}%</code>
        </span>
        <span style={{ fontSize: '0.9rem' }}>
          <strong>DIR:</strong>{' '}
          <code>{metrics.disparate_impact_ratio != null ? metrics.disparate_impact_ratio.toFixed(4) : 'N/A'}</code>
        </span>
        <FourFifthsBadge passes={metrics.passes_four_fifths} />
      </div>
      {metrics.unprivileged_groups && metrics.unprivileged_groups.length > 0 && (
        <details style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
          <summary style={{ cursor: 'pointer', color: '#4b5563' }}>Per-group DIR breakdown</summary>
          <ul style={{ marginTop: '0.4rem', paddingLeft: '1.2rem' }}>
            {metrics.unprivileged_groups.map(u => (
              <li key={u.group}>
                <strong>{u.group}</strong>: DIR = {u.dir != null ? u.dir.toFixed(4) : 'N/A'}{' '}
                — <FourFifthsBadge passes={u.passes_four_fifths} />
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

function RateBar({ rate, color = '#3b82f6' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        height: 10, width: `${Math.max(4, rate * 160)}px`,
        background: color, borderRadius: 4, transition: 'width 0.3s',
      }} />
      <span style={{ fontSize: '0.82rem' }}>{(rate * 100).toFixed(1)}%</span>
    </div>
  )
}

function BeforeAfterTable({ metricsBefore, metricsAfter, thresholds, label }) {
  if (!metricsBefore || !metricsAfter) return null
  const groups = [...new Set([
    ...metricsBefore.group_rates.map(g => g.group),
    ...metricsAfter.group_rates.map(g => g.group),
  ])].sort()
  const beforeMap = Object.fromEntries(metricsBefore.group_rates.map(g => [g.group, g]))
  const afterMap  = Object.fromEntries(metricsAfter.group_rates.map(g  => [g.group, g]))
  const threshMap = Object.fromEntries((thresholds || []).map(t => [t.group, t.threshold]))

  return (
    <section style={{ marginBottom: '1.5rem' }}>
      <h3 style={{ marginBottom: '0.5rem', fontSize: '1rem' }}>{label} — Before / After</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th>Group</th>
            <th>Threshold</th>
            <th>Before rate</th>
            <th>After rate</th>
            <th>Change</th>
          </tr>
        </thead>
        <tbody>
          {groups.map(group => {
            const b = beforeMap[group]
            const a = afterMap[group]
            const t = threshMap[group]
            const delta = a && b ? a.selection_rate - b.selection_rate : 0
            return (
              <tr key={group}>
                <td>{group}</td>
                <td><code>{t != null ? t.toFixed(3) : '0.700'}</code></td>
                <td><RateBar rate={b?.selection_rate ?? 0} color="#94a3b8" /></td>
                <td><RateBar rate={a?.selection_rate ?? 0} color="#3b82f6" /></td>
                <td style={{ color: delta > 0 ? '#059669' : delta < 0 ? '#dc2626' : '#6b7280', fontWeight: 600 }}>
                  {delta > 0 ? '+' : ''}{(delta * 100).toFixed(1)}%
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', alignItems: 'center', marginTop: '0.5rem' }}>
        <span style={{ fontSize: '0.9rem' }}>
          <strong>DIR before:</strong>{' '}
          <code>{metricsBefore.disparate_impact_ratio != null ? metricsBefore.disparate_impact_ratio.toFixed(4) : 'N/A'}</code>
          {' '}<FourFifthsBadge passes={metricsBefore.passes_four_fifths} />
        </span>
        <span style={{ fontSize: '0.9rem' }}>
          <strong>DIR after:</strong>{' '}
          <code>{metricsAfter.disparate_impact_ratio != null ? metricsAfter.disparate_impact_ratio.toFixed(4) : 'N/A'}</code>
          {' '}<FourFifthsBadge passes={metricsAfter.passes_four_fifths} />
        </span>
      </div>
    </section>
  )
}

export function AdminFairnessPage() {
  const { auth } = useAuth()
  const [jobs, setJobs] = useState(null)
  const [selectedJobId, setSelectedJobId] = useState('')
  const [includeBuffer, setIncludeBuffer] = useState(false)
  const [auditData, setAuditData]       = useState(null)
  const [mitigateData, setMitigateData] = useState(null)
  const [loadingAudit,    setLoadingAudit]    = useState(false)
  const [loadingMitigate, setLoadingMitigate] = useState(false)
  const [mitigationOn,    setMitigationOn]    = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    apiRequest('/api/v1/jobs/?limit=200', { headers: { Authorization: `Bearer ${auth.token}` } })
      .then(data => { if (!cancelled) setJobs(data) })
      .catch(err => { if (!cancelled) setError(err.message) })
    return () => { cancelled = true }
  }, [auth.token])

  useEffect(() => {
    if (!selectedJobId) { setAuditData(null); setMitigateData(null); return }
    let cancelled = false
    setLoadingAudit(true)
    setError('')
    setAuditData(null)
    setMitigateData(null)
    setMitigationOn(false)
    const params = new URLSearchParams({ include_buffer: includeBuffer })
    apiRequest(`/api/v1/fairness/audit/${selectedJobId}?${params}`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
      .then(data => { if (!cancelled) setAuditData(data) })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to load fairness audit.') })
      .finally(() => { if (!cancelled) setLoadingAudit(false) })
    return () => { cancelled = true }
  }, [selectedJobId, includeBuffer, auth.token])

  useEffect(() => {
    if (!mitigationOn || !selectedJobId) { if (!mitigationOn) setMitigateData(null); return }
    let cancelled = false
    setLoadingMitigate(true)
    setError('')
    const params = new URLSearchParams({ include_buffer: includeBuffer })
    apiRequest(`/api/v1/fairness/mitigate/${selectedJobId}?${params}`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
      .then(data => { if (!cancelled) setMitigateData(data) })
      .catch(err => { if (!cancelled) setError(err.message || 'Failed to load mitigation data.') })
      .finally(() => { if (!cancelled) setLoadingMitigate(false) })
    return () => { cancelled = true }
  }, [mitigationOn, selectedJobId, includeBuffer, auth.token])

  return (
    <>
      <AdminSubNav />
      <header className="dashboard-header">
        <p className="eyebrow">Admin tool</p>
        <h1>⚖️ Fairness Audit</h1>
        <p className="muted">
          Audit disparate impact across gender and reservation category for any job's
          current matching results. Optionally apply threshold equalization mitigation.
        </p>
      </header>

      {error && <ErrorBlock message={error} />}

      <section className="dashboard-card" style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Select a Job</h2>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <select
            value={selectedJobId}
            onChange={e => setSelectedJobId(e.target.value)}
            style={{ minWidth: 260, padding: '0.5rem 0.75rem', borderRadius: 6, border: '1px solid #d1d5db', fontSize: '0.9rem' }}
          >
            <option value="">— Choose a job posting —</option>
            {Array.isArray(jobs) && jobs.map(j => (
              <option key={j.id} value={j.id}>{j.title} (#{j.id})</option>
            ))}
          </select>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.9rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={includeBuffer} onChange={e => setIncludeBuffer(e.target.checked)} />
            Include buffer-match candidates
          </label>
        </div>
        {!selectedJobId && !loadingAudit && (
          <p className="muted" style={{ marginTop: '0.75rem' }}>Choose a job above to see its fairness metrics.</p>
        )}
      </section>

      {loadingAudit && <LoadingBlock label="Loading... fairness audit…" />}

      {auditData && (
        <section className="dashboard-card" style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
            <div>
              <h2 style={{ marginBottom: '0.2rem' }}>{auditData.job_title}</h2>
              <p className="muted" style={{ margin: 0 }}>
                {auditData.total_candidates_evaluated} candidates evaluated
                · {auditData.total_selected} selected
                {auditData.buffer_matching_enabled && ' (buffer matching enabled)'}
              </p>
            </div>
            <label style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '0.5rem 1rem', border: '1px solid #d1d5db', borderRadius: 8,
              background: mitigationOn ? '#eff6ff' : '#f9fafb',
              cursor: 'pointer', userSelect: 'none', fontSize: '0.9rem', fontWeight: 600,
            }}>
              <span style={{
                display: 'inline-block', width: 40, height: 22, borderRadius: 11,
                background: mitigationOn ? '#3b82f6' : '#d1d5db', position: 'relative', transition: 'background 0.2s',
              }}>
                <span style={{
                  position: 'absolute', top: 3, left: mitigationOn ? 20 : 3,
                  width: 16, height: 16, borderRadius: '50%', background: '#fff', transition: 'left 0.2s',
                }} />
              </span>
              <input type="checkbox" hidden checked={mitigationOn} onChange={e => setMitigationOn(e.target.checked)} />
              Apply fairness mitigation
            </label>
          </div>
          <FairnessMetricsPanel metrics={auditData.gender_metrics} label="Gender" />
          <FairnessMetricsPanel metrics={auditData.category_metrics} label="Reservation Category" />
        </section>
      )}

      {loadingMitigate && <LoadingBlock label="Computing threshold equalization…" />}

      {mitigationOn && mitigateData && (
        <section className="dashboard-card" style={{ marginBottom: '1.5rem' }}>
          <h2 style={{ marginBottom: '1rem' }}>Mitigation Results — Threshold Equalization</h2>
          <p className="muted" style={{ marginBottom: '1rem' }}>
            Per-group confidence thresholds adjusted so disparate impact ratios fall in [0.80 —“ 1.25].
            The global 0.70 gate is the floor — no group is held to a stricter standard than the original.
          </p>
          <BeforeAfterTable
            metricsBefore={mitigateData.gender_metrics_before}
            metricsAfter={mitigateData.gender_metrics_after}
            thresholds={mitigateData.gender_thresholds}
            label="Gender"
          />
          <BeforeAfterTable
            metricsBefore={mitigateData.category_metrics_before}
            metricsAfter={mitigateData.category_metrics_after}
            thresholds={mitigateData.category_thresholds}
            label="Reservation Category"
          />
          {mitigateData.changed_candidates.length === 0 ? (
            <p className="muted">No candidate selections changed after mitigation.</p>
          ) : (
            <>
              <h3 style={{ marginTop: '1rem', marginBottom: '0.5rem' }}>
                Changed Candidates ({mitigateData.changed_candidates.length})
              </h3>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Roll No</th>
                      <th>Name</th>
                      <th style={{ textAlign: 'center' }}>Gender</th>
                      <th style={{ textAlign: 'center' }}>Category</th>
                      <th style={{ textAlign: 'center' }}>Score</th>
                      <th style={{ textAlign: 'center' }}>Before</th>
                      <th style={{ textAlign: 'center' }}>After</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mitigateData.changed_candidates.map(c => (
                      <tr key={c.student_id}>
                        <td><code>{c.roll_number}</code></td>
                        <td>
                          {c.full_name}
                          {c.fairness_adjusted && (
                            <span style={{
                              marginLeft: 6, fontSize: '0.72rem', fontWeight: 700,
                              padding: '1px 7px', borderRadius: 10,
                              background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe',
                            }}>⚖️ fairness-adjusted</span>
                          )}
                        </td>
                        <td style={{ textAlign: 'center' }}>{c.gender || '—'}</td>
                        <td style={{ textAlign: 'center' }}>{c.category || '—'}</td>
                        <td style={{ textAlign: 'center' }}><code>{c.score.toFixed(3)}</code></td>
                        <td style={{ textAlign: 'center' }}>
                          <span style={{ color: c.original_selected ? '#059669' : '#6b7280', fontWeight: 600 }}>
                            {c.original_selected ? 'Selected' : 'Excluded'}
                          </span>
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <span style={{ color: c.mitigated_selected ? '#1d4ed8' : '#6b7280', fontWeight: 600 }}>
                            {c.mitigated_selected ? 'Selected' : 'Excluded'}
                          </span>
                        </td>
                        <td style={{ fontSize: '0.8rem', color: '#6b7280', maxWidth: 280 }}>{c.fairness_reason || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}
    </>
  )
}

