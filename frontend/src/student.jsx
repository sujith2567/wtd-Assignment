import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { apiRequest, useAuth } from './api.jsx'
import { StatCard, LoadingBlock, ErrorBlock, EmptyState, formatPercent, formatCgpa } from './components.jsx'

export function StudentSubNav() {
  const tabs = [
    { to: '/student/profile', label: 'My Profile & AI Explanation' },
    { to: '/student/recommendations', label: 'Recommended Jobs' },
    { to: '/student/interviews', label: 'My Interview Outcomes' },
    { to: '/student/alumni', label: 'Placed Alumni Insights' },
    { to: '/student/readiness', label: 'Readiness Check' },
    { to: '/student/applications', label: 'My Applications' },
  ]
  return (
    <nav className="admin-tabs" aria-label="Student sections">
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

// ----- 1. Student Profile & Domain Explanation Page ------------------------

export function StudentProfilePage() {
  const { auth } = useAuth()
  const [profile, setProfile] = useState(null)
  const [explanation, setExplanation] = useState(null)
  const [shapData, setShapData] = useState(null)
  const [anomalyData, setAnomalyData] = useState(null)
  const [improveData, setImproveData] = useState(null)

  const [loadingProfile, setLoadingProfile] = useState(true)
  const [loadingExplanation, setLoadingExplanation] = useState(true)
  const [profileError, setProfileError] = useState('')
  const [explanationError, setExplanationError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadProfile() {
      setLoadingProfile(true)
      setProfileError('')
      try {
        const data = await apiRequest('/api/v1/students/profile', {
          headers: { Authorization: `Bearer ${auth.token}` },
        })
        if (!cancelled) {
          setProfile(data)
          loadExplanation(data.id)
        }
      } catch (err) {
        if (!cancelled) setProfileError(err.message || 'Failed to load profile.')
      } finally {
        if (!cancelled) setLoadingProfile(false)
      }
    }

    async function loadExplanation(studentId) {
      setLoadingExplanation(true)
      setExplanationError('')
      try {
        const [explRes, shapRes, anomalyRes, improveRes] = await Promise.allSettled([
          apiRequest(`/api/v1/matching/student/${studentId}/explanation`, { headers: { Authorization: `Bearer ${auth.token}` } }),
          apiRequest(`/api/v1/explain/shap-compare/${studentId}`, { headers: { Authorization: `Bearer ${auth.token}` } }),
          apiRequest(`/api/v1/audit/anomaly-score/${studentId}`, { headers: { Authorization: `Bearer ${auth.token}` } }),
          apiRequest(`/api/v1/explain/improve/${studentId}`, { headers: { Authorization: `Bearer ${auth.token}` } })
        ])

        if (!cancelled) {
          if (explRes.status === 'fulfilled') setExplanation(explRes.value)
          if (shapRes.status === 'fulfilled') setShapData(shapRes.value.shap_analysis)
          if (anomalyRes.status === 'fulfilled') setAnomalyData(anomalyRes.value.anomaly_audit)
          if (improveRes.status === 'fulfilled') setImproveData(improveRes.value.improvement_analysis)
        }
      } catch (err) {
        if (!cancelled) setExplanationError(err.message || 'Failed to load AI explanation.')
      } finally {
        if (!cancelled) setLoadingExplanation(false)
      }
    }

    loadProfile()
    return () => { cancelled = true }
  }, [auth.token])

  return (
    <>
      <StudentSubNav />
      <header className="dashboard-header">
        <p className="eyebrow">Student Portal</p>
        <h1>My Profile &amp; AI Domain Classification</h1>
        <p className="muted">View your academic credentials and transparent AI feature attribution.</p>
      </header>

      {profileError && <ErrorBlock message={profileError} />}

      {loadingProfile ? (
        <LoadingBlock label="Loading... profile data…" />
      ) : profile ? (
        <>
          {/* Academic Overview Cards */}
          <section className="detail-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', marginBottom: '24px' }}>
            <article className="detail-card">
              <p className="stat-label">Full Name</p>
              <p className="stat-value">{profile.full_name || auth.user.fullName}</p>
            </article>
            <article className="detail-card">
              <p className="stat-label">Roll Number</p>
              <p className="stat-value mono">{profile.roll_number}</p>
            </article>
            <article className="detail-card">
              <p className="stat-label">Department</p>
              <p className="stat-value">{profile.department}</p>
            </article>
            <article className="detail-card">
              <p className="stat-label">CGPA</p>
              <p className="stat-value" style={{ color: '#1959b8', fontWeight: 800 }}>{formatCgpa(profile.cgpa)}</p>
            </article>
            <article className="detail-card">
              <p className="stat-label">Active Backlogs</p>
              <p className="stat-value">{profile.active_backlogs}</p>
            </article>
            <article className="detail-card">
              <p className="stat-label">Batch Year</p>
              <p className="stat-value">{profile.batch_year}</p>
            </article>
          </section>

          {/* Skills & Resume Info */}
          <section className="detail-grid" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: '28px' }}>
            <article className="detail-card" style={{ gridColumn: 'span 1' }}>
              <p className="stat-label" style={{ marginBottom: '8px' }}>Skills Inventory</p>
              <div className="skill-chips">
                {(profile.skills || []).length > 0 ? (
                  profile.skills.map((s) => (
                    <span key={s} className="chip">{s}</span>
                  ))
                ) : (
                  <span className="muted">No skills listed yet</span>
                )}
              </div>
            </article>

            <article className="detail-card" style={{ gridColumn: 'span 1' }}>
              <p className="stat-label" style={{ marginBottom: '8px' }}>Resume Text Snippet</p>
              <p className="muted" style={{ fontSize: '0.85rem', lineHeight: '1.4', margin: 0, maxHeight: '80px', overflowY: 'auto' }}>
                {profile.raw_resume_text || 'No resume text uploaded.'}
              </p>
            </article>
          </section>

          {/* Prominent Novelty Feature: AI Explainability View */}
          <section className="explainability-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
              <div>
                <h2>AI Domain Classification &amp; Explainability</h2>
                <p className="muted" style={{ margin: 0 }}>
                  Transparent breakdown of why the machine learning classifier predicted your primary domain.
                </p>
              </div>
              <span className="badge badge-good" style={{ fontSize: '0.85rem', padding: '6px 12px' }}>
                Novelty Feature
              </span>
            </div>

            {explanationError && <ErrorBlock message={explanationError} />}

            {loadingExplanation ? (
              <LoadingBlock label="Computing AI feature attributions…" />
            ) : explanation ? (
              <>
                <div className="explanation-headline" style={{ marginTop: '20px' }}>
                  <div>
                    <p className="stat-label">Predicted Domain</p>
                    <p className="stat-value" style={{ color: '#1959b8' }}>{explanation.predicted_domain}</p>
                  </div>
                  <div>
                    <p className="stat-label">Confidence Score</p>
                    <p className="stat-value">{formatPercent(explanation.confidence_score)}</p>
                  </div>
                  <div>
                    <p className="stat-label">Ground-Truth Label</p>
                    <p className="stat-value">
                      {explanation.ground_truth_domain || '—'}
                      {explanation.is_correct === true && <span className="badge badge-good"> match</span>}
                      {explanation.is_correct === false && <span className="badge badge-bad"> mismatch</span>}
                    </p>
                  </div>
                  <div>
                    <p className="stat-label">Model Version</p>
                    <p className="stat-value mono">{explanation.model_version}</p>
                  </div>
                </div>

                <p className="summary-text" style={{ fontSize: '0.98rem' }}>
                  {explanation.human_readable_summary}
                </p>

                <h3>Class Probabilities Distribution</h3>
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

                <h3>Top Contributing Skill &amp; Resume Keywords</h3>
                <ul className="factor-list">
                  {explanation.top_contributing_factors.map((f, idx) => (
                    <li key={`${f.keyword}-${idx}`} className={`factor factor-${f.direction}`}>
                      <div className="factor-head">
                        <span className="factor-keyword">{f.keyword}</span>
                        <span className="factor-weight">Attribution Weight: {f.weight}</span>
                      </div>
                      <p className="factor-desc">{f.description}</p>
                      <p className="factor-direction">{f.direction.replace('_', ' ')}</p>
                    </li>
                  ))}
                </ul>

                {/* Novelty 1: Isolation Forest Profile Integrity Audit */}
                {anomalyData && (
                  <div style={{ marginTop: '28px', paddingTop: '20px', borderTop: '1px solid #dfe6f2' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3 style={{ margin: 0, color: '#172033' }}>🌲 Profile Integrity &amp; Anomaly Audit</h3>
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
                    <h3 style={{ margin: '0 0 10px', color: '#172033' }}>📊 SHAP Resume-vs-Database Distribution Comparison</h3>
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
                        <span key={s} className="chip" style={{ background: '#e6f0ff', color: '#1959b8' }}>✓ {s}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Novelty 3: How to Improve Your Match Recommendations */}
                {improveData && (
                  <div style={{ marginTop: '24px', paddingTop: '20px', borderTop: '1px solid #dfe6f2' }}>
                    <h3 style={{ margin: '0 0 4px', color: '#172033' }}>🚀 How to Improve Your Placement Match Score</h3>
                    <p className="muted" style={{ margin: '0 0 14px' }}>
                      Targeted skill suggestions calculated from missing SHAP feature contributions for <strong>{improveData.target_domain}</strong>.
                    </p>
                    <div style={{ display: 'grid', gap: '10px' }}>
                      {improveData.recommendations.map((rec) => (
                        <div key={rec.rank} style={{ background: '#f8fbff', border: '1px solid #cce0ff', borderLeft: '4px solid #1959b8', padding: '12px 14px', borderRadius: '8px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                            <strong style={{ color: '#1959b8', fontSize: '.92rem' }}>#{rec.rank} Add Skill / Keyword: "{rec.suggested_skill}"</strong>
                            <span className="chip" style={{ background: '#e6f0ff', color: '#1959b8', fontWeight: 700 }}>Potential Gain: +{(rec.potential_shap_gain * 100).toFixed(1)}%</span>
                          </div>
                          <p style={{ margin: 0, fontSize: '.88rem', color: '#44536b' }}>{rec.reason}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : null}
          </section>
        </>
      ) : null}
      <StudentExplainabilityChatbot />
    </>
  )
}

// ----- 2. Job / Company Recommendations Page (Strict + Buffer Split) ---------

export function StudentRecommendationsPage() {
  const { auth } = useAuth()
  const [_profile, setProfile] = useState(null)
  const [explanation, setExplanation] = useState(null)
  const [directJobs, setDirectJobs] = useState([])
  const [bufferJobs, setBufferJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadData() {
      setLoading(true)
      setError('')
      try {
        const student = await apiRequest('/api/v1/students/profile', {
          headers: { Authorization: `Bearer ${auth.token}` },
        })
        if (cancelled) return
        setProfile(student)

        const expl = await apiRequest(`/api/v1/matching/student/${student.id}/explanation`, {
          headers: { Authorization: `Bearer ${auth.token}` },
        })
        if (cancelled) return
        setExplanation(expl)

        const allJobs = await apiRequest('/api/v1/jobs/?limit=100', {
          headers: { Authorization: `Bearer ${auth.token}` },
        })
        if (cancelled) return

        const sDomain = (expl.predicted_domain || '').toLowerCase().trim()
        const sConfidence = expl.confidence_score || 0.0
        const sCgpa = parseFloat(student.cgpa || 0)
        const sBacklogs = student.active_backlogs || 0
        const sSkillsSet = new Set((student.skills || []).map((s) => s.trim().toLowerCase()))

        const direct = []
        const buffer = []

        allJobs.forEach((job) => {
          const jDomain = (job.target_domain || '').toLowerCase().trim()
          const isDomainMatch = sDomain && jDomain && (sDomain === jDomain || jDomain.includes(sDomain) || sDomain.includes(jDomain))
          
          const minCgpa = parseFloat(job.min_cgpa || 0)
          const maxBacklogs = job.max_backlogs_allowed || 0
          const bufferPct = parseFloat(job.buffer_threshold_percent || 10.0)
          const bufferCgpaFloor = minCgpa * (1.0 - bufferPct / 100.0)

          const meetsStrict = (sCgpa >= minCgpa) && (sBacklogs <= maxBacklogs)
          const meetsBuffer = (sCgpa >= bufferCgpaFloor) && (sBacklogs <= maxBacklogs + 1) && (sConfidence >= 0.70)

          const reqSkills = (job.required_skills || []).map((s) => s.trim().toLowerCase())
          const matchedSkills = reqSkills.filter((s) => sSkillsSet.has(s))

          if (isDomainMatch && meetsStrict) {
            direct.push({
              ...job,
              matchedSkillsCount: matchedSkills.length,
              totalReqSkillsCount: reqSkills.length,
              matchReason: `Direct match for predicted domain (${expl.predicted_domain}) & meets CGPA (${sCgpa.toFixed(2)} >= ${minCgpa.toFixed(2)})`,
            })
          } else if (isDomainMatch && meetsBuffer) {
            const gapNote = []
            if (sCgpa < minCgpa) gapNote.append(`CGPA ${sCgpa.toFixed(2)} vs min ${minCgpa.toFixed(2)}`)
            if (sBacklogs > maxBacklogs) gapNote.append(`${sBacklogs} active backlogs`)
            buffer.push({
              ...job,
              matchedSkillsCount: matchedSkills.length,
              totalReqSkillsCount: reqSkills.length,
              matchReason: `AI Promoted via high domain confidence (${(sConfidence*100).toFixed(0)}% >= 70%). ${gapNote.join('; ')} within adaptive buffer criteria.`,
            })
          }
        })

        setDirectJobs(direct)
        setBufferJobs(buffer)

      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load job recommendations.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadData()
    return () => { cancelled = true }
  }, [auth.token])

  return (
    <>
      <StudentSubNav />
      <header className="dashboard-header">
        <p className="eyebrow">Placement Opportunities</p>
        <h1>AI Job &amp; Company Recommendations</h1>
        <p className="muted">
          Jobs matched to your predicted domain (<strong>{explanation?.predicted_domain || 'Loading...'}</strong> &bull; {(explanation?.confidence_score * 100 || 0).toFixed(1)}% Confidence).
        </p>
      </header>

      {error && <ErrorBlock message={error} />}

      {loading ? (
        <LoadingBlock label="Matching open jobs to your AI domain classification…" />
      ) : (
        <>
          {/* Section 1: Direct Eligible Jobs */}
          <section style={{ marginBottom: '32px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <h2 style={{ margin: 0, fontSize: '1.3rem' }}>Direct Eligible Job Matches</h2>
              <span className="badge badge-good" style={{ fontSize: '0.85rem' }}>
                {directJobs.length} Jobs
              </span>
            </div>

            {directJobs.length === 0 ? (
              <EmptyState message="No direct domain matches meeting strict CGPA requirements found." />
            ) : (
              <div style={{ display: 'grid', gap: '18px', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
                {directJobs.map((job) => (
                  <article key={job.id} className="explainability-card" style={{ padding: '20px', border: '1px solid #cce0ff', background: '#fafcff' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <h3 style={{ margin: '0 0 4px', fontSize: '1.15rem', color: '#172033' }}>{job.title}</h3>
                        <p className="muted" style={{ margin: 0, fontWeight: 700, color: '#1959b8' }}>{job.company_name}</p>
                      </div>
                      <span className="badge badge-good" style={{ fontSize: '0.75rem' }}>Direct Match</span>
                    </div>

                    <div style={{ margin: '12px 0', fontSize: '0.86rem', display: 'grid', gap: '4px' }}>
                      <div>Domain: <strong>{job.target_domain}</strong></div>
                      <div>Location: <strong>{job.location || 'Remote'}</strong> &bull; Salary: <strong>{job.salary_range || 'N/A'}</strong></div>
                      <div>Min CGPA: <strong>{formatCgpa(job.min_cgpa)}</strong> | Max Backlogs: <strong>{job.max_backlogs_allowed}</strong></div>
                    </div>

                    <div style={{ marginBottom: '12px' }}>
                      <div className="skill-chips">
                        {(job.required_skills || []).map((s) => (
                          <span key={s} className="chip" style={{ background: '#eef3fb' }}>{s}</span>
                        ))}
                      </div>
                    </div>

                    <div style={{ background: '#f0f7ff', padding: '8px 10px', borderRadius: '6px', borderLeft: '3px solid #1959b8', fontSize: '0.82rem', color: '#1d2f4d' }}>
                      {job.matchReason}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          {/* Section 2: Adaptive Buffer Job Recommendations */}
          <section style={{ marginBottom: '32px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <h2 style={{ margin: 0, fontSize: '1.3rem' }}>
                Adaptive Buffer Job Recommendations <span style={{ color: '#b58a1c', fontWeight: 600 }}>(AI Promoted)</span>
              </h2>
              <span className="badge badge-buffer" style={{ fontSize: '0.85rem', background: '#fdf9ef', color: '#b58a1c', border: '1px solid #f5e5bd' }}>
                {bufferJobs.length} AI-Promoted Jobs
              </span>
            </div>
            <p className="muted" style={{ marginTop: 0, marginBottom: '14px' }}>
              Jobs where your domain fit confidence (&ge; 70%) clears you for recruiter buffer evaluation even if CGPA/backlogs are slightly outside strict limits.
            </p>

            {bufferJobs.length === 0 ? (
              <EmptyState message="No additional buffer-promoted job opportunities at this time." />
            ) : (
              <div style={{ display: 'grid', gap: '18px', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
                {bufferJobs.map((job) => (
                  <article key={job.id} className="explainability-card" style={{ padding: '20px', border: '2px solid #f5e5bd', background: '#fffdf9' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <h3 style={{ margin: '0 0 4px', fontSize: '1.15rem', color: '#172033' }}>{job.title}</h3>
                        <p className="muted" style={{ margin: 0, fontWeight: 700, color: '#b58a1c' }}>{job.company_name}</p>
                      </div>
                      <span className="badge badge-buffer" style={{ background: '#fdf9ef', color: '#b58a1c', border: '1px solid #f5e5bd', fontSize: '0.75rem' }}>
                        AI Buffer Match
                      </span>
                    </div>

                    <div style={{ margin: '12px 0', fontSize: '0.86rem', display: 'grid', gap: '4px' }}>
                      <div>Domain: <strong>{job.target_domain}</strong></div>
                      <div>Location: <strong>{job.location || 'Remote'}</strong> &bull; Salary: <strong>{job.salary_range || 'N/A'}</strong></div>
                      <div>Strict Requirements: Min CGPA <strong>{formatCgpa(job.min_cgpa)}</strong> | Max Backlogs: <strong>{job.max_backlogs_allowed}</strong></div>
                    </div>

                    <div style={{ marginBottom: '12px' }}>
                      <div className="skill-chips">
                        {(job.required_skills || []).map((s) => (
                          <span key={s} className="chip" style={{ background: '#fef3d6', color: '#7a5a07' }}>{s}</span>
                        ))}
                      </div>
                    </div>

                    <div style={{ background: '#fcf8ec', padding: '8px 10px', borderRadius: '6px', borderLeft: '3px solid #b58a1c', fontSize: '0.82rem', color: '#54410e' }}>
                      {job.matchReason}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </>
  )
}

// ----- 3. Student Interview Outcomes View ----------------------------------

export function StudentInterviewsPage() {
  const { auth } = useAuth()
  const [interviews, setInterviews] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setError('')
      try {
        const data = await apiRequest('/api/v1/interviews/my-interviews', {
          headers: { Authorization: `Bearer ${auth.token}` },
        })
        if (!cancelled) setInterviews(data)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load interview records.')
      }
    }
    load()
    return () => { cancelled = true }
  }, [auth.token])

  return (
    <>
      <StudentSubNav />
      <header className="dashboard-header">
        <p className="eyebrow">Campus Recruitment</p>
        <h1>My Interview Feedback &amp; Outcomes</h1>
        <p className="muted">Detailed recruiter ratings, round outcomes, and actionable recommendations.</p>
      </header>

      {error && <ErrorBlock message={error} />}

      {interviews == null ? (
        <LoadingBlock label="Loading... interview records…" />
      ) : interviews.length === 0 ? (
        <EmptyState message="No interview evaluation records logged for your profile yet." />
      ) : (
        <div style={{ display: 'grid', gap: '20px' }}>
          {interviews.map((item) => (
            <article key={item.id} className="explainability-card" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
                <div>
                  <h3 style={{ margin: '0 0 4px', fontSize: '1.3rem', color: '#172033' }}>{item.job_title}</h3>
                  <p className="muted" style={{ margin: 0, fontWeight: 700, color: '#1959b8' }}>
                    {item.company_name} &bull; Round: {item.round_name} (#{item.round_number})
                  </p>
                </div>
                <span className={`badge ${item.interview_outcome === 'passed' ? 'badge-good' : item.interview_outcome === 'on_hold' ? 'badge-buffer' : 'badge-bad'}`} style={{ fontSize: '0.9rem', padding: '6px 14px' }}>
                  {item.interview_outcome.toUpperCase()}
                </span>
              </div>

              <div className="explanation-headline" style={{ margin: '18px 0', padding: '14px' }}>
                <div>
                  <p className="stat-label">Technical Score</p>
                  <p className="stat-value" style={{ color: '#1959b8' }}>{item.technical_score} / 10</p>
                </div>
                <div>
                  <p className="stat-label">Communication Score</p>
                  <p className="stat-value">{item.communication_score} / 10</p>
                </div>
                <div>
                  <p className="stat-label">Problem Solving Score</p>
                  <p className="stat-value">{item.problem_solving_score} / 10</p>
                </div>
              </div>

              <div style={{ display: 'grid', gap: '12px', fontSize: '0.9rem' }}>
                {item.strengths && (
                  <div>
                    <strong style={{ color: '#1d6b3d' }}>Strengths: </strong>
                    <span>{item.strengths}</span>
                  </div>
                )}
                {item.weaknesses && (
                  <div>
                    <strong style={{ color: '#8a1d29' }}>Areas for Growth: </strong>
                    <span>{item.weaknesses}</span>
                  </div>
                )}
                {item.detailed_feedback && (
                  <div className="summary-text" style={{ margin: 0 }}>
                    <strong>Recruiter Summary: </strong>{item.detailed_feedback}
                  </div>
                )}
                {item.improvement_recommendations?.length > 0 && (
                  <div style={{ background: '#fdf9ef', borderLeft: '4px solid #b58a1c', padding: '10px 12px', borderRadius: '6px' }}>
                    <strong style={{ color: '#b58a1c' }}>Actionable Recommendations:</strong>
                    <ul style={{ margin: '4px 0 0', paddingLeft: '20px' }}>
                      {item.improvement_recommendations.map((rec, i) => (
                        <li key={i}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  )
}

// ----- 4. Placed Alumni Insights Page ---------------------------------------

export function StudentAlumniPage() {
  const { auth } = useAuth()
  const [alumni, setAlumni] = useState(null)
  const [search, setSearch] = useState('')
  const [domain, setDomain] = useState('')
  const [error, setError] = useState('')
  
  // Explainability modal state
  const [selectedAlumni, setSelectedAlumni] = useState(null)
  const [explanation, setExplanation] = useState(null)
  const [loadingExpl, setLoadingExpl] = useState(false)
  const [explError, setExplError] = useState('')

  async function load(qSearch = search, qDomain = domain) {
    setError('')
    try {
      const params = new URLSearchParams()
      if (qSearch.trim()) params.set('search', qSearch.trim())
      if (qDomain.trim()) params.set('domain', qDomain.trim())
      const data = await apiRequest(`/api/v1/placed-students/?${params.toString()}`, {
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      setAlumni(data)
    } catch (err) {
      setError(err.message || 'Failed to load placed alumni records.')
    }
  }

  useEffect(() => { load('', '') }, [auth.token]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleSearchSubmit(e) {
    e.preventDefault()
    load(search, domain)
  }

  function handleReset() {
    setSearch(''); setDomain(''); load('', '')
  }

  async function handleViewExplainability(item) {
    setSelectedAlumni(item)
    setExplanation(null)
    setLoadingExpl(true)
    setExplError('')

    try {
      const data = await apiRequest(`/api/v1/placed-students/${item.id}/explainability`, {
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      setExplanation(data)
    } catch (err) {
      setExplError(err.message || 'Failed to load explainability breakdown.')
    } finally {
      setLoadingExpl(false)
    }
  }

  return (
    <>
      <StudentSubNav />
      <header className="dashboard-header">
        <p className="eyebrow">Alumni Network</p>
        <h1>Placed Alumni Database &amp; Talent Insights</h1>
        <p className="muted">Explore successfully placed students, key skills/talents highlighted, and AI explainability breakdowns.</p>
      </header>

      <form className="filter-row" onSubmit={handleSearchSubmit}>
        <label className="field filter-field">
          <span>Search (name / company / role)</span>
          <input
            type="search"
            value={search}
            placeholder="e.g. Google, Data Engineer..."
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="field filter-field">
          <span>Target Domain</span>
          <input
            type="search"
            value={domain}
            placeholder="e.g. Web Development"
            onChange={(e) => setDomain(e.target.value)}
          />
        </label>
        <div className="filter-actions">
          <button className="primary-button" type="submit">Apply</button>
          <button className="logout-button" type="button" onClick={handleReset}>Reset</button>
        </div>
      </form>

      {error && <ErrorBlock message={error} onRetry={() => load()} />}

      {alumni == null ? (
        <LoadingBlock label="Loading... placed alumni database…" />
      ) : alumni.length === 0 ? (
        <EmptyState message="No placed alumni found matching your criteria." />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
          {alumni.map((item) => (
            <article key={item.id} className="stat-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <span className="badge badge-good" style={{ margin: 0, fontSize: '.8rem' }}>{item.outcome} ({item.placement_year})</span>
                  <span className="mono" style={{ fontSize: '.85rem', color: '#1959b8', fontWeight: 700 }}>CGPA {formatCgpa(item.cgpa)}</span>
                </div>
                <h3 style={{ margin: '0 0 4px', fontSize: '1.2rem' }}>{item.student_name}</h3>
                <p style={{ margin: '0 0 10px', color: '#1959b8', fontWeight: 700, fontSize: '.95rem' }}>
                  {item.role_title} @ {item.company_name}
                </p>
                <p className="stat-label" style={{ marginBottom: '6px' }}>Domain: {item.domain}</p>
                
                <div className="skill-chips" style={{ maxWidth: '100%', marginBottom: '16px' }}>
                  {(item.talents || []).map((t) => (
                    <span key={t} className="chip" style={{ background: '#eef5ff', color: '#1959b8', border: '1px solid #cce0ff' }}>
                      ✨ {t}
                    </span>
                  ))}
                </div>
              </div>

              <button
                className="primary-button"
                style={{ width: '100%', padding: '10px', fontSize: '.88rem' }}
                onClick={() => handleViewExplainability(item)}
              >
                🔍 View AI Explainability
              </button>
            </article>
          ))}
        </div>
      )}

      {/* Explainability Breakdown Modal */}
      {selectedAlumni && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: '680px' }}>
            <div className="modal-header">
              <h2>🧠 Explainability Analysis: {selectedAlumni.student_name}</h2>
              <button className="close-button" onClick={() => setSelectedAlumni(null)}>×</button>
            </div>

            {explError && <ErrorBlock message={explError} />}

            {loadingExpl ? (
              <LoadingBlock label="Calculating SHAP & TF-IDF feature attribution..." />
            ) : explanation ? (
              <div>
                <p style={{ margin: '0 0 16px', color: '#5c6b82' }}>
                  Placed as <strong>{explanation.role_title}</strong> at <strong>{explanation.company_name}</strong>
                </p>

                <div className="explanation-headline">
                  <div>
                    <p className="stat-label">Actual Domain</p>
                    <p className="stat-value">{explanation.actual_domain}</p>
                  </div>
                  <div>
                    <p className="stat-label">AI Predicted</p>
                    <p className="stat-value">{explanation.predicted_domain}</p>
                  </div>
                  <div>
                    <p className="stat-label">Model Confidence</p>
                    <p className="stat-value" style={{ color: '#1959b8' }}>{formatPercent(explanation.confidence_score)}</p>
                  </div>
                </div>

                <div className="summary-text" style={{ margin: '16px 0' }}>
                  {explanation.human_readable_summary}
                </div>

                <h3 style={{ fontSize: '1rem', color: '#24416b', margin: '20px 0 10px' }}>Key Contributing Talent Factors</h3>
                <ul className="factor-list">
                  {(explanation.explainability_factors || []).map((f, i) => (
                    <li key={i} className="factor factor-supports">
                      <div className="factor-head">
                        <span className="factor-keyword">✨ {f.feature}</span>
                        <span className="factor-weight">weight +{f.weight}</span>
                      </div>
                      <p className="factor-desc">{f.description}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </div>
      )}

      <StudentExplainabilityChatbot />
    </>
  )
}

// ----- 5. Floating AI Explainability Chatbot Widget -------------------------

export function StudentExplainabilityChatbot() {
  const { auth } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([
    { sender: 'bot', text: '👋 Hi! I am your AI Explainability Assistant. Ask me anything about your domain match, SHAP scores, or profile audit status.' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSend(queryText = input) {
    const userMsg = typeof queryText === 'string' ? queryText.trim() : input.trim()
    if (!userMsg || loading) return

    if (!auth?.token) {
      setMessages(prev => [...prev, { sender: 'user', text: userMsg }, { sender: 'bot', text: 'Please sign in to your student account to ask explainability questions.' }])
      return
    }

    setInput('')
    setMessages(prev => [...prev, { sender: 'user', text: userMsg }])
    setLoading(true)

    try {
      const data = await apiRequest('/api/v1/students/chatbot/query', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${auth.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query: userMsg })
      })
      setMessages(prev => [...prev, { sender: 'bot', text: data.answer }])
    } catch (err) {
      const errMsg = err.message === 'Failed to fetch' 
        ? 'Cannot connect to backend server. Please verify FastAPI is running at http://127.0.0.1:8000.'
        : err.message
      setMessages(prev => [...prev, { sender: 'bot', text: `Sorry, couldn't fetch explanation answer: ${errMsg}` }])
    } finally {
      setLoading(false)
    }
  }

  const quickPrompts = [
    'Why was I matched to this domain?',
    'What does my SHAP score mean?',
    'Is my profile flagged for anomaly audit?',
    'How can I improve my placement match?'
  ]

  return (
    <>
      <button className="chatbot-toggle" onClick={() => setIsOpen(!isOpen)}>
        💬 AI Assistant
      </button>

      {isOpen && (
        <div className="chatbot-window">
          <div className="chatbot-header">
            <h3>🤖 AI Explainability Assistant</h3>
            <button className="close-button" style={{ color: '#fff' }} onClick={() => setIsOpen(false)}>×</button>
          </div>

          <div className="chatbot-messages">
            {messages.map((m, idx) => (
              <div key={idx} className={`chat-bubble ${m.sender === 'user' ? 'chat-user' : 'chat-bot'}`}>
                {m.text}
              </div>
            ))}
            {loading && <div className="chat-bubble chat-bot">Thinking…</div>}
          </div>

          <div className="chat-quick-prompts">
            {quickPrompts.map((qp, i) => (
              <button key={i} className="quick-prompt-btn" onClick={() => handleSend(qp)}>
                {qp}
              </button>
            ))}
          </div>

          <form className="chat-input-row" onSubmit={(e) => { e.preventDefault(); handleSend(); }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your AI results…"
            />
            <button type="submit" disabled={loading}>Send</button>
          </form>
        </div>
      )}
    </>
  )
}

// ----- 6. Placement Readiness Check Tab ------------------------------------

export function StudentReadinessPage() {
  const { auth } = useAuth()
  const [selectedDomain, setSelectedDomain] = useState('Software Development')
  const [questions, setQuestions] = useState([])
  const [answers, setAnswers] = useState({})
  const [scoreResult, setScoreResult] = useState(null)
  
  const [loadingQuestions, setLoadingQuestions] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Load latest score on mount
  useEffect(() => {
    let cancelled = false
    async function loadLatestScore() {
      if (!auth?.user?.user_id) return
      try {
        const studentProfile = await apiRequest('/api/v1/students/profile', {
          headers: { Authorization: `Bearer ${auth.token}` }
        })
        const data = await apiRequest(`/api/v1/readiness/score/${studentProfile.id}`, {
          headers: { Authorization: `Bearer ${auth.token}` }
        })
        if (!cancelled) setScoreResult(data)
      } catch (err) {
        console.error(err);
      }
    }
    loadLatestScore()
    return () => { cancelled = true }
  }, [auth.token, auth?.user?.user_id])

  // Load questions when domain changes
  useEffect(() => {
    let cancelled = false
    async function loadQuestions() {
      setLoadingQuestions(true)
      setError('')
      try {
        const qList = await apiRequest(`/api/v1/readiness/questions/${encodeURIComponent(selectedDomain)}`, {
          headers: { Authorization: `Bearer ${auth.token}` }
        })
        if (!cancelled) {
          setQuestions(qList)
          const defaultAnswers = {}
          qList.forEach(q => { defaultAnswers[q.id] = 3 })
          setAnswers(defaultAnswers)
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load domain questions.')
      } finally {
        if (!cancelled) setLoadingQuestions(false)
      }
    }
    loadQuestions()
    return () => { cancelled = true }
  }, [auth.token, selectedDomain])

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccessMsg('')

    const payloadAnswers = Object.entries(answers).map(([qId, pts]) => ({
      question_id: parseInt(qId, 10),
      selected_points: parseInt(pts, 10)
    }))

    try {
      const res = await apiRequest('/api/v1/readiness/submit', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${auth.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          domain: selectedDomain,
          answers: payloadAnswers
        })
      })
      setScoreResult(res)
      setSuccessMsg(`Readiness Score updated! Overall Readiness: ${res.total_score_percent}%`)
    } catch (err) {
      setError(err.message || 'Failed to calculate readiness score.')
    } finally {
      setSubmitting(false)
    }
  }

  const domains = [
    'Software Development',
    'Data Science & Analytics',
    'Web Development',
    'Machine Learning'
  ]

  return (
    <>
      <StudentSubNav />
      <header className="dashboard-header">
        <p className="eyebrow">Preparation &amp; Skill Audit</p>
        <h1>Placement Readiness Score</h1>
        <p className="muted">Self-evaluation checklist to measure interview, DSA, and technical domain readiness.</p>
      </header>

      {/* Latest Readiness Score Card */}
      {scoreResult && (
        <section className="explainability-card" style={{ marginBottom: '24px', borderLeft: '5px solid #1959b8' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <span className="eyebrow">Evaluated Domain: {scoreResult.domain}</span>
              <h2 style={{ margin: '4px 0 0', fontSize: '1.5rem', color: '#172033' }}>
                Overall Readiness: <span style={{ color: scoreResult.total_score_percent >= 75 ? '#1d6b3d' : '#8a1d29' }}>{scoreResult.total_score_percent}%</span>
              </h2>
            </div>
            <span className={`badge ${scoreResult.total_score_percent >= 75 ? 'badge-good' : 'badge-bad'}`} style={{ fontSize: '1rem', padding: '8px 14px' }}>
              {scoreResult.total_score_percent >= 75 ? 'Placement Ready' : 'Needs Practice'}
            </span>
          </div>

          <div className="stat-grid" style={{ marginBottom: '16px' }}>
            {Object.entries(scoreResult.category_scores || {}).map(([cat, pct]) => (
              <StatCard key={cat} label={`${cat} Score`} value={`${pct}%`} hint={pct >= 75 ? 'Strong Area' : 'Focus Area'} />
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div style={{ background: '#f0f9f4', padding: '14px', borderRadius: '10px', border: '1px solid #bce6cb' }}>
              <strong style={{ color: '#1d6b3d' }}>✓ Strong Areas (&ge; 75%):</strong>
              <div className="skill-chips" style={{ marginTop: '8px' }}>
                {(scoreResult.strong_areas || []).length > 0 ? (
                  scoreResult.strong_areas.map(a => <span key={a} className="chip" style={{ background: '#d6f5e3', color: '#1d6b3d' }}>{a}</span>)
                ) : <span className="muted">None flagged yet</span>}
              </div>
            </div>

            <div style={{ background: '#fcf2f2', padding: '14px', borderRadius: '10px', border: '1px solid #f2c7c7' }}>
              <strong style={{ color: '#8a1d29' }}>⚠️ Weak Areas / Needs Focus (&lt; 60%):</strong>
              <div className="skill-chips" style={{ marginTop: '8px' }}>
                {(scoreResult.weak_areas || []).length > 0 ? (
                  scoreResult.weak_areas.map(a => <span key={a} className="chip" style={{ background: '#fcefef', color: '#8a1d29' }}>{a}</span>)
                ) : <span className="muted">No major weak areas flagged</span>}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Quiz / Self Assessment Checklist */}
      <section className="explainability-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#172033' }}>Take Readiness Self-Check</h2>
            <p className="muted" style={{ margin: '2px 0 0', fontSize: '.85rem' }}>Select your target domain and rate your current confidence level per skill item.</p>
          </div>

          <select
            value={selectedDomain}
            onChange={(e) => setSelectedDomain(e.target.value)}
            style={{ padding: '8px 14px', borderRadius: '8px', border: '1px solid #cbd6e6', fontWeight: 650, color: '#1959b8' }}
          >
            {domains.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>

        {error && <ErrorBlock message={error} />}
        {successMsg && <div style={{ background: '#d6f5e3', color: '#1d6b3d', padding: '12px 14px', borderRadius: '8px', marginBottom: '16px', fontWeight: 650 }}>{successMsg}</div>}

        {loadingQuestions ? (
          <LoadingBlock label="Loading... domain questions..." />
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '20px' }}>
            {questions.map((q, idx) => (
              <div key={q.id} style={{ background: '#f8fbff', border: '1px solid #dfe6f2', padding: '16px', borderRadius: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 700, color: '#172033' }}>Q{idx + 1}. {q.question_text}</span>
                  <span className="chip" style={{ background: '#e6f0ff', color: '#1959b8' }}>Category: {q.category}</span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '8px', marginTop: '10px' }}>
                  {(q.options || []).map(opt => (
                    <label key={opt.points} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '.82rem', background: '#fff', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd6e6', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        name={`q_${q.id}`}
                        value={opt.points}
                        checked={answers[q.id] === opt.points}
                        onChange={() => setAnswers({ ...answers, [q.id]: opt.points })}
                      />
                      <span>{opt.text}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}

            <button type="submit" className="primary-button" disabled={submitting} style={{ justifySelf: 'start', padding: '12px 28px' }}>
              {submitting ? 'Calculating Score...' : 'Calculate & Save Readiness Score'}
            </button>
          </form>
        )}
      </section>

      <StudentExplainabilityChatbot />
    </>
  )
}

// ----- 7. Student Applications Status Timeline Tab -------------------------

export function StudentApplicationsPage() {
  const { auth } = useAuth()
  const [applications, setApplications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function loadApplications() {
      setLoading(true)
      setError('')
      try {
        const profile = await apiRequest('/api/v1/students/profile', {
          headers: { Authorization: `Bearer ${auth.token}` }
        })
        const data = await apiRequest(`/api/v1/applications/${profile.id}`, {
          headers: { Authorization: `Bearer ${auth.token}` }
        })
        if (!cancelled) setApplications(data)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load application status history.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    loadApplications()
    return () => { cancelled = true }
  }, [auth.token])

  const stages = [
    { key: 'applied', label: 'Applied' },
    { key: 'shortlisted', label: 'Shortlisted' },
    { key: 'interview', label: 'Interview' },
    { key: 'offer', label: 'Offer' },
  ]

  function getStepState(currentStatus, stageKey) {
    if (currentStatus === 'rejected') {
      if (stageKey === 'applied') return 'is-done'
      return 'is-rejected'
    }
    const order = ['applied', 'shortlisted', 'interview', 'offer']
    const currIdx = order.indexOf(currentStatus)
    const stageIdx = order.indexOf(stageKey)

    if (stageIdx < currIdx) return 'is-done'
    if (stageIdx === currIdx) return 'is-current'
    return '—'
  }

  return (
    <>
      <StudentSubNav />
      <header className="dashboard-header">
        <p className="eyebrow">Recruitment Lifecycle</p>
        <h1>My Applications &amp; Status Timeline</h1>
        <p className="muted">Track live status updates as recruiters evaluate candidates and conduct hiring rounds.</p>
      </header>

      {error && <ErrorBlock message={error} />}

      {loading ? (
        <LoadingBlock label="Loading... your applications timeline…" />
      ) : applications.length === 0 ? (
        <EmptyState message="You haven't submitted any job applications yet. Visit 'Recommended Jobs' to apply." />
      ) : (
        <div className="timeline-container">
          {applications.map((app) => (
            <div key={app.id} className="app-card">
              <div className="app-card-header">
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#172033' }}>{app.company_name}</h3>
                  <p className="muted" style={{ margin: '2px 0 0', fontSize: '.85rem' }}>
                    Applied on {new Date(app.created_at).toLocaleDateString()} | Last Updated: {new Date(app.updated_at).toLocaleDateString()}
                  </p>
                </div>
                <span className={`badge ${app.status === 'offer' ? 'badge-good' : app.status === 'rejected' ? 'badge-bad' : 'badge-buffer'}`} style={{ fontSize: '.92rem', padding: '6px 14px' }}>
                  {app.status.toUpperCase()}
                </span>
              </div>

              {/* Status Timeline Stepper */}
              <div className="stepper-row">
                {stages.map((stage, idx) => {
                  const stateClass = getStepState(app.status, stage.key)
                  const isLast = idx === stages.length - 1
                  const isLineActive = app.status !== 'rejected' && stages.findIndex(s => s.key === app.status) > idx

                  return (
                    <div key={stage.key} style={{ display: 'flex', alignItems: 'center', flex: isLast ? '0 1 auto' : 1 }}>
                      <div className={`step-item ${stateClass}`}>
                        <div className="step-circle">
                          {stateClass === 'is-done' ? '✓' : stateClass === 'is-rejected' ? '×' : idx + 1}
                        </div>
                        <span className="step-label">{stage.label}</span>
                      </div>
                      {!isLast && <div className={`step-line ${isLineActive ? 'is-active' : ''}`} />}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      <StudentExplainabilityChatbot />
    </>
  )
}
