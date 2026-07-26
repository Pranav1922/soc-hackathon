/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Override the API base URL in prod builds. Dev falls back to "/api" (Vite proxy → :8000). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
