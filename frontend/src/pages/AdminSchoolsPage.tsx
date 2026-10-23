import { useEffect, useState, type FormEvent } from 'react'
import { apiRequest } from '../services/api'
import type { AdminCatalogItem, School, SchoolClass } from '../types'

type AdminSchoolsPageProps = {
  token: string
}

type VariantDraft = {
  size: string
  color: string
  price: string
  stock_quantity: string
}

type RosterDraft = {
  name: string
  grade: string
  section: string
  roll_number: string
}

type ClassDraft = {
  grade: string
  sections: string
}

const emptyVariant = (): VariantDraft => ({ size: '', color: '', price: '', stock_quantity: '0' })
const emptyRosterEntry = (): RosterDraft => ({ name: '', grade: '', section: '', roll_number: '' })
const emptyClassEntry = (): ClassDraft => ({ grade: '', sections: '' })

async function uploadImage(file: File, token: string): Promise<string> {
  if (file.size > 5 * 1024 * 1024) throw new Error('Choose an image smaller than 5 MB.')
  const form = new FormData()
  form.append('file', file)
  const result = await apiRequest<{ image_url: string }>('/admin/uploads/image', { method: 'POST', body: form }, token)
  return result.image_url
}

function parseClasses(input: string) {
  const byGrade = new Map<number, Set<string>>()
  for (const line of input.split(/\r?\n/).map((value) => value.trim()).filter(Boolean)) {
    if (/^grade\s*,\s*sections?$/i.test(line)) continue
    const rangeMatch = /^(\d{1,2})(?:\s*-\s*(\d{1,2}))?\s*:\s*(.+)$/.exec(line)
    const csvMatch = /^(\d{1,2})\s*,\s*(.+)$/.exec(line)
    const match = rangeMatch ?? csvMatch
    if (!match) throw new Error(`Invalid class line: "${line}". Use "Grade,Section" or "1-12: A, B".`)
    const first = Number(match[1])
    const last = Number(rangeMatch?.[2] || match[1])
    if (first < 1 || last > 12 || last < first) throw new Error('Class grades must be between 1 and 12.')
    const sectionsText = rangeMatch ? rangeMatch[3] : csvMatch?.[2]
    const sections = (sectionsText ?? '').split(',').map((value) => value.trim().toUpperCase()).filter(Boolean)
    if (!sections.length || sections.length > 12) throw new Error(`Add 1 to 12 sections for grade ${first}.`)
    for (let grade = first; grade <= last; grade += 1) {
      const configured = byGrade.get(grade) ?? new Set<string>()
      for (const section of sections) {
        if (configured.has(section)) throw new Error(`Section ${section} is listed more than once for grade ${grade}.`)
        configured.add(section)
      }
      if (configured.size > 12) throw new Error(`Add no more than 12 sections for grade ${grade}.`)
      byGrade.set(grade, configured)
    }
  }
  if (!byGrade.size) throw new Error('Add at least one grade and section.')
  return [...byGrade.entries()].map(([grade, sections]) => ({ grade, sections: [...sections] }))
}

function parseClassFields(entries: ClassDraft[]) {
  return parseClasses(entries.map(({ grade, sections }) => `${grade}: ${sections}`).join('\n'))
}

