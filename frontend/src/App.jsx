import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileSearch,
  FileText,
  Loader2,
  LockKeyhole,
  Paperclip,
  RotateCcw,
  Scale,
  Send,
  ShieldCheck,
  Upload
} from 'lucide-react';

const API_ENDPOINT = 'https://fema-fast-track.onrender.com/api/analyze-claim';

const starterMessage = {
  role: 'assistant',
  content:
    'Start with what happened. Include the date, ZIP code, what was damaged, and what help you need if you know those details.'
};

const fieldLabels = {
  date_of_incident: 'Incident date',
  zip_code: 'Damaged property ZIP code',
  disaster_type: 'Disaster type',
  damage_type: 'Primary damage type',
  damage_description: 'Damage description',
  receipts_or_estimates: 'Receipts, estimates, photos, or document status',
  requested_relief: 'Requested FEMA assistance',
  stafford_act_terms: 'Stafford Act terminology',
  statement_of_loss: 'Statement of loss',
  evidence_total: 'Evidence total',
  evidence_summary: 'Evidence summary'
};

const requiredFields = [
  'date_of_incident',
  'zip_code',
  'disaster_type',
  'damage_type',
  'damage_description',
  'receipts_or_estimates',
  'requested_relief'
];

function formatFieldName(field) {
  if (!field) return 'Additional detail';
  if (typeof field === 'object') {
    return field.label || field.name || field.field || field.key || 'Additional detail';
  }
  return fieldLabels[field] || String(field).replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function normalizeMissingFields(fields) {
  if (!fields) return [];
  if (Array.isArray(fields)) return fields;
  if (typeof fields === 'object') {
    return Object.entries(fields)
      .filter(([, value]) => value)
      .map(([key, value]) => (typeof value === 'string' ? value : key));
  }
  return [fields];
}

function claimValue(claim, key) {
  if (!claim) return null;
  const value = claim[key];
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'number') return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  return value;
}

