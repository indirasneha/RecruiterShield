"use client";

import { useRef, useState } from "react";
import {
  Activity, ArrowRight, ArrowUpRight, BadgeCheck, Check, ChevronRight,
  CircleAlert, Clipboard, FileText, Fingerprint, LockKeyhole, ScanLine,
  Shield, ShieldAlert, ShieldCheck, Sparkles, UploadCloud, X,
} from "lucide-react";
import { analyzeDocument, analyzeMessage, type Analysis } from "@/lib/api";
import "./document.css";

const examples = [
  {
    label: "Candidate-paid fee",
    text: "For this internship, pay a refundable processing charge before we can issue your appointment letter.",
  },
  {
    label: "Credential request",
    text: "The interview is scheduled for Thursday. Read back the six-digit code from your authenticator app to activate your candidate account.",
  },
  {
    label: "Routine interview",
    text: "Thank you for applying. Would Tuesday or Thursday suit you for a video interview with the hiring team?",
  },
];

function summaryText(result: Analysis, source: string) {
  const lines = [
    `RecruiterShield ${source} review: ${result.risk_level} risk`,
    `Engine: ${result.analysis_type === "ai_hybrid" ? "AI hybrid" : "Baseline fallback"}`,
    "",
    "Findings:",
    ...(result.findings.length
      ? result.findings.flatMap((finding) => [
          `• ${finding.category}${finding.page_number ? ` (page ${finding.page_number})` : ""}`,
          `  Why it matters: ${finding.explanation}`,
          `  Evidence: ${finding.evidence}`,
        ])
      : ["• No clear warning indicators were found."]),
    "",
    "Recommended next steps:",
    ...result.recommended_actions.map((action) => `• ${action}`),
    "",
    result.disclaimer,
  ];
  return lines.join("\n");
}

