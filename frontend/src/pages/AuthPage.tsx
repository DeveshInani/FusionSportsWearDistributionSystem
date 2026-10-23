import { useEffect, useState, type FormEvent } from 'react'
import { Brand } from '../components/Brand'
import { apiRequest } from '../services/api'
import type { AuthMode, AuthResponse, School, SchoolClass } from '../types'

type AuthPageProps = {
  onAuthenticated: (response: AuthResponse) => void
}

export function AuthPage({ onAuthenticated }: AuthPageProps) {
  const [mode, setMode] = useState<AuthMode>('login')
  const [schools, setSchools] = useState<School[]>([])
  const [classes, setClasses] = useState<SchoolClass[]>([])
  const [classesForSchoolId, setClassesForSchoolId] = useState('')
  const [schoolId, setSchoolId] = useState('')
  const [grade, setGrade] = useState('')
  const [section, setSection] = useState('')
  const [name, setName] = useState('')
  const [rollNumber, setRollNumber] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const availableClasses = classesForSchoolId === schoolId ? classes : []
  const selectedClass = availableClasses.find((schoolClass) => schoolClass.grade === Number(grade))

  useEffect(() => {
    let active = true
    apiRequest<School[]>('/schools')
      .then((list) => {
        if (!active) return
        setSchools(list)
        if (list.length) setSchoolId(String(list[0].id))
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Schools could not be loaded.')
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!schoolId || mode !== 'register') return
    let active = true
    apiRequest<SchoolClass[]>(`/schools/${schoolId}/classes`)
      .then((list) => {
        if (!active) return
        setClasses(list)
        setClassesForSchoolId(schoolId)
        setGrade((current) => list.some((item) => item.grade === Number(current)) ? current : '')
        setSection('')
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Class list could not be loaded.')
      })
    return () => { active = false }
  }, [schoolId, mode])

  const selectMode = (nextMode: AuthMode) => {
    setMode(nextMode)
    setError('')
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const payload = mode === 'login'
        ? { email, password }
        : {
            email,
            password,
            name,
            school_id: Number(schoolId),
            grade: Number(grade),
            section,
            roll_number: rollNumber.trim(),
          }
      const response = await apiRequest<AuthResponse>(`/auth/${mode}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      onAuthenticated(response)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Account request failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-layout">
        <aside className="auth-intro">
          <Brand />
          <div className="auth-intro-copy">
            <p className="auth-kicker">School uniform store</p>
            <h1>School essentials, made simple.</h1>
            <p>Shop approved uniforms, sportswear and accessories for your school.</p>
          </div>
          <p className="auth-intro-foot">A simpler way to get ready for school.</p>
        </aside>

        <section className="auth-card" aria-labelledby="auth-title">
          <div className="auth-card-heading">
            <p className="auth-kicker">Student account</p>
            <h2 id="auth-title">{mode === 'login' ? 'Sign in' : 'Create your account'}</h2>
            <p>{mode === 'login' ? 'Continue to your school store.' : 'Verify your student details to get started.'}</p>
          </div>

          <div className="auth-tabs" role="tablist" aria-label="Account access">
            <button type="button" role="tab" aria-selected={mode === 'login'} className={mode === 'login' ? 'auth-tab active' : 'auth-tab'} onClick={() => selectMode('login')}>Sign in</button>
            <button type="button" role="tab" aria-selected={mode === 'register'} className={mode === 'register' ? 'auth-tab active' : 'auth-tab'} onClick={() => selectMode('register')}>Sign up</button>
          </div>

          <form className="auth-form" onSubmit={submit}>
            {mode === 'register' && (
              <>
                <label>School
                  <select required value={schoolId} onChange={(event) => setSchoolId(event.target.value)}>
                    <option value="" disabled>{schools.length ? 'Choose your school' : 'No schools are available yet'}</option>
                    {schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
                  </select>
                </label>
                <label>Full name
                  <input autoComplete="name" required minLength={2} value={name} onChange={(event) => setName(event.target.value)} placeholder="As listed with your school" />
                </label>
                <div className="inline-fields">
                  <label>Class
                    <select required value={grade} onChange={(event) => { setGrade(event.target.value); setSection('') }}>
                      <option value="">Select class</option>
                      {availableClasses.map((item) => <option key={item.grade} value={item.grade}>Class {item.grade}</option>)}
                    </select>
                  </label>
                  <label>Section
                    <select required value={section} onChange={(event) => setSection(event.target.value)} disabled={!selectedClass}>
                      <option value="">Select</option>
                      {selectedClass?.sections.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                  </label>
                </div>
                <label>Roll number
                  <input required value={rollNumber} onChange={(event) => setRollNumber(event.target.value)} placeholder="Your school roll number" />
                  <span className="field-hint">Use the name, class, section, and roll number provided by your school.</span>
                </label>
              </>
            )}
            <label>Email address
              <input autoComplete="email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" />
            </label>
            <label>Password
              <input autoComplete={mode === 'login' ? 'current-password' : 'new-password'} type="password" minLength={8} maxLength={72} required value={password} onChange={(event) => setPassword(event.target.value)} placeholder={mode === 'login' ? 'Your password' : 'At least 8 characters'} />
            </label>
            {error && <p className="error-text" role="alert">{error}</p>}
            {mode === 'register' && !schools.length && !error && <p className="field-hint">No schools have been set up yet. Please contact your school store administrator.</p>}
            <button className="button button-primary auth-submit" type="submit" disabled={loading || (mode === 'register' && (!schoolId || !schools.length || !availableClasses.length))}>
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Verify and create account'}
            </button>
          </form>
          <p className="auth-security">Registration is checked against the school’s demo student roster.</p>
        </section>
      </div>
    </main>
  )
}
