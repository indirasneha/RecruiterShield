"use client";

import { useRef, useState } from "react";
import { Activity, ArrowUpRight, BadgeCheck, ChevronRight, CircleAlert, FileText, Fingerprint, LockKeyhole, ScanLine, Shield, ShieldAlert, ShieldCheck, Sparkles, UploadCloud } from "lucide-react";
import { analyzeDocument, analyzeMessage, type Analysis } from "@/lib/api";
import "./document.css";

const examples = ["A recruiter requested a processing fee", "They asked for an OTP or password", "The offer pressures me to act today"];

export default function Home() {
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("Reading the message");
  const [error, setError] = useState("");
  const [documentError, setDocumentError] = useState("");
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const documentInput = useRef<HTMLInputElement>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true); setLoadingLabel("Reading the message"); setError(""); setDocumentError("");
    try { setResult(await analyzeMessage(message)); }
    catch (e) { setError(e instanceof Error ? e.message : "Something went wrong. Please try again."); }
    finally { setLoading(false); }
  }

  async function uploadDocument(file?: File) {
    if (!file) return;
    setDocumentError(""); setError(""); setLoading(true); setLoadingLabel("Reviewing your offer letter"); setUploadProgress(0);
    try { setResult(await analyzeDocument(file, setUploadProgress)); }
    catch (e) { setDocumentError(e instanceof Error ? e.message : "The PDF could not be analyzed. Please try another file."); }
    finally { setLoading(false); setUploadProgress(null); if (documentInput.current) documentInput.current.value = ""; }
  }

  const riskTone = result?.risk_level.toLowerCase() ?? "";
  return <main className="shell">
    <header className="topbar">
      <a className="brand" href="#top" aria-label="RecruiterShield home"><span className="brand-mark"><Shield size={19} strokeWidth={2.4} /></span><span>Recruiter<span className="brand-light">Shield</span></span></a>
      <nav className="nav"><a href="#how-it-works">How it works</a><a href="#privacy">Privacy</a></nav>
      <a className="top-cta" href="#analyzer">Check a message <ArrowUpRight size={15} /></a>
    </header>

    <section className="hero" id="top">
      <div className="hero-copy">
        <div className="eyebrow"><span className="pulse-dot" /> YOUR FIRST LINE OF DEFENCE</div>
        <h1>Before you trust<br />the offer, <span>verify the<br className="mobile-break" /> opportunity.</span></h1>
        <p className="hero-sub">Recruitment scams are getting harder to spot. Get a clearer read on suspicious messages before you share your identity or say yes.</p>
        <div className="trust-row"><div className="avatar-stack"><span>R</span><span>S</span><span>A</span></div><span>Built to help students apply with confidence</span></div>
      </div>
      <div className="hero-visual" aria-hidden="true">
        <div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit orbit-three"/>
        <div className="shield-core"><div className="core-glow"/><ShieldCheck size={62} strokeWidth={1.25}/></div>
        <div className="float-card card-scan"><span className="float-icon"><ScanLine size={16}/></span><span><b>Message scan</b><small>Evidence-led review</small></span><span className="live-indicator"/></div>
        <div className="float-card card-privacy"><span className="float-icon purple"><Fingerprint size={16}/></span><span><b>Identity first</b><small>Your text isn’t stored</small></span></div>
        <div className="visual-caption"><span className="caption-line"/> A safer step before you reply</div>
      </div>
    </section>

    <section className="workspace" id="analyzer">
      <div className="section-heading"><div><div className="eyebrow muted-eyebrow">THE MESSAGE CHECK</div><h2>Take a closer look.</h2></div><div className="secure-note"><LockKeyhole size={14}/> Private by design</div></div>
      <div className="analysis-grid">
        <div className="input-card panel">
          <div className="panel-head"><div className="panel-icon"><ScanLine size={17}/></div><div><h3>Analyze a recruitment message</h3><p>Paste an email, text, or recruiter conversation.</p></div></div>
          <form onSubmit={submit}>
            <label className="sr-only" htmlFor="message">Recruitment message</label>
            <textarea id="message" maxLength={12000} value={message} onChange={e => setMessage(e.target.value)} placeholder="Paste the message here…\n\nYou can remove names and contact details first. Never include passwords or one-time codes." />
            <div className="input-meta"><span>{message.length.toLocaleString()} / 12,000</span><span><LockKeyhole size={12}/> Not saved</span></div>
            {error && <div role="alert" className="error-box"><CircleAlert size={16}/>{error}</div>}
            <button className="analyze-button" type="submit" disabled={loading || !message.trim()}>{loading ? <><span className="spinner"/> Reviewing message…</> : <>Analyze message <ChevronRight size={17}/></>}</button>
          </form>
          <div className="examples"><span>Try an example</span>{examples.map((item, i) => <button key={item} type="button" onClick={() => setMessage(["We need a $60 processing fee today to secure your internship.", "Send your password and OTP to complete recruiter verification.", "Act now, this offer expires today only. Message us on Telegram."][i])}>{item}</button>)}</div>
        </div>
        <div className={`results-card panel ${result ? "has-result" : ""}`} aria-live="polite">
          {!result && !loading ? <div className="empty-state"><div className="empty-art"><div className="empty-ring ring-a"/><div className="empty-ring ring-b"/><div className="empty-icon"><Shield size={28}/></div><span className="sparkle sparkle-a">✦</span><span className="sparkle sparkle-b">✧</span></div><div className="eyebrow muted-eyebrow">YOUR REVIEW</div><h3>Your results will appear here.</h3><p>Paste a recruitment message to see potential warning signs and practical next steps.</p><div className="empty-foot"><Activity size={14}/> Clear evidence. Practical guidance.</div></div> : loading ? <div className="loading-state"><div className="loading-emblem"><ScanLine size={27}/></div><div className="spinner large"/><h3>{loadingLabel}</h3><p>Looking for common recruitment warning signs…</p></div> : result && <div className="result-content">
            <div className="result-top"><div><div className="eyebrow muted-eyebrow">INITIAL REVIEW</div><h3>Here’s what stood out.</h3></div><span className="baseline-tag"><Sparkles size={12}/> {result.analysis_type === "ai_hybrid" ? "AI HYBRID" : "BASELINE FALLBACK"}</span></div>
            <div className={`risk-banner ${riskTone}`}><span className="risk-symbol">{result.risk_level === "HIGH" ? <ShieldAlert size={21}/> : result.risk_level === "MEDIUM" ? <CircleAlert size={21}/> : <ShieldCheck size={21}/>}</span><span><small>INDICATED RISK</small><b>{result.risk_level}</b></span><span className="risk-note">{result.risk_level === "HIGH" ? "Pause before responding" : result.risk_level === "MEDIUM" ? "Take time to verify" : "No obvious flags detected"}</span></div>
            {result.document_metadata && <div className="document-meta"><FileText size={13}/> {result.document_metadata.page_count} pages analyzed · {result.document_metadata.extraction_status.replaceAll("_", " ")}</div>}<div className="findings"><div className="subhead">Signals to consider <span>{result.findings.length}</span></div>{result.findings.length === 0 ? <div className="no-findings"><ShieldCheck size={16}/> No clear warning indicators were found.</div> : result.findings.map((finding, i) => <article className="finding" key={`${finding.category}-${i}`}><span className="finding-bullet"><CircleAlert size={14}/></span><div><h4>{finding.category}{finding.page_number && <small className="page-badge">PAGE {finding.page_number}</small>}</h4><p>{finding.explanation}</p><div className="evidence">“{finding.evidence.replace(/^The message includes “|”.$/g, "") }”</div></div></article>)}</div>
            <div className="actions"><div className="subhead">Your next steps</div>{result.recommended_actions.map((action, i) => <div className="action" key={action}><span>{String(i + 1).padStart(2, "0")}</span><p>{action}</p></div>)}</div>
            <p className="disclaimer"><CircleAlert size={14}/>{result.disclaimer}</p>
          </div>}
        </div>
      </div>
    </section>

    <section className="upload-strip" id="how-it-works" aria-busy={loading}>
      <input ref={documentInput} className="sr-only" type="file" accept="application/pdf,.pdf" aria-label="Choose an offer letter PDF" onChange={event => uploadDocument(event.target.files?.[0])}/>
      <div className="upload-icon"><FileText size={19}/></div>
      <div className="upload-copy"><h3>Have an offer letter to check?</h3><p>Upload a text-based PDF, up to 5 MB. Scanned documents are not supported yet.</p>
        {uploadProgress !== null && <div className="upload-progress-wrap"><div className="upload-progress-track"><div className="upload-progress-bar" style={{ width: `${uploadProgress}%` }}/></div><span>{uploadProgress === 100 ? "Upload complete · analyzing…" : `Uploading PDF · ${uploadProgress}%`}</span></div>}
        {documentError && <div role="alert" className="upload-error"><CircleAlert size={14}/>{documentError}</div>}
      </div>
      <button className="upload-button" type="button" disabled={loading} onClick={() => documentInput.current?.click()}><UploadCloud size={16}/>{loading && uploadProgress !== null ? "Uploading…" : "Upload PDF"}</button>
    </section>
    <section className="privacy-strip" id="privacy"><div className="privacy-lock"><LockKeyhole size={18}/></div><div><h3>Your privacy is part of your protection.</h3><p>The service does not persist submissions. Your text and result stay in this browser tab&apos;s memory until you leave or refresh. Remove personal details before pasting; never share passwords, OTPs, or full identity document numbers.</p></div><BadgeCheck size={20} className="privacy-check"/></section>
    <footer><a className="brand footer-brand" href="#top"><span className="brand-mark"><Shield size={15}/></span><span>Recruiter<span className="brand-light">Shield</span></span></a><span>Built with care for the next generation of talent.</span><span className="footer-status"><span/> SYSTEM READY</span></footer>
  </main>;
}
