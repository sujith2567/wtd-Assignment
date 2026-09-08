import { useEffect, useState } from 'react'
import { Link, NavLink, useNavigate, useParams } from 'react-router-dom'
import { apiRequest, useAuth } from './api.jsx'

import { StatCard, LoadingBlock, ErrorBlock, EmptyState, formatPercent, formatCgpa } from './components.jsx';

import { AdminSectionsPage, AdminSectionDetailPage } from './admin.jsx'

export function RecruiterSubNav() {
  const tabs = [
    { to: '/recruiter/jobs', label: 'My Job Postings' },
    { to: '/recruiter/sections', label: '📂 Sections' },
    { to: '/recruiter/post-job', label: 'Post New Job' },
  ]
  return (
    <nav className="admin-tabs" aria-label="Recruiter sections">
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) => `admin-tab${isActive ? ' is-active' : ''}`}
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}

export function RecruiterSectionsPage() {
  return (
    <div className="recruiter-glass-theme">
      <RecruiterSubNav />
      <AdminSectionsPage />
    </div>
  )
}

export function RecruiterSectionDetailPage() {
  return (
    <div className="recruiter-glass-theme">
      <RecruiterSubNav />
      <AdminSectionDetailPage />
    </div>
  )
}


// ----- 1. My Job Postings ---------------------------------------------------

