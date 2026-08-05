const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type User = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  organization_id: string;
};

function authHeaders(): HeadersInit {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const auth = authHeaders();
  Object.entries(auth).forEach(([k, v]) => headers.set(k, v as string));
  if (!(options.body instanceof FormData) && !headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    throw new Error(
      "Impossible de joindre l’API (Failed to fetch). Vérifiez que le backend tourne sur http://localhost:8000."
    );
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; refresh_token: string }>("/api/auth/login/json", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>("/api/auth/me"),
  documents: () => request<DocumentItem[]>("/api/documents"),
  uploadDocument: (title: string, file: File) => {
    const form = new FormData();
    form.append("title", title);
    form.append("file", file);
    return request<DocumentItem>("/api/documents/upload", { method: "POST", body: form });
  },
  deleteDocument: (id: string) => request<void>(`/api/documents/${id}`, { method: "DELETE" }),
  chat: (message: string, conversationId?: string, documentId?: string) =>
    request<{ conversation_id: string; answer: string; citations: Citation[] }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        conversation_id: conversationId || null,
        document_id: documentId || null,
      }),
    }),
  conversations: () => request<ConversationItem[]>("/api/chat/conversations"),
  deleteConversation: (id: string) =>
    request<void>(`/api/chat/conversations/${id}`, { method: "DELETE" }),
  deleteAllConversations: () => request<void>("/api/chat/conversations", { method: "DELETE" }),
  messages: (id: string) => request<MessageItem[]>(`/api/chat/conversations/${id}/messages`),
  exercises: () => request<ExerciseItem[]>("/api/exercises"),
  exercise: (id: string) => request<ExerciseItem>(`/api/exercises/${id}`),
  generateExercise: (payload: {
    document_id: string;
    exercise_type: string;
    title?: string;
    topic?: string;
    question_count?: number;
    time_limit_seconds?: number;
  }) =>
    request<ExerciseItem>("/api/exercises/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  submitAttempt: (id: string, answers: Record<string, unknown>, duration_seconds?: number) =>
    request<AttemptItem>(`/api/exercises/${id}/attempts`, {
      method: "POST",
      body: JSON.stringify({ answers, duration_seconds }),
    }),
  myAttempts: () => request<AttemptItem[]>("/api/exercises/attempts/me"),
  learnerStats: () => request<LearnerStats>("/api/dashboard/learner"),
  trainerStats: () => request<TrainerStats>("/api/dashboard/trainer"),
  exportCsvUrl: () => `${API_URL}/api/dashboard/trainer/export.csv`,
  grammar: (text: string, language = "fr") =>
    request<{ corrected_text: string; explanations: string[] }>("/api/languages/grammar", {
      method: "POST",
      body: JSON.stringify({ text, language }),
    }),
  comprehension: (document_id: string, question_count = 3) =>
    request<Record<string, unknown>>("/api/languages/comprehension", {
      method: "POST",
      body: JSON.stringify({ document_id, question_count }),
    }),
  pronunciation: async (reference_text: string, audio?: File) => {
    const form = new FormData();
    form.append("reference_text", reference_text);
    if (audio) form.append("audio", audio);
    return request<Record<string, unknown>>("/api/languages/pronunciation", {
      method: "POST",
      body: form,
    });
  },
};

export type DocumentItem = {
  id: string;
  title: string;
  filename: string;
  status: string;
  error_message?: string | null;
  created_at: string;
};

export type Citation = {
  document_id: string;
  document_title: string;
  chunk_index: number;
  excerpt: string;
};

export type ConversationItem = { id: string; title: string; created_at: string };
export type MessageItem = {
  id: string;
  role: string;
  content: string;
  citations?: Citation[] | null;
  created_at: string;
};

export type ExerciseItem = {
  id: string;
  title: string;
  exercise_type: string;
  topic?: string | null;
  payload: Record<string, unknown>;
  time_limit_seconds?: number | null;
  document_id?: string | null;
  created_at: string;
};

export type AttemptItem = {
  id: string;
  exercise_id: string;
  score: number | null;
  max_score: number | null;
  feedback: Record<string, unknown> | null;
  weak_topics: string[] | null;
  duration_seconds: number | null;
  created_at: string;
};

export type LearnerStats = {
  attempts_count: number;
  average_score: number | null;
  documents_available: number;
  weak_topics: string[];
  recent_attempts: AttemptItem[];
};

export type TrainerStats = {
  learners_count: number;
  documents_count: number;
  indexed_documents: number;
  attempts_count: number;
  average_score: number | null;
  recurrent_weak_topics: { topic: string; count: number }[];
  score_by_exercise_type: { exercise_type: string; average_score: number }[];
};