export function AdminSchoolsPage({ token }: AdminSchoolsPageProps) {
  const [schools, setSchools] = useState<School[]>([])
  const [schoolId, setSchoolId] = useState('')
  const [items, setItems] = useState<AdminCatalogItem[]>([])
  const [loading, setLoading] = useState(true)
  const [catalogSchoolId, setCatalogSchoolId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [schoolName, setSchoolName] = useState('')
  const [schoolCity, setSchoolCity] = useState('')
  const [schoolAddress, setSchoolAddress] = useState('')
  const [schoolDescription, setSchoolDescription] = useState('')
  const [classMode, setClassMode] = useState<'fields' | 'bulk'>('fields')
  const [classDrafts, setClassDrafts] = useState<ClassDraft[]>([{ grade: '1', sections: 'A, B' }])
  const [classLines, setClassLines] = useState('')
  const [schoolImage, setSchoolImage] = useState<File | null>(null)
  const [schoolClasses, setSchoolClasses] = useState<SchoolClass[]>([])
  const [schoolClassesSchoolId, setSchoolClassesSchoolId] = useState('')
  const [rosterMode, setRosterMode] = useState<'fields' | 'bulk'>('fields')
  const [rosterDrafts, setRosterDrafts] = useState<RosterDraft[]>([emptyRosterEntry()])
  const [rosterText, setRosterText] = useState('')
  const [productName, setProductName] = useState('')
  const [productCategory, setProductCategory] = useState('Formal Uniform')
  const [productGender, setProductGender] = useState<'boys' | 'girls' | 'unisex'>('unisex')
  const [productDescription, setProductDescription] = useState('')
  const [productImage, setProductImage] = useState<File | null>(null)
  const [variants, setVariants] = useState<VariantDraft[]>([emptyVariant()])

  const configuredSchoolClasses = schoolClassesSchoolId === schoolId ? schoolClasses : []

  const refreshSchools = async () => {
    const data = await apiRequest<School[]>('/schools')
    setSchools(data)
    setSchoolId((current) => data.some((school) => String(school.id) === current) ? current : String(data[0]?.id ?? ''))
  }

  useEffect(() => {
    let active = true
    apiRequest<School[]>('/schools')
      .then((data) => {
        if (!active) return
        setSchools(data)
        setSchoolId(String(data[0]?.id ?? ''))
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Schools could not be loaded.')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!schoolId) return
    let active = true
    apiRequest<SchoolClass[]>(`/schools/${schoolId}/classes`)
      .then((classes) => {
        if (active) {
          setSchoolClasses(classes)
          setSchoolClassesSchoolId(schoolId)
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'School classes could not be loaded.')
      })
    return () => { active = false }
  }, [schoolId])

  useEffect(() => {
    if (!schoolId) return
    let active = true
    apiRequest<AdminCatalogItem[]>(`/admin/schools/${schoolId}/products`, {}, token)
      .then((data) => {
        if (!active) return
        setItems(data)
        setCatalogSchoolId(schoolId)
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'School catalog could not be loaded.')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [schoolId, token])

  const submitSchool = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setMessage('')
    setSaving(true)
    try {
      const logoUrl = schoolImage ? await uploadImage(schoolImage, token) : undefined
      const school = await apiRequest<School>('/admin/schools', {
        method: 'POST',
        body: JSON.stringify({
          name: schoolName.trim(),
          city: schoolCity.trim(),
          address: schoolAddress.trim(),
          description: schoolDescription.trim() || null,
          logo_url: logoUrl ?? null,
          classes: classMode === 'fields' ? parseClassFields(classDrafts) : parseClasses(classLines),
        }),
      }, token)
      await refreshSchools()
      setSchoolId(String(school.id))
      setSchoolName('')
      setSchoolCity('')
      setSchoolAddress('')
      setSchoolDescription('')
      setSchoolImage(null)
      setClassDrafts([{ grade: '1', sections: 'A, B' }])
      setClassLines('')
      setMessage(`${school.name} is ready for student registration.`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'School could not be created.')
    } finally {
      setSaving(false)
    }
  }

  const submitRoster = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setMessage('')
    setSaving(true)
    try {
      const students = rosterMode === 'fields'
        ? rosterDrafts.map(({ name, grade, section, roll_number }) => {
            if (!name.trim() || !grade || !section || !roll_number.trim()) throw new Error('Complete every student field before adding the roster.')
            return { name: name.trim(), grade: Number(grade), section, roll_number: roll_number.trim() }
          })
        : rosterText.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
            if (/^name\s*,\s*grade\s*,\s*section\s*,\s*roll[\s_-]*number$/i.test(line)) return null
            const [name, grade, section, roll_number, ...extra] = line.split(',').map((value) => value.trim())
            if (extra.length || !name || !grade || !section || !roll_number || !/^\d+$/.test(grade)) {
              throw new Error(`Invalid roster line: "${line}". Use "Name, grade, section, roll number".`)
            }
            return { name, grade: Number(grade), section, roll_number }
          }).filter((student): student is NonNullable<typeof student> => student !== null)
      if (students.length > 500) throw new Error('Add no more than 500 student records at a time.')
      const result = await apiRequest<{ created: number }>(`/admin/schools/${schoolId}/roster`, {
        method: 'POST',
        body: JSON.stringify({ students }),
      }, token)
      setRosterDrafts([emptyRosterEntry()])
      setRosterText('')
      setMessage(`${result.created} student ${result.created === 1 ? 'entry' : 'entries'} added. Students can now verify their school details and sign up.`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Student roster could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  const submitProduct = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setMessage('')
    setSaving(true)
    try {
      const validVariants = variants.map((variant) => {
        const price = Number(variant.price)
        const stock = Number(variant.stock_quantity)
        if (!variant.size.trim() || !Number.isFinite(price) || price <= 0 || !Number.isInteger(stock) || stock < 0) {
          throw new Error('Each size needs a positive price and a whole-number stock quantity (zero is allowed).')
        }
        return { size: variant.size.trim(), color: variant.color.trim() || null, price, stock_quantity: stock }
      })
      const keys = validVariants.map((variant) => `${variant.size.toLowerCase()}|${(variant.color ?? '').toLowerCase()}`)
      if (new Set(keys).size !== keys.length) throw new Error('Each size and color combination must be unique.')
      const imageUrl = productImage ? await uploadImage(productImage, token) : null
      await apiRequest<AdminCatalogItem[]>(`/admin/schools/${schoolId}/products`, {
        method: 'POST',
        body: JSON.stringify({
          name: productName.trim(),
          category: productCategory.trim(),
          gender: productGender,
          description: productDescription.trim() || null,
          image_url: imageUrl,
          variants: validVariants,
        }),
      }, token)
      const updated = await apiRequest<AdminCatalogItem[]>(`/admin/schools/${schoolId}/products`, {}, token)
      setItems(updated)
      setProductName('')
      setProductDescription('')
      setProductImage(null)
      setVariants([emptyVariant()])
      setMessage('Product, sizes, pricing and school inventory are live in the selected school catalog.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Product could not be created.')
    } finally {
      setSaving(false)
    }
  }

  const saveCatalogItem = async (item: AdminCatalogItem, price: number, stock: number, active: boolean) => {
    setError('')
    setMessage('')
    try {
      const updated = await apiRequest<AdminCatalogItem>(`/admin/catalog-items/${item.catalog_item_id}`, {
        method: 'PATCH',
        body: JSON.stringify({ selling_price: price, stock_quantity: stock, is_active: active }),
      }, token)
      setItems((current) => current.map((entry) => entry.catalog_item_id === updated.catalog_item_id ? updated : entry))
      setMessage(`${updated.name} · ${updated.size} inventory saved.`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Inventory could not be updated.')
    }
  }

  return (
    <section className="school-admin">
      <div className="school-admin-intro">
        <div>
          <p className="eyebrow">School storefronts</p>
          <h2>Schools, students & catalog</h2>
          <p>Create school profiles, verify student enrollment, and manage school-specific products and live stock.</p>
        </div>
        <label className="school-picker">Manage school
          <select value={schoolId} onChange={(event) => setSchoolId(event.target.value)} disabled={!schools.length}>
            {schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
          </select>
        </label>
      </div>
      {error && <p className="error-text" role="alert">{error}</p>}
      {message && <p className="admin-success" role="status">{message}</p>}
      {loading && !schools.length ? <p className="state-message">Loading schools…</p> : (
        <>
          <div className="school-admin-grid">
            <form className="panel school-admin-card" onSubmit={(event) => void submitSchool(event)}>
              <div className="admin-card-heading"><span className="admin-card-number">01</span><div><h3>Create a school</h3><p>Set the address and available classes before students sign up.</p></div></div>
              <label>School name<input required minLength={2} maxLength={255} value={schoolName} onChange={(event) => setSchoolName(event.target.value)} placeholder="e.g. Northside Academy" /></label>
              <div className="admin-form-row">
                <label>City<input required minLength={2} maxLength={100} value={schoolCity} onChange={(event) => setSchoolCity(event.target.value)} /></label>
                <label>School image<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => setSchoolImage(event.target.files?.[0] ?? null)} /></label>
              </div>
              <label>School address<textarea required minLength={5} maxLength={1000} value={schoolAddress} onChange={(event) => setSchoolAddress(event.target.value)} rows={2} /></label>
              <label>About this school<textarea maxLength={2000} value={schoolDescription} onChange={(event) => setSchoolDescription(event.target.value)} rows={2} placeholder="Store details or school uniform information" /></label>
              <div className="admin-input-heading">
                <div><strong>Class and section setup</strong><span className="admin-field-hint">Add the grades and sections students can select during sign-up.</span></div>
                <div className="admin-entry-mode" role="group" aria-label="Class setup entry mode">
                  <button type="button" className={classMode === 'fields' ? 'active' : ''} aria-pressed={classMode === 'fields'} onClick={() => setClassMode('fields')}>Field wise</button>
                  <button type="button" className={classMode === 'bulk' ? 'active' : ''} aria-pressed={classMode === 'bulk'} onClick={() => setClassMode('bulk')}>Bulk upload</button>
                </div>
              </div>
              {classMode === 'fields' ? (
                <div className="admin-entry-list">
                  {classDrafts.map((entry, index) => (
                    <div className="admin-entry-row class-entry-row" key={index}>
                      <label>Class / grade
                        <select required value={entry.grade} onChange={(event) => setClassDrafts((current) => current.map((item, i) => i === index ? { ...item, grade: event.target.value } : item))}>
                          <option value="">Select class</option>
                          {Array.from({ length: 12 }, (_, i) => i + 1).map((grade) => <option key={grade} value={grade}>Class {grade}</option>)}
                        </select>
                      </label>
                      <label>Sections
                        <input required value={entry.sections} onChange={(event) => setClassDrafts((current) => current.map((item, i) => i === index ? { ...item, sections: event.target.value } : item))} placeholder="A, B, C" />
                        <span className="admin-field-hint">Separate section names with commas.</span>
                      </label>
                      <button className="button button-secondary button-small entry-remove" type="button" aria-label={`Remove class row ${index + 1}`} disabled={classDrafts.length === 1} onClick={() => setClassDrafts((current) => current.filter((_, i) => i !== index))}>Remove</button>
                    </div>
                  ))}
                  <button className="button button-secondary button-small entry-add" type="button" disabled={classDrafts.length >= 12} onClick={() => setClassDrafts((current) => [...current, emptyClassEntry()])}>Add class</button>
                </div>
              ) : (
                <label>Upload or paste classes
                  <input type="file" accept=".csv,.txt,text/plain,text/csv" onChange={(event) => {
                    const file = event.target.files?.[0]
                    if (file) void file.text().then(setClassLines).catch(() => setError('Class setup file could not be read.'))
                  }} />
                  <textarea required value={classLines} onChange={(event) => setClassLines(event.target.value)} rows={5} placeholder={'Grade,Section\n1,A\n1,B\n2,A\n\nOr use ranges: 1-12: A, B'} />
                  <span className="admin-field-hint">CSV format: one Grade,Section pair per line. You can also paste a range like 1-12: A, B.</span>
                </label>
              )}
              <button className="button button-primary" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create school'}</button>
            </form>

            <form className="panel school-admin-card" onSubmit={(event) => void submitRoster(event)}>
              <div className="admin-card-heading"><span className="admin-card-number">02</span><div><h3>Verify student enrollment</h3><p>Add roster records. Only matching students can claim an account.</p></div></div>
              {!schoolId ? <p className="muted">Create or select a school first.</p> : (
                <>
                  <div className="admin-input-heading">
                    <div><strong>Student roster</strong><span className="admin-field-hint">Only matching roster details can be used to claim a student account.</span></div>
                    <div className="admin-entry-mode" role="group" aria-label="Student roster entry mode">
                      <button type="button" className={rosterMode === 'fields' ? 'active' : ''} aria-pressed={rosterMode === 'fields'} onClick={() => setRosterMode('fields')}>Field wise</button>
                      <button type="button" className={rosterMode === 'bulk' ? 'active' : ''} aria-pressed={rosterMode === 'bulk'} onClick={() => setRosterMode('bulk')}>Bulk upload</button>
                    </div>
                  </div>
                  {rosterMode === 'fields' ? (
                    <div className="admin-entry-list">
                      {!configuredSchoolClasses.length && <p className="admin-field-hint">No classes are configured for this school yet. Add a school with class and section setup first.</p>}
                      {rosterDrafts.map((entry, index) => {
                        const selectedClass = configuredSchoolClasses.find((item) => item.grade === Number(entry.grade))
                        return (
                          <div className="admin-entry-row roster-entry-row" key={index}>
                            <label>Student name<input required minLength={2} maxLength={255} value={entry.name} onChange={(event) => setRosterDrafts((current) => current.map((item, i) => i === index ? { ...item, name: event.target.value } : item))} placeholder="Full name" /></label>
                            <label>Class<select required value={entry.grade} onChange={(event) => setRosterDrafts((current) => current.map((item, i) => i === index ? { ...item, grade: event.target.value, section: '' } : item))}><option value="">Select class</option>{configuredSchoolClasses.map((item) => <option key={item.grade} value={item.grade}>Class {item.grade}</option>)}</select></label>
                            <label>Section<select required value={entry.section} disabled={!selectedClass} onChange={(event) => setRosterDrafts((current) => current.map((item, i) => i === index ? { ...item, section: event.target.value } : item))}><option value="">Select section</option>{selectedClass?.sections.map((section) => <option key={section} value={section}>{section}</option>)}</select></label>
                            <label>Roll number<input required maxLength={30} value={entry.roll_number} onChange={(event) => setRosterDrafts((current) => current.map((item, i) => i === index ? { ...item, roll_number: event.target.value } : item))} placeholder="e.g. 8-A-014" /></label>
                            <button className="button button-secondary button-small entry-remove" type="button" aria-label={`Remove student row ${index + 1}`} disabled={rosterDrafts.length === 1} onClick={() => setRosterDrafts((current) => current.filter((_, i) => i !== index))}>Remove</button>
                          </div>
                        )
                      })}
                      <button className="button button-secondary button-small entry-add" type="button" disabled={rosterDrafts.length >= 500} onClick={() => setRosterDrafts((current) => [...current, emptyRosterEntry()])}>Add student</button>
                    </div>
                  ) : (
                    <label>Upload or paste roster
                      <input type="file" accept=".csv,.txt,text/plain,text/csv" onChange={(event) => {
                        const file = event.target.files?.[0]
                        if (file) void file.text().then(setRosterText).catch(() => setError('Roster file could not be read.'))
                      }} />
                      <textarea required value={rosterText} onChange={(event) => setRosterText(event.target.value)} rows={7} placeholder={'Name,Grade,Section,Roll Number\nAarav Mehta,8,A,G8-A-014'} />
                      <span className="admin-field-hint">CSV columns: Name, Grade, Section, Roll Number. Each class and section must exist.</span>
                    </label>
                  )}
                  <button className="button button-secondary" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Add roster entries'}</button>
                </>
              )}
            </form>
          </div>

          <form className="panel school-admin-card school-product-form" onSubmit={(event) => void submitProduct(event)}>
            <div className="admin-card-heading"><span className="admin-card-number">03</span><div><h3>Publish to this school</h3><p>Each size gets its own price and inventory; photos are optimized on upload.</p></div></div>
            {!schoolId ? <p className="muted">Create or select a school before adding products.</p> : (
              <>
                <div className="school-product-form-grid">
                  <label>Product name<input required minLength={2} maxLength={255} value={productName} onChange={(event) => setProductName(event.target.value)} placeholder="e.g. Sports uniform set" /></label>
                  <label>Category<input required minLength={2} maxLength={80} value={productCategory} onChange={(event) => setProductCategory(event.target.value)} placeholder="Formal Uniform, Sportswear…" /></label>
                  <label>For<select value={productGender} onChange={(event) => setProductGender(event.target.value as typeof productGender)}><option value="unisex">Everyone</option><option value="boys">Boys</option><option value="girls">Girls</option></select></label>
                  <label>Product image<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => setProductImage(event.target.files?.[0] ?? null)} /></label>
                  <label className="school-product-description">Description<textarea maxLength={2000} value={productDescription} onChange={(event) => setProductDescription(event.target.value)} rows={2} /></label>
                </div>
                <div className="variant-editor-heading"><div><h4>Sizes, prices & stock</h4><p>Inventory is independent for each school.</p></div><button className="button button-secondary button-small" type="button" onClick={() => setVariants((current) => [...current, emptyVariant()])}>Add size</button></div>
                <div className="variant-editor-list">
                  {variants.map((variant, index) => (
                    <div className="variant-editor-row" key={index}>
                      <label>Size<input required maxLength={20} value={variant.size} onChange={(event) => setVariants((current) => current.map((entry, i) => i === index ? { ...entry, size: event.target.value } : entry))} placeholder="M" /></label>
                      <label>Color<input maxLength={50} value={variant.color} onChange={(event) => setVariants((current) => current.map((entry, i) => i === index ? { ...entry, color: event.target.value } : entry))} placeholder="Navy" /></label>
                      <label>Price (₹)<input required type="number" min="0.01" step="0.01" value={variant.price} onChange={(event) => setVariants((current) => current.map((entry, i) => i === index ? { ...entry, price: event.target.value } : entry))} /></label>
                      <label>Stock<input required type="number" min="0" step="1" value={variant.stock_quantity} onChange={(event) => setVariants((current) => current.map((entry, i) => i === index ? { ...entry, stock_quantity: event.target.value } : entry))} /></label>
                      {variants.length > 1 && <button type="button" className="text-button variant-remove" aria-label={`Remove size ${variant.size || index + 1}`} onClick={() => setVariants((current) => current.filter((_, i) => i !== index))}>Remove</button>}
                    </div>
                  ))}
                </div>
                <button className="button button-primary" type="submit" disabled={saving}>{saving ? 'Publishing…' : 'Publish product to school'}</button>
              </>
            )}
          </form>

          <section className="panel school-catalog-panel">
            <div className="section-heading"><div><h3>School catalog & inventory</h3><p>Stock and price updates appear in the student catalog immediately.</p></div><span>{items.length} sizes</span></div>
            {!schoolId ? <p className="muted">Create or select a school to view its catalog.</p> : catalogSchoolId !== schoolId ? <p className="state-message">Loading school catalog…</p> : !items.length ? <p className="muted">No products have been published to this school yet.</p> : (
              <div className="school-catalog-list">
                {items.map((item) => (
                  <CatalogStockRow key={item.catalog_item_id} item={item} onSave={saveCatalogItem} />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </section>
  )
}

function CatalogStockRow({
  item,
  onSave,
}: {
  item: AdminCatalogItem
  onSave: (item: AdminCatalogItem, price: number, stock: number, active: boolean) => Promise<void>
}) {
  const [price, setPrice] = useState(String(item.selling_price))
  const [stock, setStock] = useState(String(item.stock_quantity))
  const [active, setActive] = useState(item.is_active)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    const parsedPrice = Number(price)
    const parsedStock = Number(stock)
    if (!Number.isFinite(parsedPrice) || parsedPrice <= 0 || !Number.isInteger(parsedStock) || parsedStock < 0) {
      setError('Enter a positive price and a whole-number stock quantity.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSave(item, parsedPrice, parsedStock, active)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Inventory could not be updated.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <article className="school-catalog-row">
      <div className="school-catalog-info">
        {item.image_url && <img src={item.image_url} alt="" />}
        <div><strong>{item.name}</strong><span>{item.category} · {item.gender} · Size {item.size}{item.color ? ` · ${item.color}` : ''}</span></div>
      </div>
      <label>Price<input aria-label={`Price for ${item.name} size ${item.size}`} type="number" min="0.01" step="0.01" value={price} onChange={(event) => setPrice(event.target.value)} /></label>
      <label>Stock<input aria-label={`Stock for ${item.name} size ${item.size}`} type="number" min="0" step="1" value={stock} onChange={(event) => setStock(event.target.value)} /></label>
      <label className="catalog-active-toggle"><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} /> Live</label>
      <button className="button button-secondary button-small" type="button" disabled={saving} onClick={() => void save()}>{saving ? 'Saving…' : 'Save'}</button>
      {error && <p className="error-text catalog-row-error" role="alert">{error}</p>}
    </article>
  )
}
