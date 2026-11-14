export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type Analysis = {
  risk_level: RiskLevel;
  findings: { category: string; explanation: string; evidence: string; page_number?: number | null }[];
  recommended_actions: string[];
  disclaimer: string;
  analysis_type: string;
  document_metadata?: { page_count: number; pages_with_text: number; extraction_status: string; size_bytes: number } | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function errorMessage(response: Response): Promise<string> {
  const payload = await response.json().catch(() => null);
  const detail = Array.isArray(payload?.detail) ? payload.detail[0]?.msg : payload?.detail;
  return typeof detail === "string" ? detail : "The service could not complete this analysis. Please try again.";
}

export async function analyzeMessage(text: string): Promise<Analysis> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/analyze/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch {
    throw new Error("Could not reach the analysis service. Check that the backend is running.");
  }
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  return response.json() as Promise<Analysis>;
}

export async function analyzeDocument(file: File, onProgress: (percent: number) => void): Promise<Analysis> {
  if (!file.name.toLowerCase().endsWith(".pdf") || (file.type && file.type !== "application/pdf")) {
    throw new Error("Choose a PDF file to analyze.");
  }
  if (file.size === 0) throw new Error("The selected PDF is empty.");
  if (file.size > 5 * 1024 * 1024) throw new Error("The PDF exceeds the 5 MB upload limit.");

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/analyze/document`);
    xhr.setRequestHeader("Content-Type", "application/pdf");
    xhr.upload.onprogress = event => {
      if (event.lengthComputable) onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    };
    xhr.onerror = () => reject(new Error("Could not reach the analysis service. Check that the backend is running."));
    xhr.onabort = () => reject(new Error("The PDF upload was cancelled."));
    xhr.onload = () => {
      let payload: Analysis | { detail?: unknown };
      try { payload = JSON.parse(xhr.responseText) as Analysis | { detail?: unknown }; }
      catch { reject(new Error("The analysis service returned an unreadable response.")); return; }
      if (xhr.status < 200 || xhr.status >= 300) {
        const detail = (payload as { detail?: unknown }).detail;
        reject(new Error(typeof detail === "string" ? detail : "The PDF could not be analyzed. Please check the file and try again."));
        return;
      }
      resolve(payload as Analysis);
    };
    xhr.send(file);
  });
}