export default function Home() {
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<Analysis | null>(null);
  const [resultSource, setResultSource] = useState("message");
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("Reviewing the message");
  const [error, setError] = useState("");
  const [documentError, setDocumentError] = useState("");
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");
  const documentInput = useRef<HTMLInputElement>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setLoadingLabel("Reviewing the message");
    setError("");
    setDocumentError("");
    setCopyState("idle");
    try {
      setResult(await analyzeMessage(message));
      setResultSource("message");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The message could not be analyzed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function uploadDocument(file?: File) {
    if (!file) return;
    setDocumentError("");
    setError("");
    setLoading(true);
    setLoadingLabel("Extracting and reviewing the offer");
    setUploadProgress(0);
    setCopyState("idle");
    try {
      setResult(await analyzeDocument(file, setUploadProgress));
      setResultSource("offer document");
    } catch (cause) {
      setDocumentError(cause instanceof Error ? cause.message : "The PDF could not be analyzed. Check the file and try again.");
    } finally {
      setLoading(false);
      setUploadProgress(null);
      if (documentInput.current) documentInput.current.value = "";
    }
  }

  async function copySummary() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(summaryText(result, resultSource));
      setCopyState("copied");
    } catch {
      setCopyState("error");
    }
  }

  const riskTone = result?.risk_level.toLowerCase() ?? "";
  const riskMessage = result?.risk_level === "HIGH"
    ? "Pause. Do not send money, identity documents, bank details, passwords, or one-time codes."
    : result?.risk_level === "MEDIUM"
      ? "Some details need independent checking before you respond or share information."
      : "No strong warning signal was identified. LOW risk does not prove an opportunity is safe.";

  return (
    <main className="shell" id="top">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="RecruiterShield home">
          <span className="brand-mark"><Shield size={18} strokeWidth={2.4} /></span>
          <span>Recruiter<span className="brand-light">Shield</span></span>
        </a>
        <nav className="nav" aria-label="Main navigation">
          <a href="#analyzer">Analyze</a><a href="#how-it-works">How it works</a><a href="#privacy">Privacy</a>
        </nav>
        <a className="top-cta" href="#analyzer">Start a review <ArrowUpRight size={15} /></a>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow"><span className="pulse-dot" /> A SAFER FIRST STEP</div>
          <h1>Before you trust the offer, <span>check the signals.</span></h1>
          <p className="hero-sub">Review recruitment messages and offer letters for common fraud and identity-harvesting warning signs. See what stood out and what to do next.</p>
          <div className="hero-points">
            <span><ScanLine size={15} /> Evidence-led review</span>
            <span><LockKeyhole size={15} /> No submissions stored</span>
          </div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit orbit-three" />
          <div className="shield-core"><div className="core-glow" /><ShieldCheck size={58} strokeWidth={1.35} /></div>
          <div className="float-card card-scan"><span className="float-icon"><ScanLine size={16} /></span><span><b>Review the request</b><small>Signals with evidence</small></span></div>
          <div className="float-card card-privacy"><span className="float-icon purple"><Fingerprint size={16} /></span><span><b>Keep identity safe</b><small>Verify through official channels</small></span></div>
        </div>
      </section>

      <section className="workspace" id="analyzer">
        <div className="section-heading">
          <div><div className="eyebrow muted-eyebrow">RECRUITMENT CHECK</div><h2>What would you like to review?</h2></div>
          <div className="secure-note"><LockKeyhole size={14} /> Processed for this review</div>
        </div>

        <div className="analysis-grid" aria-busy={loading}>
          <section className="input-card panel" aria-labelledby="message-title">
            <div className="panel-head">
              <div className="panel-icon"><ScanLine size={17} /></div>
              <div><h3 id="message-title">Analyze a message</h3><p>Paste an email, SMS, or recruiter conversation.</p></div>
            </div>
            <form onSubmit={submit}>
              <label className="sr-only" htmlFor="message">Recruitment message</label>
              <textarea id="message" maxLength={12000} value={message} onChange={(event) => setMessage(event.target.value)} placeholder={"Paste the message here…\n\nRemove names and contact details first. Never include passwords or one-time codes."} aria-describedby="message-help message-count" />
              <div className="input-meta" id="message-help"><span id="message-count">{message.length.toLocaleString()} / 12,000 characters</span><span><LockKeyhole size={12} /> Not saved by the service</span></div>
              {error && <div role="alert" className="error-box"><CircleAlert size={16} />{error}</div>}
              <button className="analyze-button" type="submit" disabled={loading || !message.trim()}>
                {loading && loadingLabel === "Reviewing the message" ? <><span className="spinner" /> Reviewing message…</> : <>Analyze message <ChevronRight size={17} /></>}
              </button>
            </form>
            <div className="examples" aria-label="Synthetic example messages">
              <div className="examples-heading"><span>Try a synthetic example</span><small>Click to fill; it will not submit</small></div>
              <div className="example-buttons">
                {examples.map((example) => <button key={example.label} type="button" onClick={() => { setMessage(example.text); setError(""); }}><span>{example.label}</span><ArrowRight size={13} /></button>)}
              </div>
            </div>
          </section>

          <section className={`results-card panel ${result ? "has-result" : ""}`} aria-labelledby="results-title" aria-live="polite" aria-busy={loading}>
            {!result && !loading ? (
              <div className="empty-state">
                <div className="empty-icon"><Shield size={27} /></div>
                <div className="eyebrow muted-eyebrow">YOUR REVIEW</div>
                <h3 id="results-title">Analysis appears here</h3>
                <p>Start with a message or PDF. We’ll show potential warning signs, supporting evidence, and practical steps.</p>
                <div className="empty-foot"><Activity size={14} /> Risk review, not identity verification</div>
              </div>
            ) : loading ? (
              <div className="loading-state" role="status">
                <div className="loading-emblem"><ScanLine size={25} /></div>
                <span className="spinner large" />
                <h3 id="results-title">{loadingLabel}</h3>
                <p>{uploadProgress !== null ? `Uploading PDF · ${uploadProgress}%` : "Checking the wording and context for warning signs…"}</p>
                {uploadProgress !== null && <div className="upload-progress-track" aria-label={`Upload progress ${uploadProgress}%`}><div className="upload-progress-bar" style={{ width: `${uploadProgress}%` }} /></div>}
              </div>
            ) : result && (
              <div className="result-content">
                <div className="result-top">
                  <div><div className="eyebrow muted-eyebrow">INITIAL RISK REVIEW</div><h3 id="results-title">Review summary</h3></div>
                  <div className={`engine-tag ${result.analysis_type === "ai_hybrid" ? "engine-ai" : "engine-fallback"}`} title={result.analysis_type === "ai_hybrid" ? "The trained text classifier and contextual checks were used." : "The trained model was unavailable; contextual checks were used."}>
                    {result.analysis_type === "ai_hybrid" ? <Sparkles size={13} /> : <Activity size={13} />}
                    {result.analysis_type === "ai_hybrid" ? "AI HYBRID" : "BASELINE FALLBACK"}
                  </div>
                </div>
                <div className={`risk-banner ${riskTone}`} role="status" aria-label={`${result.risk_level} indicated risk`}>
                  <span className="risk-symbol" aria-hidden="true">{result.risk_level === "HIGH" ? <ShieldAlert size={23} /> : result.risk_level === "MEDIUM" ? <CircleAlert size={23} /> : <ShieldCheck size={23} />}</span>
                  <span className="risk-label"><small>INDICATED RISK</small><b>{result.risk_level}</b></span>
                  <span className="risk-note">{riskMessage}</span>
                </div>
                {result.document_metadata && <div className="document-meta"><FileText size={14} /><span>{result.document_metadata.page_count} pages reviewed</span><span className="meta-divider">·</span><span>{result.document_metadata.extraction_status.replaceAll("_", " ")}</span></div>}
                <div className="findings">
                  <div className="subhead">Findings <span>{result.findings.length}</span></div>
                  {result.findings.length === 0 ? <div className="no-findings"><ShieldCheck size={16} /><span>No clear warning indicators were identified in this review.</span></div> : result.findings.map((finding, index) => (
                    <article className="finding" key={`${finding.category}-${finding.page_number ?? "message"}-${index}`}>
                      <span className="finding-bullet" aria-hidden="true"><CircleAlert size={16} /></span>
                      <div className="finding-copy">
                        <h4>{finding.category}{finding.page_number && <small className="page-badge">PAGE {finding.page_number}</small>}</h4>
                        <p>{finding.explanation}</p>
                        <div className="evidence-label">Supporting evidence</div>
                        <blockquote className="evidence">{finding.evidence}</blockquote>
                      </div>
                    </article>
                  ))}
                </div>
                <div className="actions">
                  <div className="subhead">Recommended next steps</div>
                  <ol>{result.recommended_actions.map((action) => <li className="action" key={action}><span aria-hidden="true"><Check size={13} /></span><p>{action}</p></li>)}</ol>
                </div>
                <div className="verification-note"><BadgeCheck size={16} /><p><strong>This is not recruiter verification.</strong> The review assesses submitted wording; it does not authenticate the recruiter, company, offer, or links.</p></div>
                <p className="disclaimer"><CircleAlert size={14} />{result.disclaimer}</p>
                <div className="result-footer">
                  <span>{result.analysis_type === "ai_hybrid" ? "Hybrid classifier + contextual checks" : "Contextual checks only"}</span>
                  <button className="copy-button" type="button" onClick={copySummary} aria-label="Copy analysis summary"><Clipboard size={14} />{copyState === "copied" ? "Copied" : "Copy summary"}</button>
                </div>
                {copyState === "error" && <div className="copy-error" role="status"><X size={13} /> Clipboard unavailable. Select and copy the result text manually.</div>}
              </div>
            )}
          </section>
        </div>
      </section>

      <section className="upload-strip" id="how-it-works" aria-labelledby="upload-title" aria-busy={loading && uploadProgress !== null}>
        <input ref={documentInput} className="sr-only" type="file" accept="application/pdf,.pdf" aria-label="Choose an offer letter PDF" onChange={(event) => uploadDocument(event.target.files?.[0])} />
        <div className="upload-icon"><FileText size={19} /></div>
        <div className="upload-copy">
          <h3 id="upload-title">Or review an offer letter PDF</h3>
          <p>Text-based PDFs only · maximum 5 MB · scanned/image-only PDFs are not supported.</p>
          {documentError && <div role="alert" className="upload-error"><CircleAlert size={14} />{documentError}</div>}
          {uploadProgress !== null && <div className="upload-progress-wrap"><div className="upload-progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={uploadProgress}><div className="upload-progress-bar" style={{ width: `${uploadProgress}%` }} /></div><span>{uploadProgress === 100 ? "Upload complete · analyzing" : `${uploadProgress}% uploaded`}</span></div>}
        </div>
        <button className="upload-button" type="button" disabled={loading} onClick={() => documentInput.current?.click()}><UploadCloud size={16} />{loading && uploadProgress !== null ? "Uploading PDF…" : "Choose PDF"}</button>
      </section>

      <section className="privacy-strip" id="privacy" aria-labelledby="privacy-title">
        <div className="privacy-lock"><LockKeyhole size={18} /></div>
        <div><h3 id="privacy-title">Your privacy is part of your protection.</h3><p>The service does not persist submitted messages, extracted document text, or uploaded PDFs. Results remain in this browser tab’s memory until you leave or refresh. Remove personal details before analysis; never share passwords, OTPs, or full identity document numbers.</p></div>
        <BadgeCheck size={20} className="privacy-check" aria-hidden="true" />
      </section>
      <footer>
        <a className="brand footer-brand" href="#top"><span className="brand-mark"><Shield size={15} /></span><span>Recruiter<span className="brand-light">Shield</span></span></a>
        <span>Make room for careful decisions.</span>
        <a className="footer-top" href="#top">Back to top <ArrowUpRight size={13} /></a>
      </footer>
    </main>
  );
}
