import { useEffect, useRef, useState } from 'react'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const supportedExtensions = ['pdf', 'png', 'jpg', 'jpeg', 'txt']
const maxUploadSize = 10 * 1024 * 1024

function formatFileSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatUploadTime(value) {
  return new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

function displayAnswer(value) {
  const bullet = String.fromCharCode(8226)
  return value
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1')
    .replace(/^\s*[-*]\s+/gm, '• ')
    .replace(new RegExp(`${String.fromCharCode(226, 8364, 162)} `, 'g'), `${bullet} `)
}

function App() {
  const [apiStatus, setApiStatus] = useState('checking')
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploadState, setUploadState] = useState('idle')
  const [uploadError, setUploadError] = useState('')
  const [uploadNotice, setUploadNotice] = useState('')
  const [recentMemories, setRecentMemories] = useState([])
  const [memoriesLoading, setMemoriesLoading] = useState(true)
  const [memoriesError, setMemoriesError] = useState('')
  const [selectedMemory, setSelectedMemory] = useState(null)
  const [detailState, setDetailState] = useState('idle')
  const [detailError, setDetailError] = useState('')
  const [deleteState, setDeleteState] = useState('idle')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchState, setSearchState] = useState('idle')
  const [searchAnswer, setSearchAnswer] = useState('')
  const [searchSources, setSearchSources] = useState([])
  const [searchError, setSearchError] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef(null)

  useEffect(() => {
    const controller = new AbortController()

    async function checkApi() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/health`, {
          signal: controller.signal,
        })
        const data = await response.json()
        setApiStatus(response.ok && data.status === 'ok' ? 'connected' : 'unavailable')
      } catch (error) {
        if (error.name !== 'AbortError') setApiStatus('unavailable')
      }
    }

    checkApi()
    return () => controller.abort()
  }, [])

  useEffect(() => {
    loadMemories()
  }, [])

  useEffect(() => {
    if (!uploadNotice) return undefined

    const timeoutId = window.setTimeout(() => setUploadNotice(''), 4000)
    return () => window.clearTimeout(timeoutId)
  }, [uploadNotice])

  const statusLabel = apiStatus === 'connected'
    ? 'MEMORA API connected'
    : apiStatus === 'unavailable'
      ? 'MEMORA API unavailable'
      : 'Checking MEMORA API'

  async function loadMemories() {
    setMemoriesLoading(true)
    setMemoriesError('')
    try {
      const response = await fetch(`${apiBaseUrl}/api/memories`)
      const data = await response.json().catch(() => [])
      if (!response.ok) throw new Error(data.detail || 'Saved memories could not be loaded.')
      setRecentMemories(data)
    } catch (error) {
      setRecentMemories([])
      setMemoriesError(error.message || 'Saved memories could not be loaded.')
    } finally {
      setMemoriesLoading(false)
    }
  }

  async function openMemoryDetail(memoryId) {
    setSelectedMemory(null)
    setDetailState('loading')
    setDetailError('')
    setDeleteState('idle')
    try {
      const response = await fetch(`${apiBaseUrl}/api/memories/${memoryId}`)
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || 'Memory details could not be loaded.')
      setSelectedMemory(data)
      setDetailState('ready')
    } catch (error) {
      setDetailState('error')
      setDetailError(error.message || 'Memory details could not be loaded.')
    }
  }

  function closeMemoryDetail() {
    setDetailState('idle')
    setSelectedMemory(null)
    setDetailError('')
    setDeleteState('idle')
  }

  async function deleteMemory() {
    if (!selectedMemory || deleteState === 'deleting') return
    if (!window.confirm('Delete this memory? It will be removed from MEMORA and search.')) return

    setDeleteState('deleting')
    setDetailError('')
    try {
      const response = await fetch(`${apiBaseUrl}/api/memories/${selectedMemory.id}`, { method: 'DELETE' })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || 'Memory deletion failed. Please try again.')

      setSearchSources((sources) => sources.filter((source) => source.memory_id !== selectedMemory.id))
      closeMemoryDetail()
      await loadMemories()
    } catch (error) {
      setDeleteState('error')
      setDetailError(error.message || 'Memory deletion failed. Please try again.')
    }
  }

  async function searchMemories(event) {
    event.preventDefault()
    const question = searchQuery.trim()
    if (!question) return

    setSearchState('searching')
    setSearchError('')
    setSearchAnswer('')
    setSearchSources([])
    try {
      const response = await fetch(`${apiBaseUrl}/api/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || 'Memory search could not be completed.')
      setSearchAnswer(data.answer || '')
      setSearchSources(data.sources || [])
      setSearchState('complete')
    } catch (error) {
      setSearchState('error')
      setSearchError(error.message || 'Memory search could not be completed.')
    }
  }

  function selectFile(file) {
    if (!file) return

    const extension = file.name.split('.').pop()?.toLowerCase()
    setUploadError('')
    if (!extension || !supportedExtensions.includes(extension)) {
      setSelectedFile(null)
      setUploadState('error')
      setUploadError('Choose a PDF, PNG, JPEG, or TXT file.')
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    if (file.size > maxUploadSize) {
      setSelectedFile(null)
      setUploadState('error')
      setUploadError('Choose a file smaller than 10 MB.')
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    setSelectedFile(file)
    setUploadState('ready')
  }

  function resetUpload() {
    setSelectedFile(null)
    setUploadState('idle')
    setUploadError('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function openUpload() {
    resetUpload()
    setIsUploadOpen(true)
  }

  async function uploadFile() {
    if (!selectedFile || uploadState === 'uploading') return

    setUploadState('uploading')
    setUploadError('')
    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const response = await fetch(`${apiBaseUrl}/api/memories/upload`, {
        method: 'POST',
        body: formData,
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(data.detail || 'Upload failed. Please try again.')

      await loadMemories()
      setUploadNotice(`Uploaded ${data.filename}`)
      setIsUploadOpen(false)
      resetUpload()
    } catch (error) {
      setUploadState('error')
      setUploadError(error.message || 'Upload failed. Please try again.')
    }
  }

  return (
    <main className="app-shell">
      <nav className="topbar" aria-label="Main navigation">
        <a className="wordmark" href="/">MEMORA</a>
        <div className={`api-status ${apiStatus}`} aria-live="polite">
          <span className="status-dot" />
          {statusLabel}
        </div>
      </nav>

      <section className="hero" aria-labelledby="page-title">
        <div className="hero-content">
        <p className="eyebrow">PERSONAL MEMORY SYSTEM</p>
        <h1 id="page-title">Your digital life,<br />remembered.</h1>
        <p className="intro">A quiet place for the details you do not want to lose.</p>

        <form className="search-box" onSubmit={searchMemories}>
          <label className="sr-only" htmlFor="memory-search">Search your memories</label>
          <span className="search-icon" aria-hidden="true">⌕</span>
          <input id="memory-search" type="search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Ask anything you've saved..." />
          <button type="submit" disabled={!searchQuery.trim() || searchState === 'searching'}>{searchState === 'searching' ? 'Thinking...' : 'Ask MEMORA'}</button>
        </form>

        {searchState !== 'idle' && (
          <section className="search-results" aria-live="polite" aria-labelledby="search-results-title">
            <div className="search-results-heading"><p className="eyebrow">MEMORY RETRIEVAL</p><h2 id="search-results-title">Memories related to your search</h2></div>
            {searchState === 'searching' && <p className="search-message">Finding relevant memories and preparing a grounded answer...</p>}
            {searchState === 'error' && <p className="search-error" role="alert">{searchError}</p>}
            {searchState === 'complete' && (
              <div className="memory-answer"><p className="eyebrow">WHAT MEMORA FOUND</p><p>{displayAnswer(searchAnswer)}</p></div>
            )}
            {searchState === 'complete' && searchSources.length > 0 && (
              <>
                <h3 className="source-heading">Sources from your memories</h3>
              <div className="search-result-list">
                {searchSources.map((result, index) => (
                  <button className="search-result" type="button" key={`${result.memory_id}-${index}`} onClick={() => openMemoryDetail(result.memory_id)}>
                    <div className="file-type-badge">{result.file_type.toUpperCase()}</div>
                    <div><strong>{result.filename}</strong><p>{result.chunk_text}</p></div>
                    <span>Open memory</span>
                  </button>
                ))}
              </div>
              </>
            )}
          </section>
        )}
        </div>
      </section>

      <section className="dashboard" aria-label="Memory overview">
        <div className="dashboard-content">
        <div className="section-heading">
          <div>
            <p className="eyebrow">YOUR SPACE</p>
            <h2>Memory overview</h2>
          </div>
          <button className="add-memory" type="button" onClick={openUpload}><span aria-hidden="true">+</span> Add Memory</button>
        </div>

        {uploadNotice && <p className="upload-notice" role="status">{uploadNotice}</p>}

        {isUploadOpen && (
          <div className="upload-modal-backdrop">
          <section className="upload-panel" role="dialog" aria-modal="true" aria-labelledby="upload-title">
            <div className="upload-panel-heading">
              <div>
                <p className="eyebrow">NEW MEMORY</p>
                <h2 id="upload-title">Add a file to MEMORA</h2>
              </div>
              <button className="close-upload" type="button" onClick={() => setIsUploadOpen(false)} aria-label="Close upload panel">Close</button>
            </div>

            <>
                <input
                  ref={fileInputRef}
                  className="sr-only"
                  id="memory-file"
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.txt,application/pdf,image/png,image/jpeg,text/plain"
                  onChange={(event) => selectFile(event.target.files?.[0])}
                />
                <label
                  className={`dropzone ${isDragging ? 'dragging' : ''}`}
                  htmlFor="memory-file"
                  onDragEnter={() => setIsDragging(true)}
                  onDragOver={(event) => event.preventDefault()}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={(event) => {
                    event.preventDefault()
                    setIsDragging(false)
                    selectFile(event.dataTransfer.files?.[0])
                  }}
                >
                  <span className="upload-icon" aria-hidden="true">Upload</span>
                  <strong>{selectedFile ? selectedFile.name : 'Drop a file here or choose one'}</strong>
                  <span>{selectedFile ? formatFileSize(selectedFile.size) : 'PDF, PNG, JPEG, or TXT · Maximum 10 MB'}</span>
                </label>
                {uploadState === 'error' && <p className="upload-error" role="alert">{uploadError}</p>}
                <div className="upload-actions">
                  {selectedFile && <button className="text-button" type="button" onClick={resetUpload}>Clear selection</button>}
                  <button className="upload-button" type="button" disabled={!selectedFile || uploadState === 'uploading'} onClick={uploadFile}>
                    {uploadState === 'uploading' ? 'Uploading...' : 'Upload memory'}
                  </button>
                </div>
            </>
          </section>
          </div>
        )}

        <section className="recent-memories" aria-labelledby="recent-title">
          <div className="recent-header">
            <h2 id="recent-title">Recent Memories</h2>
            <span>{memoriesLoading ? 'Loading...' : recentMemories.length ? `${recentMemories.length} saved` : 'No uploads yet'}</span>
          </div>
          {memoriesError ? (
            <p className="memory-load-error" role="alert">{memoriesError}</p>
          ) : recentMemories.length ? (
            <div className="memory-list">
              {recentMemories.map((memory) => (
                <button className="memory-row" type="button" key={memory.id} onClick={() => openMemoryDetail(memory.id)}>
                  <div className="file-type-badge">{memory.file_type.toUpperCase()}</div>
                  <div className="memory-name"><strong>{memory.filename}</strong><span>{formatFileSize(memory.size)} · {formatUploadTime(memory.uploaded_at)}</span></div>
                  {memory.processing_status !== 'ready' && <span className={`memory-status ${memory.processing_status}`}>{memory.processing_status}</span>}
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="memory-mark" aria-hidden="true">✦</div>
              <h3>Your memories will gather here.</h3>
              <p>When you upload notes, documents, and screenshots, they will appear here for you to revisit.</p>
            </div>
          )}

          {detailState !== 'idle' && (
            <div className="memory-modal-backdrop">
            <section className="memory-detail" role="dialog" aria-modal="true" aria-live="polite" aria-labelledby="detail-title">
              <div className="memory-detail-heading">
                <div><p className="eyebrow">MEMORY DETAIL</p><h3 id="detail-title">{selectedMemory?.filename || 'Loading memory...'}</h3></div>
                <div className="memory-detail-actions">
                  {detailState === 'ready' && <button className="delete-memory" type="button" onClick={deleteMemory} disabled={deleteState === 'deleting'}>{deleteState === 'deleting' ? 'Deleting...' : 'Delete memory'}</button>}
                  <button className="close-upload" type="button" onClick={closeMemoryDetail}>Close</button>
                </div>
              </div>
              {detailState === 'loading' && <p className="detail-message">Loading saved memory...</p>}
              {detailState === 'error' && <p className="memory-load-error" role="alert">{detailError || 'Memory details could not be loaded.'}</p>}
              {detailState === 'ready' && detailError && <p className="memory-load-error" role="alert">{detailError}</p>}
              {detailState === 'ready' && selectedMemory && (
                <>
                  <h4 className="detail-section-title">Memory</h4>
                  <dl className="detail-metadata">
                    <div><dt>Type</dt><dd>{selectedMemory.file_type.toUpperCase()}</dd></div>
                    <div><dt>Uploaded</dt><dd>{formatUploadTime(selectedMemory.uploaded_at)}</dd></div>
                    <div><dt>Status</dt><dd>{selectedMemory.processing_status}</dd></div>
                  </dl>
                  {['png', 'jpeg'].includes(selectedMemory.file_type) && (
                    <div className="original-image">
                      <h4>Original image</h4>
                      <img src={`${apiBaseUrl}/api/memories/${selectedMemory.id}/image`} alt={`Original upload: ${selectedMemory.filename}`} />
                    </div>
                  )}
                  <div className="ai-understanding">
                    <div>
                      <h4>What this contains</h4>
                      <p>{selectedMemory.summary || 'AI understanding is not available for this memory yet.'}</p>
                    </div>
                    <div>
                      <h4>Why you may have saved this</h4>
                      <p>{selectedMemory.context_inference || 'This is an AI inference and is not available for this memory yet.'}</p>
                    </div>
                  </div>
                  <div className="extracted-content">
                    <h4>{['png', 'jpeg'].includes(selectedMemory.file_type) ? 'Understood content' : 'Extracted content'}</h4>
                    {selectedMemory.processing_status === 'failed' ? (
                      ['png', 'jpeg'].includes(selectedMemory.file_type)
                        ? <p>Image understanding could not be completed, so this image is not searchable yet.</p>
                        : <p>Text extraction could not be completed for this file.</p>
                    ) : selectedMemory.extracted_text ? (
                      <pre>{selectedMemory.extracted_text}</pre>
                    ) : (
                      <p>No extractable text was found in this file.</p>
                    )}
                  </div>
                </>
              )}
            </section>
            </div>
          )}
        </section>
        </div>
      </section>
    </main>
  )
}

export default App