function App() {
  const [messages, setMessages] = useState([starterMessage]);
  const [input, setInput] = useState('');
  const [files, setFiles] = useState([]);
  const [sessionState, setSessionState] = useState(null);
  const [claim, setClaim] = useState(null);
  const [missingFields, setMissingFields] = useState(requiredFields);
  const [pdfUrl, setPdfUrl] = useState('');
  const [filename, setFilename] = useState('fema-fast-track-claim.pdf');
  const [status, setStatus] = useState('needs_info');
  const [error, setError] = useState('');
  const [legalCitations, setLegalCitations] = useState([]);
  const [evidenceItems, setEvidenceItems] = useState([]);
  const [evidenceWarnings, setEvidenceWarnings] = useState([]);
  const [redTeamNotes, setRedTeamNotes] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  const missing = useMemo(() => normalizeMissingFields(missingFields), [missingFields]);
  const completedCount = requiredFields.filter((field) => !missing.includes(field)).length;
  const readiness = status === 'complete' ? 100 : Math.max(12, Math.round((completedCount / requiredFields.length) * 100));
  const canSubmit = input.trim().length > 0 && !isLoading;

  async function submitClaim(event) {
    event.preventDefault();
    const text = input.trim();
    if (!text) return;

    setMessages((current) => [...current, { role: 'user', content: text }]);
    setInput('');
    setError('');
    setIsLoading(true);

    const body = new FormData();
    body.append('text', text);
    if (sessionState) body.append('session_state', JSON.stringify(sessionState));
    files.forEach((file) => body.append('files', file));

    try {
      const response = await fetch(API_ENDPOINT, {
        method: 'POST',
        body
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.message || data?.error || 'The claim review service is unavailable right now.');
      }

      const nextStatus = data?.status === 'complete' ? 'complete' : 'needs_info';
      const nextQuestion =
        data?.refusal ||
        data?.question ||
        (nextStatus === 'complete'
          ? 'Your claim packet is ready. Review the right side, then download the PDF.'
          : 'I need one more detail before I can finish the packet.');

      setStatus(nextStatus);
      setMissingFields(normalizeMissingFields(data?.missing_fields));
      setClaim(data?.claim || null);
      setPdfUrl(data?.pdf_url || '');
      setFilename(data?.filename || 'fema-fast-track-claim.pdf');
      setSessionState(data?.session_state ?? null);
      setLegalCitations(data?.legal_citations || []);
      setEvidenceItems(data?.evidence_items || []);
      setEvidenceWarnings(data?.evidence_warnings || []);
      setRedTeamNotes(data?.red_team_notes || []);
      setFiles([]);
      setMessages((current) => [...current, { role: 'assistant', content: nextQuestion }]);
    } catch (caughtError) {
      setError(caughtError.message);
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: 'I could not reach the local claim service. Your notes are still here, so you can try again.'
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  function resetIntake() {
    setMessages([starterMessage]);
    setInput('');
    setFiles([]);
    setSessionState(null);
    setClaim(null);
    setMissingFields(requiredFields);
    setPdfUrl('');
    setFilename('fema-fast-track-claim.pdf');
    setStatus('needs_info');
    setError('');
    setLegalCitations([]);
    setEvidenceItems([]);
    setEvidenceWarnings([]);
    setRedTeamNotes([]);
  }

  return (
    <main className="app-shell">
      <section className="workspace" aria-labelledby="app-title">
        <header className="topbar">
          <div className="brand-block">
            <p className="eyebrow">FEMA Fast-Track</p>
            <h1 id="app-title">Turn disaster notes into a claim-ready packet.</h1>
            <p className="lead">
              Type the story, answer the follow-up questions, upload receipts if you have them, then download the reviewed PDF.
            </p>
          </div>
          <div className="privacy-strip" aria-label="Privacy details">
            <span>
              <LockKeyhole size={16} aria-hidden="true" />
              Local only
            </span>
            <span>
              <ShieldCheck size={16} aria-hidden="true" />
              No database
            </span>
            <span>
              <Scale size={16} aria-hidden="true" />
              Cited context
            </span>
          </div>
        </header>

        <div className="process-bar" aria-label="Claim process">
          <div className="process-step active">
            <strong>1</strong>
            <span>Tell the story</span>
          </div>
          <div className={`process-step ${claim ? 'active' : ''}`}>
            <strong>2</strong>
            <span>Fill gaps</span>
          </div>
          <div className={`process-step ${legalCitations.length ? 'active' : ''}`}>
            <strong>3</strong>
            <span>Retrieve law</span>
          </div>
          <div className={`process-step ${status === 'complete' ? 'active' : ''}`}>
            <strong>4</strong>
            <span>Download PDF</span>
          </div>
        </div>

        <div className="columns">
          <section className="panel intake-panel" aria-labelledby="intake-title">
            <div className="panel-header">
              <div>
                <p className="section-kicker">Start here</p>
                <h2 id="intake-title">What happened?</h2>
              </div>
              <FileText size={24} aria-hidden="true" />
            </div>

            {error ? (
              <div className="error-banner" role="alert">
                <AlertTriangle size={18} aria-hidden="true" />
                <span>{error}</span>
              </div>
            ) : null}

            <div className="chat-log" aria-live="polite" aria-busy={isLoading}>
              {messages.map((message, index) => (
                <article className={`message ${message.role}`} key={`${message.role}-${index}`}>
                  <span className="message-label">{message.role === 'user' ? 'You' : 'Fast-Track'}</span>
                  <p>{message.content}</p>
                </article>
              ))}
              {isLoading ? (
                <article className="message assistant loading-message">
                  <span className="message-label">Fast-Track</span>
                  <p>
                    <Loader2 className="spin" size={16} aria-hidden="true" />
                    Checking facts, evidence, and Stafford Act context...
                  </p>
                </article>
              ) : null}
            </div>

            <form className="composer" onSubmit={submitClaim}>
              <label htmlFor="claim-notes">Your answer</label>
              <textarea
                id="claim-notes"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Example: On March 18, a storm knocked a tree into my roof in 78704. Water came in and the house is unsafe. I need home repair help."
                rows={6}
              />

              <div className="upload-row">
                <label className="upload-control" htmlFor="evidence-files">
                  <Upload size={18} aria-hidden="true" />
                  <span>{files.length ? `${files.length} file(s) selected` : 'Add receipts or estimates'}</span>
                </label>
                <input
                  id="evidence-files"
                  type="file"
                  accept="image/*,.pdf"
                  multiple
                  onChange={(event) => setFiles(Array.from(event.target.files || []))}
                />
                <span className="upload-hint">PDF, JPG, PNG</span>
              </div>

              <div className="composer-actions">
                <button className="secondary-button" type="button" onClick={resetIntake}>
                  <RotateCcw size={17} aria-hidden="true" />
                  <span>Reset</span>
                </button>
                <button className="primary-button" type="submit" disabled={!canSubmit}>
                  {isLoading ? <Loader2 className="spin" size={18} aria-hidden="true" /> : <Send size={18} aria-hidden="true" />}
                  <span>{isLoading ? 'Reviewing' : 'Send answer'}</span>
                </button>
              </div>
            </form>
          </section>

          <aside className="panel status-panel" aria-labelledby="status-title">
            <div className="panel-header">
              <div>
                <p className="section-kicker">Claim status</p>
                <h2 id="status-title">{status === 'complete' ? 'Ready to download' : 'Next answer needed'}</h2>
              </div>
              {status === 'complete' ? (
                <CheckCircle2 className="success-icon" size={25} aria-hidden="true" />
              ) : (
                <ClipboardCheck size={25} aria-hidden="true" />
              )}
            </div>

            <div className="progress-card">
              <div className="progress-row">
                <span>Packet readiness</span>
                <strong>{readiness}%</strong>
              </div>
              <div className="progress-track" aria-hidden="true">
                <span style={{ width: `${readiness}%` }} />
              </div>
            </div>

            <section className="status-section" aria-labelledby="checklist-title">
              <h3 id="checklist-title">Required details</h3>
              <ul className="detail-list">
                {requiredFields.map((field) => {
                  const value = claimValue(claim, field);
                  const isDone = status === 'complete' || Boolean(value);
                  return (
                    <li className={isDone ? 'done' : ''} key={field}>
                      {isDone ? <CheckCircle2 size={17} aria-hidden="true" /> : <AlertTriangle size={17} aria-hidden="true" />}
                      <span>{formatFieldName(field)}</span>
                    </li>
                  );
                })}
              </ul>
            </section>

            <section className="status-section" aria-labelledby="evidence-title">
              <h3 id="evidence-title">Evidence and legal checks</h3>
              <div className="check-grid">
                <div>
                  <Paperclip size={18} aria-hidden="true" />
                  <strong>{evidenceItems.length}</strong>
                  <span>file(s) read</span>
                </div>
                <div>
                  <FileSearch size={18} aria-hidden="true" />
                  <strong>{legalCitations.length}</strong>
                  <span>citation(s)</span>
                </div>
              </div>
              {[...evidenceWarnings, ...redTeamNotes].length ? (
                <ul className="warning-list">
                  {[...evidenceWarnings, ...redTeamNotes].map((warning, index) => (
                    <li key={`${warning}-${index}`}>{warning}</li>
                  ))}
                </ul>
              ) : null}
            </section>

            <section className="status-section" aria-labelledby="summary-title">
              <h3 id="summary-title">Claim preview</h3>
              {claim ? (
                <dl className="claim-summary">
                  {['date_of_incident', 'zip_code', 'disaster_type', 'damage_type', 'evidence_total'].map((key) => (
                    <div key={key}>
                      <dt>{formatFieldName(key)}</dt>
                      <dd>{claimValue(claim, key) || 'Not provided'}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <div className="document-placeholder">
                  <FileText size={24} aria-hidden="true" />
                  <span>Your claim preview appears after the first answer.</span>
                </div>
              )}
            </section>

            <a
              className={`download-button ${status === 'complete' && pdfUrl ? '' : 'disabled'}`}
              href={status === 'complete' && pdfUrl ? pdfUrl : undefined}
              download={filename}
              aria-disabled={status !== 'complete' || !pdfUrl}
              onClick={(event) => {
                if (status !== 'complete' || !pdfUrl) event.preventDefault();
              }}
            >
              <Download size={18} aria-hidden="true" />
              <span>{status === 'complete' && pdfUrl ? 'Download reviewed PDF' : 'Answer missing details first'}</span>
            </a>
          </aside>
        </div>
      </section>
    </main>
  );
}

export default App;