export function RecruiterJobsPage() {
  const { auth } = useAuth()
  const [jobs, setJobs] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setError('')
      try {
        const data = await apiRequest('/api/v1/jobs/my-jobs', {
          headers: { Authorization: `Bearer ${auth.token}` },
        })
        if (!cancelled) setJobs(data)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load job postings.')
      }
    }
    load()
    return () => { cancelled = true }
  }, [auth.token])

  return (
    <div className="recruiter-glass-theme">
      <RecruiterSubNav />
      <header className="dashboard-header">
        <p className="eyebrow">Recruiter Portal</p>
        <h1>My Job Postings</h1>
        <p className="muted">Manage listings and view AI-matched candidate shortlists.</p>
      </header>

      {error && <ErrorBlock message={error} />}

      {jobs == null ? (
        <LoadingBlock label="Loading... your job postings…" />
      ) : jobs.length === 0 ? (
        <EmptyState message="You haven't posted any jobs yet. Click 'Post New Job' to create one." />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Company</th>
                <th>Target Domain</th>
                <th>Min CGPA</th>
                <th>Max Backlogs</th>
                <th>Buffer Threshold</th>
                <th>Required Skills</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td><strong>{job.title}</strong></td>
                  <td>{job.company_name}</td>
                  <td>{job.target_domain}</td>
                  <td>{formatCgpa(job.min_cgpa)}</td>
                  <td>{job.max_backlogs_allowed}</td>
                  <td>{formatPercent(job.buffer_threshold_percent / 100)}</td>
                  <td>
                    <div className="skill-chips">
                      {(job.required_skills || []).map((skill) => (
                        <span key={skill} className="chip">{skill}</span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${job.status === 'active' ? 'badge-good' : 'badge-bad'}`}>
                      {job.status.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <Link className="link-button" to={`/recruiter/jobs/${job.id}/shortlist`}>
                      View Shortlist &rarr;
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ----- 2. Post a Job Page ---------------------------------------------------

export function PostJobPage() {
  const { auth } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    title: '',
    target_domain: 'Software Development',
    description: '',
    min_cgpa: '6.50',
    max_backlogs_allowed: '0',
    required_skills: '',
    preferred_skills: '',
    salary_range: '8 - 12 LPA',
    location: 'Bengaluru, KA',
    buffer_threshold_percent: '10.0',
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const _domains = [
    'Software Development',
    'Machine Learning',
    'Data Science & Analytics',
    'Cybersecurity & DevOps',
    'VLSI & Embedded Systems',
  ]

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)

    const requiredSkillsArr = form.required_skills
      .split(',')
      .map((s) => s.strip ? s.trim() : s)
      .filter(Boolean)
    const preferredSkillsArr = form.preferred_skills
      .split(',')
      .map((s) => s.strip ? s.trim() : s)
      .filter(Boolean)

    const payload = {
      title: form.title,
      target_domain: form.target_domain,
      description: form.description,
      min_cgpa: parseFloat(form.min_cgpa),
      max_backlogs_allowed: parseInt(form.max_backlogs_allowed, 10),
      required_skills: requiredSkillsArr,
      preferred_skills: preferredSkillsArr,
      salary_range: form.salary_range || null,
      location: form.location || null,
      buffer_threshold_percent: parseFloat(form.buffer_threshold_percent),
      status: 'active',
    }

    try {
      await apiRequest('/api/v1/jobs/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${auth.token}`,
        },
        body: JSON.stringify(payload),
      })
      navigate('/recruiter/jobs', { replace: true })
    } catch (err) {
      setError(err.message || 'Failed to post job.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="recruiter-glass-theme">
      <RecruiterSubNav />
      <header className="dashboard-header">
        <p className="eyebrow">Job Management</p>
        <h1>Post a New Job Opportunity</h1>
        <p className="muted">Define academic criteria, required skills, and adaptive buffer thresholds.</p>
      </header>

      {error && <ErrorBlock message={error} />}

      <section className="explainability-card" style={{ maxWidth: '800px' }}>
        <form className="auth-form" onSubmit={handleSubmit}>
          <div className="filter-row" style={{ padding: 0, border: 'none', background: 'transparent' }}>
            <label className="field filter-field">
              <span>Job Title *</span>
              <input
                required
                value={form.title}
                placeholder="e.g. Senior Machine Learning Engineer"
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </label>
            <label className="field filter-field">
              <span>Target Domain *</span>
              <select
                value={form.target_domain}
                onChange={(e) => setForm({ ...form, target_domain: e.target.value })}
              >
                <option value="Software Development">Software Development</option>
                <option value="Data Science & Analytics">Data Science &amp; Analytics</option>
                <option value="Web Development">Web Development</option>
                <option value="Machine Learning">Machine Learning</option>
                <option value="Cloud & Infrastructure">Cloud &amp; Infrastructure</option>
                <option value="Cybersecurity">Cybersecurity</option>
              </select>
            </label>
          </div>

          <label className="field">
            <span>Job Description *</span>
            <textarea
              required
              rows={4}
              style={{
                width: '100%',
                padding: '11px 12px',
                border: '1px solid #cbd6e6',
                borderRadius: '8px',
                font: 'inherit',
              }}
              value={form.description}
              placeholder="Describe key responsibilities and qualifications…"
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </label>

          <div className="filter-row" style={{ padding: 0, border: 'none', background: 'transparent' }}>
            <label className="field filter-field">
              <span>Min CGPA *</span>
              <input
                type="number"
                step="0.01"
                min="0"
                max="10"
                required
                value={form.min_cgpa}
                onChange={(e) => setForm({ ...form, min_cgpa: e.target.value })}
              />
            </label>
            <label className="field filter-field">
              <span>Max Backlogs Allowed *</span>
              <input
                type="number"
                min="0"
                required
                value={form.max_backlogs_allowed}
                onChange={(e) => setForm({ ...form, max_backlogs_allowed: e.target.value })}
              />
            </label>
            <label className="field filter-field">
              <span>Buffer Threshold (%)</span>
              <input
                type="number"
                step="1"
                min="0"
                max="50"
                value={form.buffer_threshold_percent}
                onChange={(e) => setForm({ ...form, buffer_threshold_percent: e.target.value })}
              />
            </label>
          </div>

          <div className="filter-row" style={{ padding: 0, border: 'none', background: 'transparent' }}>
            <label className="field filter-field">
              <span>Required Skills (comma separated) *</span>
              <input
                required
                value={form.required_skills}
                placeholder="Python, PyTorch, SQL"
                onChange={(e) => setForm({ ...form, required_skills: e.target.value })}
              />
            </label>
            <label className="field filter-field">
              <span>Preferred Skills (comma separated)</span>
              <input
                value={form.preferred_skills}
                placeholder="Docker, AWS, Git"
                onChange={(e) => setForm({ ...form, preferred_skills: e.target.value })}
              />
            </label>
          </div>

          <div className="filter-row" style={{ padding: 0, border: 'none', background: 'transparent' }}>
            <label className="field filter-field">
              <span>Salary Range</span>
              <input
                value={form.salary_range}
                placeholder="e.g. 10 - 14 LPA"
                onChange={(e) => setForm({ ...form, salary_range: e.target.value })}
              />
            </label>
            <label className="field filter-field">
              <span>Location</span>
              <input
                value={form.location}
                placeholder="e.g. Bengaluru, KA"
                onChange={(e) => setForm({ ...form, location: e.target.value })}
              />
            </label>
          </div>

          <div style={{ marginTop: '16px', display: 'flex', gap: '12px' }}>
            <button className="primary-button" type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Posting Job…' : 'Publish Job Posting'}
            </button>
            <button
              className="logout-button"
              type="button"
              onClick={() => navigate('/recruiter/jobs')}
            >
              Cancel
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}

// ----- Modal for Logging Interview Feedback --------------------------------

function InterviewFeedbackModal({ candidate, job, onClose, onSuccess, token }) {
  const [form, setForm] = useState({
    round_name: 'Technical Round 1',
    technical_score: 8.0,
    communication_score: 7.5,
    problem_solving_score: 8.0,
    interview_outcome: 'passed',
    strengths: '',
    weaknesses: '',
    detailed_feedback: '',
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [suggestedText, setSuggestedText] = useState(null)

  // Generate template suggestions dynamically when scores or outcome change
  useEffect(() => {
    let cancelled = false
    async function fetchSuggestions() {
      try {
        const sug = await apiRequest('/api/v1/interviews/template-suggestions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            technical_score: parseFloat(form.technical_score),
            communication_score: parseFloat(form.communication_score),
            problem_solving_score: parseFloat(form.problem_solving_score),
            outcome: form.interview_outcome,
          }),
        })
        if (!cancelled) {
          setSuggestedText(sug)
          // Autofill empty text fields if user hasn't typed custom notes
          setForm((prev) => ({
            ...prev,
            strengths: prev.strengths || sug.suggested_strengths,
            weaknesses: prev.weaknesses || sug.suggested_weaknesses,
            detailed_feedback: prev.detailed_feedback || sug.suggested_summary,
          }))
        }
      } catch {
        // Fallback silently if API fails
      }
    }
    fetchSuggestions()
    return () => { cancelled = true }
  }, [form.technical_score, form.communication_score, form.problem_solving_score, form.interview_outcome])

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)

    const payload = {
      student_id: candidate.student_id,
      job_id: job.id,
      round_number: 1,
      round_name: form.round_name,
      technical_score: parseFloat(form.technical_score),
      communication_score: parseFloat(form.communication_score),
      problem_solving_score: parseFloat(form.problem_solving_score),
      strengths: form.strengths,
      weaknesses: form.weaknesses,
      detailed_feedback: form.detailed_feedback,
      interview_outcome: form.interview_outcome,
      improvement_recommendations: suggestedText?.recommendations || [],
    }

    try {
      const res = await apiRequest('/api/v1/interviews/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      })
      onSuccess(res)
    } catch (err) {
      setError(err.message || 'Failed to submit interview feedback.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(23, 32, 51, 0.6)',
      display: 'grid', placeItems: 'center', zIndex: 1000, padding: '20px'
    }}>
      <div className="explainability-card" style={{ maxWidth: '650px', width: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.4rem' }}>Log Interview Feedback</h2>
            <p className="muted" style={{ margin: 0 }}>
              Candidate: <strong>{candidate.full_name || candidate.roll_number}</strong> &bull; Job: <strong>{job.title}</strong>
            </p>
          </div>
          <button className="logout-button" style={{ padding: '6px 12px' }} onClick={onClose}>✕</button>
        </div>

        {error && <ErrorBlock message={error} />}

        <form onSubmit={handleSubmit} className="auth-form" style={{ gap: '14px' }}>
          <div className="filter-row" style={{ padding: 0, border: 'none', background: 'transparent' }}>
            <label className="field filter-field">
              <span>Interview Round</span>
              <select value={form.round_name} onChange={(e) => setForm({ ...form, round_name: e.target.value })}>
                <option value="Technical Round 1">Technical Round 1</option>
                <option value="System Design">System Design</option>
                <option value="Coding Assessment">Coding Assessment</option>
                <option value="HR & Culture Fit">HR & Culture Fit</option>
              </select>
            </label>

            <label className="field filter-field">
              <span>Decision Outcome *</span>
              <select
                value={form.interview_outcome}
                onChange={(e) => setForm({ ...form, interview_outcome: e.target.value })}
              >
                <option value="passed">PASSED (Select / Promote)</option>
                <option value="on_hold">ON HOLD (Pending Review)</option>
                <option value="failed">FAILED (Reject)</option>
              </select>
            </label>
          </div>

          <div style={{ background: '#f7f9fc', padding: '14px', borderRadius: '10px', display: 'grid', gap: '12px' }}>
            <label className="field">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Technical Ability (1 - 10)</span>
                <strong>{form.technical_score} / 10</strong>
              </div>
              <input
                type="range" min="1" max="10" step="0.5"
                value={form.technical_score}
                onChange={(e) => setForm({ ...form, technical_score: e.target.value })}
              />
            </label>

            <label className="field">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Communication Skills (1 - 10)</span>
                <strong>{form.communication_score} / 10</strong>
              </div>
              <input
                type="range" min="1" max="10" step="0.5"
                value={form.communication_score}
                onChange={(e) => setForm({ ...form, communication_score: e.target.value })}
              />
            </label>

            <label className="field">
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Problem Solving &amp; Logic (1 - 10)</span>
                <strong>{form.problem_solving_score} / 10</strong>
              </div>
              <input
                type="range" min="1" max="10" step="0.5"
                value={form.problem_solving_score}
                onChange={(e) => setForm({ ...form, problem_solving_score: e.target.value })}
              />
            </label>
          </div>

          {/* Template Suggestions Preview */}
          {suggestedText && (
            <div style={{ background: '#f0f7ff', borderLeft: '4px solid #1959b8', padding: '10px 12px', borderRadius: '6px', fontSize: '0.84rem' }}>
              <strong style={{ color: '#1959b8' }}>AI Template Suggestion:</strong> {suggestedText.suggested_summary}
            </div>
          )}

          <label className="field">
            <span>Observed Strengths</span>
            <input
              value={form.strengths}
              onChange={(e) => setForm({ ...form, strengths: e.target.value })}
            />
          </label>

          <label className="field">
            <span>Areas for Improvement / Weaknesses</span>
            <input
              value={form.weaknesses}
              onChange={(e) => setForm({ ...form, weaknesses: e.target.value })}
            />
          </label>

          <label className="field">
            <span>Detailed Recruiter Notes</span>
            <textarea
              rows={3}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd6e6', borderRadius: '6px', font: 'inherit' }}
              value={form.detailed_feedback}
              onChange={(e) => setForm({ ...form, detailed_feedback: e.target.value })}
            />
          </label>

          <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '12px' }}>
            <button className="logout-button" type="button" onClick={onClose}>Cancel</button>
            <button className="primary-button" type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Saving Feedback…' : 'Submit Feedback'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ----- Modal for Sentence-BERT Semantic Alignment & Hybrid Score ------------

export function SemanticMatchModal({ candidate, jobId, onClose, token }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const res = await apiRequest(`/api/v1/matching/semantic/${jobId}?limit=500`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        if (!cancelled) {
          const matchedCandidate = (res?.candidates || []).find(
            (c) => c.student_id === candidate.student_id
          )
          setData(matchedCandidate || null)
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load semantic match details.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [candidate.student_id, jobId, token])

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(23, 32, 51, 0.65)',
      display: 'grid', placeItems: 'center', zIndex: 1000, padding: '20px'
    }}>
      <div className="explainability-card" style={{ maxWidth: '780px', width: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.4rem' }}>🧠 Hybrid Semantic Match</h2>
            <p className="muted" style={{ margin: 0 }}>
              Candidate: <strong>{candidate.full_name || candidate.roll_number}</strong> &bull; Roll: <code>{candidate.roll_number}</code>
            </p>
          </div>
          <button className="logout-button" style={{ padding: '6px 12px', border: 'none', cursor: 'pointer' }} onClick={onClose}>✕</button>
        </div>

        {error && <ErrorBlock message={error} />}
        {loading ? (
          <LoadingBlock label="Computing SBERT sentence embeddings & cosine alignment..." />
        ) : data ? (
          <div>
            {/* Score Badges */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '20px' }}>
              <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 600, display: 'block' }}>TF-IDF Domain Confidence</span>
                <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0f172a' }}>{(data.domain_confidence * 100).toFixed(1)}%</span>
              </div>
              <div style={{ background: '#eff6ff', padding: '12px', borderRadius: '8px', border: '1px solid #bfdbfe' }}>
                <span style={{ fontSize: '0.78rem', color: '#1d4ed8', fontWeight: 600, display: 'block' }}>SBERT Semantic Score</span>
                <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#1e40af' }}>{(data.semantic_score * 100).toFixed(1)}%</span>
              </div>
              <div style={{ background: '#f0fdf4', padding: '12px', borderRadius: '8px', border: '1px solid #bbf7d0' }}>
                <span style={{ fontSize: '0.78rem', color: '#15803d', fontWeight: 600, display: 'block' }}>Hybrid Score (0.6 / 0.4)</span>
                <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#166534' }}>{data.hybrid_score.toFixed(3)}</span>
              </div>
            </div>

            {/* Sentence-Level Alignment Table */}
            <h3 style={{ fontSize: '1.05rem', marginBottom: '6px' }}>Sentence-Level Semantic Alignment</h3>
            <p className="muted" style={{ fontSize: '0.85rem', marginTop: 0, marginBottom: '14px' }}>
              Sentence-BERT pairwise similarity mapping Job Description requirements against candidate resume sentences.
            </p>

            {(!data.sentence_alignments || data.sentence_alignments.length === 0) ? (
              <EmptyState message="No sentence-level alignments found." />
            ) : (
              <div className="table-wrap">
                <table className="data-table" style={{ fontSize: '0.85rem' }}>
                  <thead>
                    <tr>
                      <th style={{ width: '40%' }}>JD Requirement Sentence</th>
                      <th style={{ width: '45%' }}>Matched Resume Sentence</th>
                      <th style={{ width: '15%', textAlign: 'center' }}>Similarity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.sentence_alignments.map((align, idx) => (
                      <tr key={idx}>
                        <td style={{ fontWeight: 600, color: '#334155' }}>{align.jd_requirement}</td>
                        <td style={{ color: '#475569' }}>{align.best_matching_resume_sentence}</td>
                        <td style={{ textAlign: 'center' }}>
                          <span style={{
                            padding: '3px 8px', borderRadius: '12px', fontSize: '0.8rem', fontWeight: 700,
                            background: align.similarity_score >= 0.6 ? '#dcfce7' : align.similarity_score >= 0.4 ? '#fef9c3' : '#f1f5f9',
                            color: align.similarity_score >= 0.6 ? '#15803d' : align.similarity_score >= 0.4 ? '#854d0e' : '#475569',
                          }}>
                            {(align.similarity_score * 100).toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <EmptyState message="Semantic match data not available for this candidate." />
        )}
      </div>
    </div>
  )
}

// ----- 3. Candidate Shortlist View (Strict vs Buffer Match) ----------------

export function CandidateShortlistPage() {
  const { auth } = useAuth()
  const { jobId } = useParams()
  const id = Number(jobId)

  const [job, setJob] = useState(null)
  const [matchResults, setMatchResults] = useState(null)
  const [limit, setLimit] = useState(200) // Default limit set to 200 so full candidate pool is visible
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [semanticCandidate, setSemanticCandidate] = useState(null)
  const [feedbackSuccessMsg, setFeedbackSuccessMsg] = useState('')

  useEffect(() => {
    if (!Number.isFinite(id)) return
    let cancelled = false

    async function loadData() {
      setLoading(true)
      setError('')
      try {
        const [jobData, shortlistData] = await Promise.all([
          apiRequest(`/api/v1/jobs/${id}`, {
            headers: { Authorization: `Bearer ${auth.token}` },
          }),
          apiRequest(`/api/v1/matching/jobs/${id}/baseline-candidates?include_buffer=true&buffer_min_confidence=0.70&limit=${limit}`, {
            headers: { Authorization: `Bearer ${auth.token}` },
          }),
        ])
        if (!cancelled) {
          setJob(jobData)
          setMatchResults(shortlistData)
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load candidate shortlist.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadData()
    return () => { cancelled = true }
  }, [auth.token, id, limit])

  if (!Number.isFinite(id)) return <ErrorBlock message="Invalid job id." />

  const strictCandidates = matchResults?.matches?.filter((m) => m.match_tier === 'strict_match') || []
  const bufferCandidates = matchResults?.matches?.filter((m) => m.match_tier === 'buffer_match') || []

  return (
    <div className="recruiter-glass-theme">
      <RecruiterSubNav />
      <Link to="/recruiter/jobs" className="back-link">← Back to My Job Postings</Link>

      {error && <ErrorBlock message={error} />}
      {feedbackSuccessMsg && (
        <div style={{ background: '#d6f5e3', color: '#1d6b3d', padding: '12px 16px', borderRadius: '8px', marginBottom: '16px', fontWeight: 650 }}>
          {feedbackSuccessMsg}
        </div>
      )}

      {loading ? (
        <LoadingBlock label="Evaluating candidates with AI matching algorithms…" />
      ) : (
        <>
          <header className="dashboard-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div>
              <p className="eyebrow">AI Candidate Shortlist</p>
              <h1>{job?.title || `Job #${id}`}</h1>
              <p className="muted">
                Target Domain: <strong>{job?.target_domain}</strong> &bull; Min CGPA: <strong>{formatCgpa(job?.min_cgpa)}</strong> &bull; Max Backlogs: <strong>{job?.max_backlogs_allowed}</strong> &bull; Buffer Threshold: <strong>{job?.buffer_threshold_percent}%</strong>
              </p>
            </div>

            {/* Pagination & Limit Selector Control */}
            <div className="field" style={{ minWidth: '160px' }}>
              <span>Show Candidate Pool</span>
              <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
                <option value="50">Top 50 Candidates</option>
                <option value="100">Top 100 Candidates</option>
                <option value="200">Top 200 Candidates</option>
                <option value="500">All 500 Candidates</option>
              </select>
            </div>
          </header>

          <section className="stat-grid">
            <StatCard
              label="Total candidates evaluated"
              value={matchResults?.total_candidates_evaluated ?? 0}
              hint="Cross-checked against criteria"
            />
            <StatCard
              label="Strict matches"
              value={matchResults?.strict_matches_count ?? 0}
              hint="Passed hard CGPA & backlog filters"
            />
            <StatCard
              label="Buffer matches (AI Promoted)"
              value={matchResults?.buffer_matches_count ?? 0}
              hint="Recovered via AI domain-fit gate"
            />
          </section>

          {/* Section 1: Strict Match Candidates */}
          <section style={{ marginBottom: '32px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <h2 style={{ margin: 0, fontSize: '1.3rem' }}>Strict Match Candidates</h2>
              <span className="badge badge-good" style={{ fontSize: '0.85rem' }}>
                Showing {strictCandidates.length} of {matchResults?.strict_matches_count ?? 0} Strict Matches
              </span>
            </div>
            <p className="muted" style={{ marginTop: 0, marginBottom: '16px' }}>
              Candidates meeting all baseline CGPA and backlog constraints.
            </p>

            {strictCandidates.length === 0 ? (
              <EmptyState message="No candidates met the strict academic filters." />
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Candidate</th>
                      <th>Dept & CGPA</th>
                      <th>Overall Score</th>
                      <th>Academic</th>
                      <th>Skill Match</th>
                      <th>Domain Fit</th>
                      <th>Skills (Matched / Missing)</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {strictCandidates.map((c) => (
                      <tr key={c.student_id}>
                        <td>
                          <strong>{c.full_name || `Student #${c.student_id}`}</strong>
                          <br />
                          <span className="mono muted" style={{ fontSize: '0.8rem' }}>{c.roll_number}</span>
                        </td>
                        <td>
                          {c.department}
                          <br />
                          <strong>CGPA: {formatCgpa(c.cgpa)}</strong>
                        </td>
                        <td>
                          <span style={{ fontSize: '1.1rem', fontWeight: 800, color: '#1959b8' }}>
                            {c.overall_score.toFixed(3)}
                          </span>
                        </td>
                        <td>{c.academic_score.toFixed(2)}</td>
                        <td>{c.skill_match_score.toFixed(2)}</td>
                        <td>{c.domain_fit_score > 0 ? `${(c.domain_fit_score * 100).toFixed(0)}%` : '0%'}</td>
                        <td>
                          <div style={{ marginBottom: '4px' }}>
                            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#1d6b3d' }}>Matched: </span>
                            <span className="muted" style={{ fontSize: '0.8rem' }}>
                              {(c.matching_skills || []).join(', ') || 'None'}
                            </span>
                          </div>
                          {c.missing_skills?.length > 0 && (
                            <div>
                              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#8a1d29' }}>Missing: </span>
                              <span className="muted" style={{ fontSize: '0.8rem' }}>
                                {c.missing_skills.join(', ')}
                              </span>
                            </div>
                          )}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                            <button
                              className="link-button"
                              style={{ border: 'none', cursor: 'pointer' }}
                              onClick={() => setSelectedCandidate(c)}
                            >
                              Log Feedback
                            </button>
                            <button
                              className="link-button"
                              style={{ border: 'none', cursor: 'pointer', color: '#1d4ed8' }}
                              onClick={() => setSemanticCandidate(c)}
                            >
                              🧠 Semantic Match
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Section 2: Adaptive Buffer Match Candidates */}
          <section style={{ marginBottom: '32px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
              <h2 style={{ margin: 0, fontSize: '1.3rem' }}>
                Adaptive Buffer Matches <span style={{ color: '#b58a1c', fontWeight: 600 }}>(AI Novelty Feature)</span>
              </h2>
              <span className="badge badge-buffer" style={{ fontSize: '0.85rem', background: '#fdf9ef', color: '#b58a1c', border: '1px solid #f5e5bd' }}>
                Showing {bufferCandidates.length} of {matchResults?.buffer_matches_count ?? 0} AI-Promoted Candidates
              </span>
            </div>
            <p className="muted" style={{ marginTop: 0, marginBottom: '16px' }}>
              Candidates who narrowly missed strict CGPA/backlog thresholds but were rescued by exceptional AI domain fit confidence (&ge; 70%).
            </p>

            {bufferCandidates.length === 0 ? (
              <EmptyState message="No candidates met the adaptive buffer promotion criteria." />
            ) : (
              <div className="table-wrap" style={{ border: '2px solid #f5e5bd' }}>
                <table className="data-table">
                  <thead>
                    <tr style={{ background: '#fdfbf5' }}>
                      <th>Candidate</th>
                      <th>Dept & CGPA</th>
                      <th>Overall Score</th>
                      <th>Domain Fit Score</th>
                      <th>Score Breakdown</th>
                      <th>Skills Matched</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bufferCandidates.map((c) => (
                      <tr key={c.student_id} style={{ background: '#fffdf9' }}>
                        <td>
                          <strong>{c.full_name || `Student #${c.student_id}`}</strong>
                          <br />
                          <span className="mono muted" style={{ fontSize: '0.8rem' }}>{c.roll_number}</span>
                        </td>
                        <td>
                          {c.department}
                          <br />
                          <strong>CGPA: {formatCgpa(c.cgpa)}</strong>
                          <br />
                          <span style={{ fontSize: '0.75rem', color: '#b58a1c', fontWeight: 600 }}>
                            {c.active_backlogs > job?.max_backlogs_allowed ? `${c.active_backlogs} backlogs` : 'Within buffer'}
                          </span>
                        </td>
                        <td>
                          <span style={{ fontSize: '1.1rem', fontWeight: 800, color: '#b58a1c' }}>
                            {c.overall_score.toFixed(3)}
                          </span>
                        </td>
                        <td>
                          <span className="badge badge-good" style={{ background: '#d6f5e3', color: '#1d6b3d', fontSize: '0.85rem' }}>
                            {(c.domain_fit_score * 100).toFixed(1)}% Confidence
                          </span>
                        </td>
                        <td>
                          <div style={{ fontSize: '0.78rem', lineHeight: '1.4' }}>
                            <div>Acad: <strong>{c.score_breakdown?.academic_weight}</strong></div>
                            <div>Skill: <strong>{c.score_breakdown?.skill_weight}</strong></div>
                            <div>Domain: <strong>{c.score_breakdown?.domain_weight}</strong></div>
                          </div>
                        </td>
                        <td>
                          <div className="skill-chips">
                            {(c.matching_skills || []).map((s) => (
                              <span key={s} className="chip" style={{ background: '#fef3d6', color: '#7a5a07' }}>{s}</span>
                            ))}
                          </div>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                            <button
                              className="link-button"
                              style={{ border: 'none', cursor: 'pointer', background: '#fdf3d6', color: '#856404' }}
                              onClick={() => setSelectedCandidate(c)}
                            >
                              Log Feedback
                            </button>
                            <button
                              className="link-button"
                              style={{ border: 'none', cursor: 'pointer', color: '#1d4ed8' }}
                              onClick={() => setSemanticCandidate(c)}
                            >
                              🧠 Semantic Match
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

      {/* Render Modal when candidate is selected */}
      {selectedCandidate && job && (
        <InterviewFeedbackModal
          candidate={selectedCandidate}
          job={job}
          token={auth.token}
          onClose={() => setSelectedCandidate(null)}
          onSuccess={(res) => {
            setSelectedCandidate(null)
            setFeedbackSuccessMsg(`Interview feedback successfully logged for ${res.student_name || 'candidate'}! Decision: ${res.interview_outcome.toUpperCase()}`)
            setTimeout(() => setFeedbackSuccessMsg(''), 5000)
          }}
        />
      )}

      {/* Render Semantic Match Modal when candidate is clicked */}
      {semanticCandidate && job && (
        <SemanticMatchModal
          candidate={semanticCandidate}
          jobId={job.id}
          token={auth.token}
          onClose={() => setSemanticCandidate(null)}
        />
      )}
    </div>
  )
}
