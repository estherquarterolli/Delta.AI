"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/lib/api";
import type { Pesagem, PesagemCreateInput, PesagemUpdateInput } from "@/lib/types";

const QUERY_KEY = ["pesagens"];

/** Lista o histórico de pesagens do usuário (mais recente primeiro —
 * contrato já garantido pelo backend, `GET /pesagens`). */
export function usePesagens() {
  const query = useQuery<Pesagem[], ApiError>({
    queryKey: QUERY_KEY,
    queryFn: () => apiFetch<Pesagem[]>("/pesagens"),
  });

  return {
    pesagens: query.data ?? [],
    carregando: query.isLoading,
    erro: query.error,
    refazer: query.refetch,
  };
}

/** Busca uma pesagem específica a partir da lista em cache (evita um
 * endpoint `GET /pesagens/{id}` que o backend não expõe). */
export function usePesagem(id: string) {
  const { pesagens, carregando, erro, refazer } = usePesagens();
  const pesagem = pesagens.find((p) => p.id === id) ?? null;
  return { pesagem, carregando, erro, refazer };
}

export function useCriarPesagem() {
  const queryClient = useQueryClient();
  return useMutation<Pesagem, ApiError, PesagemCreateInput>({
    mutationFn: (payload) => apiFetch<Pesagem>("/pesagens", { method: "POST", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}

export function useEditarPesagem(id: string) {
  const queryClient = useQueryClient();
  return useMutation<Pesagem, ApiError, PesagemUpdateInput>({
    mutationFn: (payload) =>
      apiFetch<Pesagem>(`/pesagens/${id}`, { method: "PUT", body: payload }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}

export function useExcluirPesagem() {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (id) => apiFetch<void>(`/pesagens/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}
