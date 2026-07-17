import { supabase } from "./supabase";

/**
 * Wrapper único de chamadas ao backend FastAPI. Toda chamada de dado do
 * produto (perfil, IMC, pesagens, e futuramente nutrição/treinos/etc.)
 * passa por aqui — nunca `fetch` direto em componente/hook (ver CLAUDE.md
 * e regras do `frontend-engineer`). Responsabilidades:
 *
 * - Resolve a URL base a partir de `NEXT_PUBLIC_API_URL`.
 * - Anexa o JWT da sessão Supabase atual como `Authorization: Bearer`.
 * - Normaliza erros HTTP (4xx/5xx) em `ApiError`, preservando o corpo
 *   original — módulos como IMC precisam do corpo de erro estruturado
 *   (`campos_faltantes`, etc.), não só uma mensagem genérica.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Erro de chamada à API com status HTTP e corpo já parseado (se houver). */
export class ApiError<TBody = unknown> extends Error {
  readonly status: number;
  readonly body: TBody | null;

  constructor(message: string, status: number, body: TBody | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/** Erro de rede/timeout — nunca chegou a ter uma resposta HTTP. */
export class ApiNetworkError extends Error {
  constructor(cause: unknown) {
    super("Não foi possível conectar ao servidor. Verifique sua conexão.");
    this.name = "ApiNetworkError";
    this.cause = cause;
  }
}

async function getAuthHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
}

/**
 * Executa uma chamada autenticada ao backend. `TResponse` é o tipo do
 * corpo de sucesso; `path` é relativo (ex.: `/perfil/imc`).
 *
 * Lança `ApiError` para qualquer resposta não-2xx (o caller decide como
 * tratar cada status — 401, 404, 422 têm significados de produto
 * distintos e nunca devem cair na mesma tela de erro genérica).
 * Lança `ApiNetworkError` se a requisição nem chegou a ter resposta.
 */
export async function apiFetch<TResponse>(
  path: string,
  options: RequestOptions = {}
): Promise<TResponse> {
  const authHeader = await getAuthHeader();

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: options.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        ...authHeader,
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch (cause) {
    throw new ApiNetworkError(cause);
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const parsedBody = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : null;

  if (!response.ok) {
    throw new ApiError(
      `Erro ${response.status} em ${path}`,
      response.status,
      parsedBody
    );
  }

  return parsedBody as TResponse;
}
