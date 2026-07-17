"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/lib/api";
import type {
  CondicoesSaudeInput,
  CondicoesSaudeResponse,
  ImcResponse,
  PerfilIncompletoResponse,
} from "@/lib/types";

/**
 * Consome `GET /perfil/imc`. Não trata o `422 PERFIL_INCOMPLETO` como
 * falha de query — é um estado de produto esperado — por isso o corpo de
 * erro estruturado é devolvido dentro do resultado (`perfilIncompleto`),
 * e só erros de fato inesperados (401/500/rede) ficam em `erro`.
 */
export function useImc() {
  const query = useQuery<ImcResponse, ApiError<PerfilIncompletoResponse>>({
    queryKey: ["perfil", "imc"],
    queryFn: () => apiFetch<ImcResponse>("/perfil/imc"),
    // 422 é estado de produto esperado, não falha transitória — não
    // adianta tentar de novo sem o usuário completar o perfil.
    retry: (falhas, error) => {
      if (error instanceof ApiError && error.status === 422) return false;
      return falhas < 1;
    },
  });

  const perfilIncompleto =
    query.error instanceof ApiError && query.error.status === 422
      ? query.error.body
      : null;

  const erroInesperado =
    query.error && !(query.error instanceof ApiError && query.error.status === 422)
      ? query.error
      : null;

  return {
    imc: query.data ?? null,
    perfilIncompleto,
    erroInesperado,
    carregando: query.isLoading,
    refazer: query.refetch,
  };
}

/**
 * Grava `condicoes_saude.esta_gestante` via `PATCH /perfil/condicoes-saude`.
 * Não há `GET` dedicado pra ler o valor atual hoje (só leitura interna
 * pelo cálculo de IMC) — este hook é só de escrita; quem chama decide
 * como refletir o valor recém-salvo (ex.: usar o retorno da mutation).
 * Invalida o cache de `/perfil/imc`, já que `esta_gestante` afeta a
 * elegibilidade do IMC.
 */
export function useAtualizarCondicoesSaude() {
  const queryClient = useQueryClient();
  return useMutation<CondicoesSaudeResponse, ApiError, CondicoesSaudeInput>({
    mutationFn: (payload) =>
      apiFetch<CondicoesSaudeResponse>("/perfil/condicoes-saude", {
        method: "PATCH",
        body: payload,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["perfil", "imc"] });
    },
  });
}
