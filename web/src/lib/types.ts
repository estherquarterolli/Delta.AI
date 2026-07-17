/** Tipos espelhando os schemas Pydantic do backend (fonte de verdade:
 * `app/modules/perfil/schemas.py` e `app/modules/pesagens/schemas.py`). */

export type MotivoBloqueio = "menor_de_18" | "gestante";

export type Classificacao =
  | "abaixo_do_peso"
  | "peso_normal"
  | "sobrepeso"
  | "obesidade_grau_1"
  | "obesidade_grau_2"
  | "obesidade_grau_3";

export type CampoFaltante = "altura_cm" | "data_nascimento" | "peso";

/** Corpo de `GET /perfil/imc` (200), cobrindo elegível e bloqueado. */
export interface ImcResponse {
  elegivel: boolean;
  motivo_bloqueio: MotivoBloqueio | null;
  mensagem: string | null;
  imc: number | null;
  classificacao: Classificacao | null;
  classificacao_label: string | null;
  peso_kg: number | null;
  altura_cm: number | null;
  pesagem_registrada_em: string | null;
  calculado_em: string;
}

/** Corpo de `422 PERFIL_INCOMPLETO` de `GET /perfil/imc`. */
export interface PerfilIncompletoResponse {
  erro: "PERFIL_INCOMPLETO";
  mensagem: string;
  campos_faltantes: CampoFaltante[];
}

/** Pesagem retornada pela API (`GET/POST/PUT /pesagens`). */
export interface Pesagem {
  id: string;
  peso_kg: number;
  registrada_em: string;
  created_at: string;
  updated_at: string;
}

export interface PesagemCreateInput {
  peso_kg: number;
  registrada_em?: string;
}

export interface PesagemUpdateInput {
  peso_kg?: number;
  registrada_em?: string;
}

/** Corpo de request/response de `PATCH /perfil/condicoes-saude`. */
export interface CondicoesSaudeInput {
  esta_gestante: boolean;
}

export type CondicoesSaudeResponse = CondicoesSaudeInput;
