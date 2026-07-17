"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { usePesagens, useCriarPesagem, useExcluirPesagem } from "@/hooks/usePesagens";
import { InputMedida } from "@/components/domain/InputMedida";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { formatarDataHora, formatarPeso, paraInputDatetimeLocal } from "@/lib/format";

const novaPesagemSchema = z
  .object({
    peso_kg: z.coerce
      .number({ invalid_type_error: "Informe um peso válido." })
      .min(20, "O peso deve estar entre 20 e 400 kg.")
      .max(400, "O peso deve estar entre 20 e 400 kg."),
    registrada_em: z.string().optional(),
  })
  .refine(
    (dados) => !dados.registrada_em || new Date(dados.registrada_em) <= new Date(),
    { message: "Não é possível registrar uma data futura.", path: ["registrada_em"] }
  );

type NovaPesagemForm = z.infer<typeof novaPesagemSchema>;

export default function PesoPage() {
  const { pesagens, carregando, erro, refazer } = usePesagens();
  const criarPesagem = useCriarPesagem();
  const excluirPesagem = useExcluirPesagem();
  const [erroSubmissao, setErroSubmissao] = useState<string | null>(null);
  const [idExcluindo, setIdExcluindo] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<NovaPesagemForm>({
    resolver: zodResolver(novaPesagemSchema),
  });

  async function onSubmit(dados: NovaPesagemForm) {
    setErroSubmissao(null);
    try {
      await criarPesagem.mutateAsync({
        peso_kg: dados.peso_kg,
        registrada_em: dados.registrada_em
          ? new Date(dados.registrada_em).toISOString()
          : undefined,
      });
      reset();
    } catch (erro) {
      if (erro instanceof ApiError && erro.status === 422) {
        setErroSubmissao(
          typeof erro.body === "object" && erro.body && "detail" in erro.body
            ? String((erro.body as { detail: unknown }).detail)
            : "Não foi possível registrar essa pesagem. Confira os dados."
        );
      } else {
        setErroSubmissao("Não foi possível registrar sua pesagem agora. Tente novamente.");
      }
    }
  }

  async function excluir(id: string) {
    if (!window.confirm("Excluir esta pesagem? Essa ação não pode ser desfeita.")) return;
    setIdExcluindo(id);
    try {
      await excluirPesagem.mutateAsync(id);
    } finally {
      setIdExcluindo(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="mb-3 text-xl font-semibold">Registrar peso</h1>
        <Card>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <InputMedida
              id="peso_kg"
              label="Peso"
              unidade="kg"
              erro={errors.peso_kg?.message}
              {...register("peso_kg")}
            />
            <div>
              <Label htmlFor="registrada_em">Quando você se pesou (opcional)</Label>
              <Input
                id="registrada_em"
                type="datetime-local"
                max={paraInputDatetimeLocal(new Date())}
                aria-invalid={errors.registrada_em ? "true" : undefined}
                aria-describedby={errors.registrada_em ? "registrada_em-erro" : undefined}
                {...register("registrada_em")}
              />
              <p className="mt-1.5 text-xs text-neutral-500 dark:text-neutral-400">
                Deixe em branco para usar a data e hora de agora.
              </p>
              {errors.registrada_em && (
                <p
                  id="registrada_em-erro"
                  className="mt-1.5 text-sm text-rose-600 dark:text-rose-400"
                >
                  {errors.registrada_em.message}
                </p>
              )}
            </div>
            {erroSubmissao && <Alert variant="erro">{erroSubmissao}</Alert>}
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "Registrando..." : "Registrar pesagem"}
            </Button>
          </form>
        </Card>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Histórico</h2>

        {carregando && (
          <div className="space-y-2" aria-busy="true" aria-label="Carregando histórico">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        )}

        {!carregando && erro && (
          <div className="space-y-3">
            <Alert variant="erro">
              Não foi possível carregar seu histórico de pesagens agora.
            </Alert>
            <Button variant="secondary" onClick={() => refazer()}>
              Tentar de novo
            </Button>
          </div>
        )}

        {!carregando && !erro && pesagens.length === 0 && (
          <Alert variant="info">
            Você ainda não registrou nenhuma pesagem. Use o formulário acima para começar.
          </Alert>
        )}

        {!carregando && !erro && pesagens.length > 0 && (
          <ul className="space-y-2">
            {pesagens.map((pesagem) => (
              <li key={pesagem.id}>
                <Card className="flex items-center justify-between gap-3 p-4">
                  <div>
                    <p className="font-medium tabular-nums">{formatarPeso(pesagem.peso_kg)}</p>
                    <p className="text-sm text-neutral-500 dark:text-neutral-400">
                      {formatarDataHora(pesagem.registrada_em)}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Link
                      href={`/peso/${pesagem.id}`}
                      className="text-sm text-acento-600 hover:underline dark:text-acento-500"
                    >
                      Editar
                    </Link>
                    <button
                      type="button"
                      onClick={() => excluir(pesagem.id)}
                      disabled={idExcluindo === pesagem.id}
                      className="text-sm text-neutral-500 hover:text-rose-600 disabled:opacity-50 dark:text-neutral-400"
                      aria-label={`Excluir pesagem de ${formatarDataHora(pesagem.registrada_em)}`}
                    >
                      {idExcluindo === pesagem.id ? "Excluindo..." : "Excluir"}
                    </button>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
